from __future__ import annotations

import time
from typing import Any

import requests

from broker.models import QuoteResult

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


class AlphaVantageStockDataProvider:
    def __init__(
        self,
        api_key: str,
        cache_ttl_sec: int = 60,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (6.0, 12.0),
    ) -> None:
        self._api_key = api_key.strip()
        self._cache_ttl_sec = max(1, int(cache_ttl_sec))
        self._session = session or requests.Session()
        self._timeout = timeout
        self._cache: dict[str, tuple[float, QuoteResult]] = {}

    def fetch_stock_price(self, symbol: str) -> QuoteResult | None:
        normalized_symbol = normalize_symbol(symbol)
        if not normalized_symbol or not self._api_key:
            return None

        cached_quote = self._get_cached_quote(normalized_symbol)
        if cached_quote is not None:
            return cached_quote

        payload = self._request_quote(normalized_symbol)
        quote_result = self._build_quote_result(normalized_symbol, payload)
        if quote_result is not None:
            self._cache[normalized_symbol] = (time.monotonic(), quote_result)
        return quote_result

    def _get_cached_quote(self, symbol: str) -> QuoteResult | None:
        cached_entry = self._cache.get(symbol)
        if cached_entry is None:
            return None

        created_at, quote_result = cached_entry
        if time.monotonic() - created_at > self._cache_ttl_sec:
            self._cache.pop(symbol, None)
            return None
        return quote_result

    def _request_quote(self, symbol: str) -> dict[str, Any] | None:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self._api_key,
        }
        try:
            response = self._session.get(
                ALPHA_VANTAGE_URL,
                params=params,
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None
        if payload.get("Information") or payload.get("Note") or payload.get("Error Message"):
            return None
        return payload

    def _build_quote_result(self, symbol: str, payload: dict[str, Any] | None) -> QuoteResult | None:
        if payload is None:
            return None

        quote = payload.get("Global Quote")
        if not isinstance(quote, dict):
            return None

        raw_price = quote.get("05. price")
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None

        return QuoteResult(
            symbol=symbol,
            price=price,
            source="alpha_vantage",
            is_realtime=False,
        )
