from __future__ import annotations

import json

from flask import Flask, jsonify, request

from broker.alpha_vantage.stock_data import AlphaVantageStockDataProvider
from config import AppConfig, configure_logging
from notification.line_push import LineMessagingClient
from notification.line_receive import (
    InMemoryConversationStateStore,
    LineReceiveService,
    verify_line_signature,
)


def create_app(
    config: AppConfig | None = None,
    quote_provider: object | None = None,
    messaging_client: object | None = None,
    state_store: InMemoryConversationStateStore | None = None,
):
    active_config = config or AppConfig.from_env()
    active_config.ensure_directories()

    logger = configure_logging(active_config.log_file_path)
    active_quote_provider = quote_provider or AlphaVantageStockDataProvider(
        api_key=active_config.alpha_vantage_api_key,
        cache_ttl_sec=active_config.quote_cache_ttl_sec,
    )
    active_messaging_client = messaging_client or LineMessagingClient(
        channel_access_token=active_config.line_channel_access_token,
    )
    active_state_store = state_store or InMemoryConversationStateStore(
        ttl_sec=active_config.state_ttl_sec,
    )

    line_receive_service = LineReceiveService(
        quote_provider=active_quote_provider,
        reply_sender=active_messaging_client.reply_text,
        state_store=active_state_store,
        logger=logger,
    )

    app = Flask(__name__)
    app.config["APP_CONFIG"] = active_config
    app.config["LINE_RECEIVE_SERVICE"] = line_receive_service

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/callback")
    def callback():
        body = request.get_data(cache=False, as_text=False)
        signature = request.headers.get("x-line-signature", "")

        if not verify_line_signature(
            body=body,
            signature=signature,
            channel_secret=active_config.line_channel_secret,
        ):
            logger.warning("signature_invalid")
            return jsonify({"error": "invalid signature"}), 400

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("payload_invalid")
            return jsonify({"error": "invalid payload"}), 400

        line_receive_service.handle_payload(payload)
        return jsonify({"status": "ok"})

    return app


def main() -> int:
    active_config = AppConfig.from_env()
    app = create_app(config=active_config)
    app.run(host=active_config.app_host, port=active_config.app_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
