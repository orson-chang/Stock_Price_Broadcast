from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

from broker.models import QuoteResult
from config import AppConfig
from main import create_app
from notification.line_receive import InMemoryConversationStateStore


class FakeQuoteProvider:
    def __init__(self) -> None:
        self.seen_symbols: list[str] = []

    def fetch_stock_price(self, symbol: str) -> QuoteResult | None:
        self.seen_symbols.append(symbol)
        if symbol == "NVDA":
            return QuoteResult(
                symbol="NVDA",
                price=999.12,
                source="fake",
                is_realtime=False,
            )
        return None


class FakeMessagingClient:
    def __init__(self) -> None:
        self.replies: list[tuple[str, str]] = []

    def reply_text(self, reply_token: str, text: str) -> None:
        self.replies.append((reply_token, text))


def sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        line_channel_access_token="test-line-token",
        line_channel_secret="test-line-secret",
        alpha_vantage_api_key="test-alpha-key",
        data_dir=tmp_path / "data",
        log_file_path=tmp_path / "logs" / "trade_log.txt",
    )


def test_healthz_returns_ok(tmp_path: Path) -> None:
    app = create_app(
        config=make_config(tmp_path),
        quote_provider=FakeQuoteProvider(),
        messaging_client=FakeMessagingClient(),
        state_store=InMemoryConversationStateStore(ttl_sec=300),
    )

    client = app.test_client()
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_callback_accepts_valid_signature_and_handles_flow(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    quote_provider = FakeQuoteProvider()
    messaging_client = FakeMessagingClient()
    app = create_app(
        config=config,
        quote_provider=quote_provider,
        messaging_client=messaging_client,
        state_store=InMemoryConversationStateStore(ttl_sec=300),
    )

    client = app.test_client()
    stock_body = json.dumps({"events": [_make_text_event("Stock", "reply-1")]}).encode("utf-8")
    stock_response = client.post(
        "/callback",
        data=stock_body,
        headers={"x-line-signature": sign_body(config.line_channel_secret, stock_body)},
        content_type="application/json",
    )

    nvda_body = json.dumps({"events": [_make_text_event("NVDA", "reply-2")]}).encode("utf-8")
    nvda_response = client.post(
        "/callback",
        data=nvda_body,
        headers={"x-line-signature": sign_body(config.line_channel_secret, nvda_body)},
        content_type="application/json",
    )

    assert stock_response.status_code == 200
    assert nvda_response.status_code == 200
    assert quote_provider.seen_symbols == ["NVDA"]
    assert messaging_client.replies == [
        ("reply-1", "please provide Stock index"),
        ("reply-2", "NVDA stock now is 999.12"),
    ]


def test_callback_rejects_invalid_signature(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(
        config=config,
        quote_provider=FakeQuoteProvider(),
        messaging_client=FakeMessagingClient(),
        state_store=InMemoryConversationStateStore(ttl_sec=300),
    )

    client = app.test_client()
    body = json.dumps({"events": [_make_text_event("Stock", "reply-1")]}).encode("utf-8")
    response = client.post(
        "/callback",
        data=body,
        headers={"x-line-signature": "bad-signature"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid signature"}


def _make_text_event(text: str, reply_token: str) -> dict[str, object]:
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {
            "type": "user",
            "userId": "U999",
        },
        "message": {
            "type": "text",
            "text": text,
        },
    }
