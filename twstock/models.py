from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class OrderBookLevel:
    price: float | None = None
    size: int | None = None


@dataclass
class OrderBook:
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    bid_total: int | None = None
    ask_total: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bids": [asdict(level) for level in self.bids],
            "asks": [asdict(level) for level in self.asks],
            "bid_total": self.bid_total,
            "ask_total": self.ask_total,
        }


@dataclass
class Quote:
    symbol: str
    name: str | None = None
    price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    avg_price: float | None = None
    volume: int | None = None
    prev_volume: int | None = None
    amount_yi: float | None = None
    amplitude: float | None = None
    status: str | None = None
    update_time: str | None = None
    orderbook: OrderBook = field(default_factory=OrderBook)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_flat_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "change": self.change,
            "change_percent": self.change_percent,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "prev_close": self.prev_close,
            "avg_price": self.avg_price,
            "volume": self.volume,
            "prev_volume": self.prev_volume,
            "amount_yi": self.amount_yi,
            "amplitude": self.amplitude,
            "status": self.status,
            "update_time": self.update_time,
        }
        for i, bid in enumerate(self.orderbook.bids, start=1):
            d[f"bid{i}_price"] = bid.price
            d[f"bid{i}_size"] = bid.size
        for i, ask in enumerate(self.orderbook.asks, start=1):
            d[f"ask{i}_price"] = ask.price
            d[f"ask{i}_size"] = ask.size
        d["bid_total"] = self.orderbook.bid_total
        d["ask_total"] = self.orderbook.ask_total
        return d


@dataclass
class HistoryBar:
    timestamp: int
    datetime: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
