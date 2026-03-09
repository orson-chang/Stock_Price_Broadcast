from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from broker.models import QuoteResult
from notification.line_receive import (
    OPTION_NOT_READY_PROMPT,
    START_PROMPT,
    STATE_AWAITING_STOCK_SYMBOL,
    STATE_IDLE,
    STOCK_PROMPT,
    InMemoryConversationStateStore,
    LineReceiveService,
    verify_line_signature,
)


class FakeQuoteProvider:
    def __init__(self, quotes: dict[str, QuoteResult] | None = None) -> None:
        self._quotes = quotes or {}
        self.seen_symbols: list[str] = []

    def fetch_stock_price(self, symbol: str) -> QuoteResult | None:
        self.seen_symbols.append(symbol)
        return self._quotes.get(symbol)


class FakeReplySender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, reply_token: str, text: str) -> None:
        self.calls.append((reply_token, text))


def make_logger() -> logging.Logger:
    logger = logging.getLogger("test.line_receive")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def make_text_event(text: str, reply_token: str = "reply-token", user_id: str = "U123") -> dict[str, object]:
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {
            "type": "user",
            "userId": user_id,
        },
        "message": {
            "type": "text",
            "text": text,
        },
    }


def test_verify_line_signature_accepts_valid_signature() -> None:
    body = b'{"events":[]}'
    secret = "channel-secret"
    signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")

    assert verify_line_signature(body=body, signature=signature, channel_secret=secret) is True


def test_verify_line_signature_rejects_invalid_signature() -> None:
    assert verify_line_signature(
        body=b'{"events":[]}',
        signature="invalid-signature",
        channel_secret="channel-secret",
    ) is False


def test_stock_command_sets_waiting_state() -> None:
    provider = FakeQuoteProvider()
    replies = FakeReplySender()
    state_store = InMemoryConversationStateStore(ttl_sec=300)
    service = LineReceiveService(provider, replies, state_store, make_logger())

    service.handle_payload({"events": [make_text_event(" Stock ")]})

    assert replies.calls == [("reply-token", STOCK_PROMPT)]
    assert state_store.get_state("user:U123") == STATE_AWAITING_STOCK_SYMBOL


def test_waiting_state_fetches_quote_and_clears_state() -> None:
    provider = FakeQuoteProvider(
        {
            "NVDA": QuoteResult(
                symbol="NVDA",
                price=123.45,
                source="fake",
                is_realtime=False,
            )
        }
    )
    replies = FakeReplySender()
    state_store = InMemoryConversationStateStore(ttl_sec=300)
    service = LineReceiveService(provider, replies, state_store, make_logger())

    service.handle_payload({"events": [make_text_event("stock", reply_token="reply-1")]})
    service.handle_payload({"events": [make_text_event(" nvda ", reply_token="reply-2")]})

    assert provider.seen_symbols == ["NVDA"]
    assert replies.calls[-1] == ("reply-2", "NVDA stock now is 123.45")
    assert state_store.get_state("user:U123") == STATE_IDLE


def test_failed_quote_keeps_waiting_state() -> None:
    provider = FakeQuoteProvider()
    replies = FakeReplySender()
    state_store = InMemoryConversationStateStore(ttl_sec=300)
    service = LineReceiveService(provider, replies, state_store, make_logger())

    service.handle_payload({"events": [make_text_event("Stock", reply_token="reply-1")]})
    service.handle_payload({"events": [make_text_event(" bad ", reply_token="reply-2")]})

    assert provider.seen_symbols == ["BAD"]
    assert replies.calls[-1] == ("reply-2", "unable to fetch BAD stock price now")
    assert state_store.get_state("user:U123") == STATE_AWAITING_STOCK_SYMBOL


def test_option_command_returns_placeholder_message() -> None:
    provider = FakeQuoteProvider()
    replies = FakeReplySender()
    state_store = InMemoryConversationStateStore(ttl_sec=300)
    service = LineReceiveService(provider, replies, state_store, make_logger())

    service.handle_payload({"events": [make_text_event("Option")]})

    assert replies.calls == [("reply-token", OPTION_NOT_READY_PROMPT)]


def test_non_waiting_message_returns_start_prompt() -> None:
    provider = FakeQuoteProvider()
    replies = FakeReplySender()
    state_store = InMemoryConversationStateStore(ttl_sec=300)
    service = LineReceiveService(provider, replies, state_store, make_logger())

    service.handle_payload({"events": [make_text_event("hello")]})

    assert replies.calls == [("reply-token", START_PROMPT)]
