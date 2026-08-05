from __future__ import annotations

import re
from types import TracebackType
from typing import Any

from playwright.sync_api import (
    APIRequestContext,
    Browser,
    Locator,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from .models import HistoryBar, OrderBook, OrderBookLevel, Quote

YAHOO_QUOTE_URL = "https://tw.stock.yahoo.com/quote/{symbol}.{exchange}"
YAHOO_CHART_API = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.{exchange}"

_HEADER_SELECTOR = "#main-0-QuoteHeader-Proxy"
_PRICE_SELECTOR = f'{_HEADER_SELECTOR} span[class*="Fz(32px)"]'
_OVERVIEW_SELECTOR = "#main-2-QuoteOverview-Proxy li.price-detail-item"
_ORDERBOOK_SELECTOR = 'div[class*="Mt(12px)"]'
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class StockScraper:
    """基於 Playwright 的奇摩股市即時報價爬蟲（同步 API）。"""

    _headless: bool
    _timeout_ms: int
    _playwright: Playwright | None
    _browser: Browser | None

    def __init__(self, headless: bool = True, timeout_ms: int = 60000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None

    def __enter__(self) -> "StockScraper":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    # ------------------------------------------------------------------ #
    # 公開介面
    # ------------------------------------------------------------------ #
    def fetch_quote(self, symbol: str, with_orderbook: bool = True) -> Quote:
        """抓取單一股票的即時報價，自動判斷上市(.TW) / 上櫃(.TWO)。"""
        assert self._browser is not None, "需先使用 with StockScraper(...) 進入"
        page = self._browser.new_page(user_agent=_UA, locale="zh-TW")
        try:
            self._find_exchange(page, symbol)
            quote = self._parse_quote(page, symbol)
            if with_orderbook:
                quote.orderbook = self._parse_orderbook(page)
            return quote
        finally:
            page.close()

    def fetch_history(self, symbol: str, range_: str, interval: str = "1d") -> list[HistoryBar]:
        """透過 Yahoo Chart API 下載歷史資料（使用 Playwright 的 APIRequestContext）。"""
        assert self._playwright is not None, "需先使用 with StockScraper(...) 進入"
        exchange = self._resolve_exchange(symbol)
        url = (
            f"{YAHOO_CHART_API.format(symbol=symbol, exchange=exchange)}"
            f"?interval={interval}&range={range_}"
        )
        ctx: APIRequestContext | None = None
        try:
            ctx = self._playwright.request.new_context()
            resp = ctx.get(url, headers={"User-Agent": _UA})
            if not resp.ok:
                raise RuntimeError(f"Chart API 回應異常: HTTP {resp.status}")
            data = resp.json()
            return self._parse_chart(data)
        finally:
            if ctx is not None:
                ctx.dispose()

    # ------------------------------------------------------------------ #
    # 內部實作
    # ------------------------------------------------------------------ #
    def _resolve_exchange(self, symbol: str) -> str:
        """先試上市(.TW)，頁面無資料時再試上櫃(.TWO)，回傳可用交易所。"""
        assert self._browser is not None, "需先使用 with StockScraper(...) 進入"
        page = self._browser.new_page(user_agent=_UA, locale="zh-TW")
        try:
            return self._find_exchange(page, symbol)
        finally:
            page.close()

    def _find_exchange(self, page: Page, symbol: str) -> str:
        for exchange in ("TW", "TWO"):
            url = YAHOO_QUOTE_URL.format(symbol=symbol, exchange=exchange)
            page.goto(url, wait_until="load", timeout=self._timeout_ms)
            if self._is_invalid_page(page):
                continue
            try:
                page.wait_for_selector(_PRICE_SELECTOR, timeout=15000)
                page.wait_for_selector(_OVERVIEW_SELECTOR, timeout=15000)
            except PlaywrightTimeoutError:
                continue
            real = self._extract_exchange(page.title())
            if real is not None:
                return real
            return exchange
        raise ValueError(f"找不到股票代號: {symbol}")

    @staticmethod
    def _extract_exchange(title: str) -> str | None:
        match = re.search(r"\.(TW|TWO)\)", title)
        return match.group(1) if match else None

    @staticmethod
    def _is_invalid_page(page: Page) -> bool:
        url = page.url.lower()
        return url.startswith("https://tw.yahoo.com") or "err=404" in url

    def _parse_quote(self, page: Page, symbol: str) -> Quote:
        header = page.locator(_HEADER_SELECTOR)

        name = self._safe_text(header.locator("h1"))

        price = self._safe_float(self._safe_text(header.locator(f'span[class*="Fz(32px)"]')))
        change = self._safe_float(
            self._safe_text(header.locator('span[class*="Fz(20px)"][class*="Fw(b)"][class*="Lh(1.2)"][class*="Mend(4px)"]'))
        )
        change_percent = self._safe_float(
            self._safe_text(header.locator('span[class*="Jc(fe)"][class*="Fz(20px)"]'))
        )

        status_text = self._safe_text(header.locator('span[class*="C(#6e7780)"]'))
        status, update_time = self._parse_status(status_text)

        overview: dict[str, float | int | None] = {}
        for i in range(page.locator(_OVERVIEW_SELECTOR).count()):
            item = page.locator(_OVERVIEW_SELECTOR).nth(i)
            label = self._safe_text(item.locator("span").nth(0))
            value_text = self._safe_text(item.locator("span").nth(1))
            if label:
                overview[label] = self._coerce_number(value_text)

        return Quote(
            symbol=symbol,
            name=name,
            price=price,
            change=change,
            change_percent=change_percent,
            open=self._num(overview.get("開盤")),
            high=self._num(overview.get("最高")),
            low=self._num(overview.get("最低")),
            prev_close=self._num(overview.get("昨收")),
            avg_price=self._num(overview.get("均價")),
            volume=self._int(overview.get("總量")),
            prev_volume=self._int(overview.get("昨量")),
            amount_yi=self._num(overview.get("成交金額(億)")),
            amplitude=self._num(overview.get("振幅")),
            status=status,
            update_time=update_time,
        )

    def _parse_orderbook(self, page: Page) -> OrderBook:
        container = (
            page.locator(_ORDERBOOK_SELECTOR)
            .filter(has_text="委買價")
            .filter(has_text="委賣價")
            .first
        )
        try:
            container.wait_for(timeout=10000)
        except PlaywrightTimeoutError:
            return OrderBook()

        columns = container.locator('div[class*="W(50%)"]')
        if columns.count() < 2:
            return OrderBook()

        bids, bid_total = self._parse_orderbook_column(columns.nth(0))
        asks, ask_total = self._parse_orderbook_column(columns.nth(1))
        return OrderBook(bids=bids, asks=asks, bid_total=bid_total, ask_total=ask_total)

    def _parse_orderbook_column(
        self, column: Locator
    ) -> tuple[list[OrderBookLevel], int | None]:
        children = column.locator(":scope > div")
        if children.count() < 2:
            return [], None

        labels = children.nth(0).locator("span").all_inner_texts()
        size_first = bool(labels) and labels[0].strip() == "量"

        rows = children.nth(1)
        sub = rows.locator(":scope > div")
        if sub.count() < 2:
            return [], None

        block_a = sub.nth(0)
        block_b = sub.nth(1)

        size_block = block_a if size_first else block_b
        price_block = block_b if size_first else block_a

        sizes = [self._safe_text(cell).strip() for cell in size_block.locator(":scope > div").all()]
        prices = [
            self._safe_text(cell).strip() for cell in price_block.locator(":scope > div span").all()
        ]

        levels = [
            OrderBookLevel(price=self._safe_float(p), size=self._safe_int(s))
            for p, s in zip(prices, sizes)
        ]

        total = None
        if children.count() >= 3:
            total_text = children.nth(2).inner_text()
            match = re.search(r"[\d,]+", total_text)
            if match:
                total = self._safe_int(match.group(0))
        return levels, total

    def _parse_chart(self, data: dict[str, Any]) -> list[HistoryBar]:
        result = data["chart"]["result"][0]
        timestamps: list[int] = result.get("timestamp", [])
        quote = result["indicators"]["quote"][0]
        bars: list[HistoryBar] = []
        for i, ts in enumerate(timestamps):
            bars.append(
                HistoryBar(
                    timestamp=ts,
                    datetime=self._format_ts(ts),
                    open=self._idx(quote.get("open"), i),
                    high=self._idx(quote.get("high"), i),
                    low=self._idx(quote.get("low"), i),
                    close=self._idx(quote.get("close"), i),
                    volume=self._safe_int(self._idx(quote.get("volume"), i)),
                )
            )
        return bars

    # ------------------------------------------------------------------ #
    # 工具函式
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_text(locator: Locator) -> str:
        try:
            return locator.inner_text().strip()
        except Exception:
            return ""

    @staticmethod
    def _parse_status(text: str) -> tuple[str | None, str | None]:
        if not text:
            return None, None
        parts = [p.strip() for p in text.split("|")]
        status = parts[0] if parts else None
        update_time = parts[1].replace("更新", "").strip() if len(parts) > 1 else None
        return status, update_time

    @staticmethod
    def _coerce_number(text: str) -> float | int | None:
        value = StockScraper._safe_float(text)
        if value is not None and value == int(value):
            return int(value)
        return value

    @staticmethod
    def _num(value: float | int | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _int(value: float | int | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(text: str | float | int | None) -> float | None:
        if text is None:
            return None
        cleaned = (
            str(text)
            .replace(",", "")
            .replace("%", "")
            .replace("(", "")
            .replace(")", "")
            .replace("+", "")
            .strip()
        )
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _safe_int(text: str | float | int | None) -> int | None:
        value = StockScraper._safe_float(text)
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _idx(
        values: list[float | int | None] | None, i: int
    ) -> float | int | None:
        if not values or i >= len(values):
            return None
        value = values[i]
        if value is None:
            return None
        return value

    @staticmethod
    def _format_ts(ts: int) -> str:
        import datetime

        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
