from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class QuoteResult:
    symbol: str
    price: float
    source: str
    is_realtime: bool


class StockPriceProvider(Protocol):
    def fetch_stock_price(self, symbol: str) -> QuoteResult | None:
        """Return the latest stock price for a symbol."""
