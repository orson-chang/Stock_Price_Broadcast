from __future__ import annotations

import requests

LINE_MESSAGE_API_BASE = "https://api.line.me/v2/bot/message"


class LineMessagingClient:
    def __init__(
        self,
        channel_access_token: str,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (6.0, 20.0),
    ) -> None:
        self._channel_access_token = channel_access_token.strip()
        self._session = session or requests.Session()
        self._timeout = timeout

    def reply_text(self, reply_token: str, text: str) -> None:
        payload = {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
        self._post("reply", payload)

    def push_text(self, to_id: str, text: str) -> None:
        payload = {
            "to": to_id,
            "messages": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
        self._post("push", payload)

    def _post(self, endpoint: str, payload: dict[str, object]) -> None:
        headers = {
            "Authorization": f"Bearer {self._channel_access_token}",
            "Content-Type": "application/json",
        }
        response = self._session.post(
            f"{LINE_MESSAGE_API_BASE}/{endpoint}",
            headers=headers,
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
