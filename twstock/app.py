from __future__ import annotations

import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

import gradio as gr
import pandas as pd

from twstock.main import HISTORY_INTERVALS, load_config
from twstock.models import Quote
from twstock.output import write_history, write_quotes
from twstock.scraper import StockScraper

_SCRAPER_START_TIMEOUT = 60

_QUOTE_COLUMNS_ZH: dict[str, str] = {
    "symbol": "代號",
    "name": "名稱",
    "price": "成交價",
    "change": "漲跌",
    "change_percent": "漲跌幅(%)",
    "open": "開盤",
    "high": "最高",
    "low": "最低",
    "prev_close": "昨收",
    "avg_price": "均價",
    "volume": "成交量(張)",
    "prev_volume": "昨量",
    "amount_yi": "成交金額(億)",
    "amplitude": "振幅(%)",
    "status": "狀態",
    "update_time": "更新時間",
    "bid1_price": "買1價",
    "bid1_size": "買1量",
    "bid2_price": "買2價",
    "bid2_size": "買2量",
    "bid3_price": "買3價",
    "bid3_size": "買3量",
    "bid4_price": "買4價",
    "bid4_size": "買4量",
    "bid5_price": "買5價",
    "bid5_size": "買5量",
    "ask1_price": "賣1價",
    "ask1_size": "賣1量",
    "ask2_price": "賣2價",
    "ask2_size": "賣2量",
    "ask3_price": "賣3價",
    "ask3_size": "賣3量",
    "ask4_price": "賣4價",
    "ask4_size": "賣4量",
    "ask5_price": "賣5價",
    "ask5_size": "賣5量",
    "bid_total": "委買小計",
    "ask_total": "委賣小計",
}

_HISTORY_COLUMNS_ZH: dict[str, str] = {
    "datetime": "時間",
    "symbol": "代號",
    "open": "開盤",
    "high": "最高",
    "low": "最低",
    "close": "收盤",
    "volume": "成交量",
}

_QUOTE_COLUMNS_ORDER = [
    "symbol",
    "name",
    "price",
    "change",
    "change_percent",
    "open",
    "high",
    "low",
    "prev_close",
    "avg_price",
    "volume",
    "prev_volume",
    "amount_yi",
    "amplitude",
    "status",
    "update_time",
] + [k for k in _QUOTE_COLUMNS_ZH if k not in [
    "symbol",
    "name",
    "price",
    "change",
    "change_percent",
    "open",
    "high",
    "low",
    "prev_close",
    "avg_price",
    "volume",
    "prev_volume",
    "amount_yi",
    "amplitude",
    "status",
    "update_time",
]]


_Job = tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]


class _BrowserWorker:
    """Playwright 瀏覽器常駐於單一執行緒，所有 Playwright 呼叫皆在此執行緒執行。

    Gradio 每次事件可能跑在不同 worker thread，而 Playwright sync API 的
    瀏覽器物件綁定建立它的執行緒，跨執行緒使用會報錯，故以專屬執行緒串接。
    """

    def __init__(self, headless: bool, timeout_ms: int) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._start_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue[_Job] | None = None
        self._ready: threading.Event | None = None
        self._init_error: Exception | None = None

    def _ensure_started(self) -> None:
        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._init_error = None
                self._ready = threading.Event()
                self._queue = queue.Queue()
                self._thread = threading.Thread(
                    target=self._run, daemon=True, name="stock-browser"
                )
                self._thread.start()

    def _run(self) -> None:
        assert self._ready is not None and self._queue is not None
        scraper = StockScraper(headless=self._headless, timeout_ms=self._timeout_ms)
        try:
            scraper.__enter__()
        except Exception as exc:
            self._init_error = exc
            self._ready.set()
            return
        self._ready.set()
        while True:
            func, args, holder = self._queue.get()
            try:
                holder["result"] = func(scraper, *args)
                holder["error"] = None
            except Exception as exc:
                holder["result"] = None
                holder["error"] = exc
            finally:
                holder["done"].set()

    def submit(self, func: Callable[..., Any], *args: Any) -> Any:
        self._ensure_started()
        assert self._ready is not None and self._queue is not None
        if not self._ready.wait(timeout=_SCRAPER_START_TIMEOUT):
            raise RuntimeError("瀏覽器啟動逾時")
        if self._init_error is not None:
            raise RuntimeError(f"瀏覽器啟動失敗: {self._init_error}") from self._init_error
        with self._request_lock:
            holder: dict[str, Any] = {
                "done": threading.Event(),
                "result": None,
                "error": None,
            }
            self._queue.put((func, args, holder))
            holder["done"].wait()
            if holder["error"] is not None:
                raise holder["error"]
            return holder["result"]


_worker: _BrowserWorker | None = None


def _get_worker() -> _BrowserWorker:
    global _worker
    if _worker is None:
        cfg = load_config()
        scraper_cfg = cfg.get("scraper", {})
        _worker = _BrowserWorker(
            headless=bool(scraper_cfg.get("headless", True)),
            timeout_ms=int(scraper_cfg.get("timeout_ms", 60000)),
        )
    return _worker


def _parse_symbols(text: str) -> list[str]:
    tokens = [t.strip() for t in text.replace(",", " ").replace("\n", " ").split()]
    seen: list[str] = []
    for token in tokens:
        if token and token not in seen:
            seen.append(token)
    return seen


def _out_dir(cfg: dict[str, Any]) -> str:
    return str(cfg.get("output", {}).get("dir", "output"))


def _quote_summary(q: Quote) -> str:
    price = f"{q.price:,.2f}" if q.price is not None else "?"
    change = f"{q.change_percent:+.2f}%" if q.change_percent is not None else "?"
    return f"[OK] {q.symbol} {q.name or ''} 成交 {price} 漲跌幅 {change} 狀態 {q.status or '?'}"


# ------------------------------------------------------------------ #
# 實際抓取邏輯（在瀏覽器專屬執行緒內執行）
# ------------------------------------------------------------------ #
def _fetch_quotes_impl(
    scraper: StockScraper, symbols: list[str], with_orderbook: bool
) -> tuple[list[Quote], list[str]]:
    quotes: list[Quote] = []
    errors: list[str] = []
    for symbol in symbols:
        try:
            quotes.append(scraper.fetch_quote(symbol, with_orderbook=with_orderbook))
        except Exception as exc:
            errors.append(f"[FAIL] {symbol} 抓取失敗: {exc}")
    return quotes, errors


def _fetch_history_impl(
    scraper: StockScraper, symbols: list[str], interval: str, range_: str, out_dir: str
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    files: list[str] = []
    for symbol in symbols:
        try:
            bars = scraper.fetch_history(symbol, range_, interval)
            for bar in bars:
                row = bar.to_dict()
                row["symbol"] = symbol
                rows.append(row)
            files.append(str(write_history(bars, symbol, out_dir)))
        except Exception as exc:
            errors.append(f"[FAIL] {symbol} 歷史資料抓取失敗: {exc}")
    return rows, errors, files


# ------------------------------------------------------------------ #
# Gradio 事件處理
# ------------------------------------------------------------------ #
def fetch_quotes(symbols_text: str, with_orderbook: bool, save_output: bool):
    symbols = _parse_symbols(symbols_text)
    if not symbols:
        return pd.DataFrame(), {}, "請先輸入股票代號", []

    try:
        quotes, errors = _get_worker().submit(_fetch_quotes_impl, symbols, with_orderbook)
    except Exception as exc:
        return pd.DataFrame(), {}, f"[FAIL] 瀏覽器啟動失敗: {exc}", []

    df = pd.DataFrame([q.to_flat_dict() for q in quotes])
    if df.empty:
        df = pd.DataFrame(columns=_QUOTE_COLUMNS_ORDER)
    else:
        df = df.reindex(columns=_QUOTE_COLUMNS_ORDER)
    df.columns = [_QUOTE_COLUMNS_ZH.get(c, c) for c in df.columns]
    payload: dict[str, Any] = {
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "quotes": [q.to_dict() for q in quotes],
        "errors": errors,
    }

    files: list[str] = []
    if save_output and quotes:
        cfg = load_config()
        formats = cfg.get("output", {}).get("formats", ["json", "csv"])
        files = [str(p) for p in write_quotes(quotes, _out_dir(cfg), formats)]

    log_lines = [_quote_summary(q) for q in quotes]
    log_lines += errors
    log = "\n".join(log_lines) if log_lines else "（無結果）"
    return df, payload, log, files


def fetch_history(symbols_text: str, range_choice: str):
    symbols = _parse_symbols(symbols_text)
    if not symbols:
        return pd.DataFrame(), "請先輸入股票代號", []

    interval, range_ = HISTORY_INTERVALS[range_choice]
    cfg = load_config()

    try:
        rows, errors, files = _get_worker().submit(
            _fetch_history_impl, symbols, interval, range_, _out_dir(cfg)
        )
    except Exception as exc:
        return pd.DataFrame(), f"[FAIL] 瀏覽器啟動失敗: {exc}", []

    if rows:
        df = pd.DataFrame(rows)
        df = df[["datetime", "symbol", "open", "high", "low", "close", "volume"]]
    else:
        df = pd.DataFrame(columns=["datetime", "symbol", "open", "high", "low", "close", "volume"])
    df.columns = [_HISTORY_COLUMNS_ZH.get(c, c) for c in df.columns]

    log_lines = [f"[OK] 已下載 {len(rows)} 筆歷史資料"] if rows else []
    log_lines += errors
    log = "\n".join(log_lines) if log_lines else "（無結果）"
    return df, log, files


# ------------------------------------------------------------------ #
# UI
# ------------------------------------------------------------------ #
def build_app() -> gr.Blocks:
    cfg = load_config()
    default_symbols = " ".join(str(s) for s in cfg.get("stocks", ["2330", "2317", "2454"]))

    with gr.Blocks(title="台股即時資料爬蟲") as demo:
        gr.Markdown("# 台股即時資料爬蟲（奇摩股市 + Playwright）")
        gr.Markdown("資料來源：奇摩股市即時報價。上櫃股票（如 5347）會自動以 .TWO 抓取。")

        with gr.Tab("即時行情"):
            with gr.Row():
                symbols = gr.Textbox(
                    label="股票代號",
                    value=default_symbols,
                    placeholder="以逗號或空白分隔，例：2330, 2317, 5347",
                )
                with gr.Column():
                    orderbook = gr.Checkbox(label="抓取買賣五檔", value=True)
                    save_quotes = gr.Checkbox(label="儲存至 output/", value=True)
                    auto_refresh = gr.Checkbox(label="盤中自動更新", value=False)
                    refresh_interval = gr.Radio(
                        label="更新間隔",
                        choices=["5", "10", "30", "60"],
                        value="10",
                        visible=False,
                    )
            fetch_btn = gr.Button("抓取報價", variant="primary")
            quotes_df = gr.Dataframe(
                label="報價一覽",
                interactive=False,
                headers=list(_QUOTE_COLUMNS_ZH.values()),
            )
            quote_json = gr.JSON(label="詳細資料（含買賣五檔）")
            log = gr.Markdown("")
            out_files = gr.Files(label="輸出檔案")

            refresh_timer = gr.Timer(value=10, active=False)

            def toggle_auto_refresh(checked: bool, interval: str):
                return (
                    gr.Timer(active=checked, value=int(interval)),
                    gr.Radio(visible=checked),
                )

            auto_refresh.change(
                toggle_auto_refresh,
                inputs=[auto_refresh, refresh_interval],
                outputs=[refresh_timer, refresh_interval],
            )

            fetch_btn.click(
                fetch_quotes,
                inputs=[symbols, orderbook, save_quotes],
                outputs=[quotes_df, quote_json, log, out_files],
            )
            refresh_timer.tick(
                fetch_quotes,
                inputs=[symbols, orderbook, save_quotes],
                outputs=[quotes_df, quote_json, log, out_files],
            )

        with gr.Tab("歷史資料"):
            with gr.Row():
                hist_symbols = gr.Textbox(label="股票代號", value=default_symbols)
                hist_range = gr.Dropdown(
                    label="區間",
                    choices=list(HISTORY_INTERVALS.keys()),
                    value="1mo",
                )
            hist_btn = gr.Button("下載歷史資料", variant="primary")
            hist_df = gr.Dataframe(
                label="歷史資料",
                interactive=False,
                headers=list(_HISTORY_COLUMNS_ZH.values()),
            )
            hist_log = gr.Markdown("")
            hist_files = gr.Files(label="輸出 CSV")

            hist_btn.click(
                fetch_history,
                inputs=[hist_symbols, hist_range],
                outputs=[hist_df, hist_log, hist_files],
            )

    return demo


demo = build_app()

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), server_name="127.0.0.1", server_port=7860)
