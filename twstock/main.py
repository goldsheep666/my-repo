from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from twstock.output import write_history, write_quotes  # noqa: E402
from twstock.models import Quote  # noqa: E402
from twstock.scraper import StockScraper  # noqa: E402

CONFIG_FILE = BASE_DIR / "config.json"

HISTORY_INTERVALS: dict[str, tuple[str, str]] = {
    "1m": ("1m", "1d"),
    "5d": ("5m", "5d"),
    "1mo": ("1d", "1mo"),
    "3mo": ("1d", "3mo"),
    "6mo": ("1d", "6mo"),
    "1y": ("1d", "1y"),
    "5y": ("1wk", "5y"),
}


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_stocks(args_stocks: list[str], config: dict[str, Any]) -> list[str]:
    if args_stocks:
        return args_stocks
    return [str(s) for s in config.get("stocks", [])]


def _resolve_formats(args_format: str | None, config: dict[str, Any]) -> list[str]:
    if args_format == "both":
        return ["json", "csv"]
    if args_format:
        return [args_format]
    return [str(f) for f in config.get("output", {}).get("formats", ["json", "csv"])]


def _reconfigure_stdout() -> None:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass


def main() -> None:
    _reconfigure_stdout()

    parser = argparse.ArgumentParser(
        description="台股即時資料爬蟲（奇摩股市 + Playwright）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("stocks", nargs="*", help="股票代號（空格分隔）；未提供時讀取 config.json")
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default=None,
        help="輸出格式（預設讀取 config.json）",
    )
    parser.add_argument("--no-orderbook", action="store_true", help="不爬取買賣五檔")
    parser.add_argument(
        "--history",
        choices=list(HISTORY_INTERVALS.keys()),
        default=None,
        help="額外下載歷史資料區間",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="是否使用無頭模式（預設讀取 config.json）",
    )
    args = parser.parse_args()

    config = load_config()
    stocks = _resolve_stocks(args.stocks, config)
    formats = _resolve_formats(args.format, config)

    if not stocks:
        print("[FAIL] 沒有指定股票代號，且 config.json 未設定 stocks", file=sys.stderr)
        sys.exit(1)

    scraper_cfg = config.get("scraper", {})
    headless = scraper_cfg.get("headless", True) if args.headless is None else args.headless
    timeout_ms = int(scraper_cfg.get("timeout_ms", 60000))
    out_dir = config.get("output", {}).get("dir", "output")

    print(f"[INFO] 監控 {len(stocks)} 檔股票: {', '.join(stocks)}")
    print(f"[INFO] 輸出格式: {', '.join(formats)}  |  headless={headless}")

    with StockScraper(headless=headless, timeout_ms=timeout_ms) as scraper:
        quotes: list[Quote] = []
        for symbol in stocks:
            try:
                quote = scraper.fetch_quote(symbol, with_orderbook=not args.no_orderbook)
                quotes.append(quote)
                change = quote.change_percent
                change_str = f"{change:+.2f}%" if change is not None else "?"
                price_str = f"{quote.price:,.2f}" if quote.price is not None else "?"
                summary = (
                    f"[OK] {symbol} {quote.name or ''} 成交 {price_str} "
                    f"漲跌幅 {change_str} 狀態 {quote.status or '?'} {quote.update_time or ''}"
                )
                print(summary)
            except Exception as exc:
                print(f"[FAIL] {symbol} 抓取失敗: {exc}", file=sys.stderr)

        if quotes:
            written = write_quotes(quotes, out_dir, formats)
            for path in written:
                print(f"[OK] 已輸出: {path}")
        else:
            print("[WARN] 沒有任何成功抓取的報價，略過輸出")

        if args.history and stocks:
            interval, range_ = HISTORY_INTERVALS[args.history]
            for symbol in stocks:
                try:
                    bars = scraper.fetch_history(symbol, range_, interval)
                    path = write_history(bars, symbol, out_dir)
                    print(f"[OK] 歷史資料已輸出: {path}（{len(bars)} 筆）")
                except Exception as exc:
                    print(f"[FAIL] {symbol} 歷史資料抓取失敗: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
