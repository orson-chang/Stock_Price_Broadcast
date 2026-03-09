from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from broker.models import QuoteResult, StockPriceProvider

STATE_IDLE = "idle"
STATE_AWAITING_STOCK_SYMBOL = "awaiting_stock_symbol"

STOCK_PROMPT = "please provide Stock index"
START_PROMPT = "send Stock to start stock quote query"
OPTION_NOT_READY_PROMPT = "option query is not implemented yet"


def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    if not signature or not channel_secret:
        return False
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)


def normalize_command(text: str) -> str:
    return text.strip().casefold()


def normalize_stock_symbol(text: str) -> str:
    return text.strip().upper()


def format_stock_price(quote: QuoteResult) -> str:
    return f"{quote.price:.2f}"


def extract_source_context(event: dict[str, Any]) -> tuple[str, str]:
    source = event.get("source")
    if not isinstance(source, dict):
        return "unknown", "unknown:missing"

    source_type = str(source.get("type") or "unknown").strip() or "unknown"
    for key in ("userId", "groupId", "roomId"):
        raw_id = source.get(key)
        if raw_id:
            return source_type, f"{source_type}:{raw_id}"
    return source_type, f"{source_type}:missing"


@dataclass(slots=True)
class ConversationState:
    state: str
    updated_at: float


class InMemoryConversationStateStore:
    def __init__(self, ttl_sec: int = 300) -> None:
        self._ttl_sec = max(1, int(ttl_sec))
        self._state_by_source_id: dict[str, ConversationState] = {}

    def get_state(self, source_id: str) -> str:
        self._purge_expired()
        conversation_state = self._state_by_source_id.get(source_id)
        if conversation_state is None:
            return STATE_IDLE
        return conversation_state.state

    def set_state(self, source_id: str, state: str) -> None:
        self._purge_expired()
        self._state_by_source_id[source_id] = ConversationState(
            state=state,
            updated_at=time.monotonic(),
        )

    def clear_state(self, source_id: str) -> None:
        self._state_by_source_id.pop(source_id, None)

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired_keys = [
            source_id
            for source_id, conversation_state in self._state_by_source_id.items()
            if now - conversation_state.updated_at > self._ttl_sec
        ]
        for source_id in expired_keys:
            self._state_by_source_id.pop(source_id, None)


class LineReceiveService:
    def __init__(
        self,
        quote_provider: StockPriceProvider,
        reply_sender: Callable[[str, str], None],
        state_store: InMemoryConversationStateStore,
        logger: logging.Logger,
    ) -> None:
        self._quote_provider = quote_provider
        self._reply_sender = reply_sender
        self._state_store = state_store
        self._logger = logger

    def handle_payload(self, payload: dict[str, Any]) -> None:
        raw_events = payload.get("events", [])
        if not isinstance(raw_events, list):
            return

        for event in raw_events:
            if isinstance(event, dict):
                self._handle_event(event)

    def _handle_event(self, event: dict[str, Any]) -> None:
        if event.get("type") != "message":
            return

        reply_token = str(event.get("replyToken") or "").strip()
        message = event.get("message")
        if not reply_token or not isinstance(message, dict):
            return
        if message.get("type") != "text":
            return

        text = str(message.get("text") or "")
        source_type, source_id = extract_source_context(event)
        reply_text = self.handle_text_message(
            source_type=source_type,
            source_id=source_id,
            text=text,
        )
        self._reply_sender(reply_token, reply_text)

    def handle_text_message(self, source_type: str, source_id: str, text: str) -> str:
        normalized_text = text.strip()
        normalized_command = normalize_command(text)

        self._logger.info(
            "webhook_received source_type=%s source_id=%s text=%s",
            source_type,
            source_id,
            normalized_text,
        )

        if normalized_command == "stock":
            self._state_store.set_state(source_id, STATE_AWAITING_STOCK_SYMBOL)
            self._logger.info(
                "command=stock source_type=%s source_id=%s",
                source_type,
                source_id,
            )
            return STOCK_PROMPT

        if normalized_command == "option":
            self._logger.info(
                "command=option source_type=%s source_id=%s",
                source_type,
                source_id,
            )
            return OPTION_NOT_READY_PROMPT

        if self._state_store.get_state(source_id) == STATE_AWAITING_STOCK_SYMBOL:
            symbol = normalize_stock_symbol(normalized_text)
            quote_result = self._quote_provider.fetch_stock_price(symbol)
            if quote_result is not None:
                self._state_store.clear_state(source_id)
                formatted_price = format_stock_price(quote_result)
                self._logger.info(
                    "quote_status=success source_type=%s source_id=%s ticker=%s price=%s provider=%s",
                    source_type,
                    source_id,
                    quote_result.symbol,
                    formatted_price,
                    quote_result.source,
                )
                return f"{quote_result.symbol} stock now is {formatted_price}"

            self._state_store.set_state(source_id, STATE_AWAITING_STOCK_SYMBOL)
            self._logger.info(
                "quote_status=failure source_type=%s source_id=%s ticker=%s",
                source_type,
                source_id,
                symbol,
            )
            return f"unable to fetch {symbol} stock price now"

        self._logger.info(
            "command=help source_type=%s source_id=%s text=%s",
            source_type,
            source_id,
            normalized_text,
        )
        return START_PROMPT
