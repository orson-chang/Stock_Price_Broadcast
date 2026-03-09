from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = BASE_DIR / ".env"
LOGGER_NAME = "line_stock_bot"


def load_env_file(env_file: Path = DEFAULT_ENV_FILE) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def get_env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer env var: {name}={raw_value!r}") from exc


@dataclass(slots=True)
class AppConfig:
    line_channel_access_token: str
    line_channel_secret: str
    alpha_vantage_api_key: str
    app_host: str = "127.0.0.1"
    app_port: int = 5000
    state_ttl_sec: int = 300
    quote_cache_ttl_sec: int = 60
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    log_file_path: Path = field(default_factory=lambda: BASE_DIR / "logs" / "trade_log.txt")

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_env_file()
        return cls(
            line_channel_access_token=require_env("LINE_CHANNEL_ACCESS_TOKEN"),
            line_channel_secret=require_env("LINE_CHANNEL_SECRET"),
            alpha_vantage_api_key=require_env("ALPHA_VANTAGE_API_KEY"),
            app_host=os.environ.get("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
            app_port=get_env_int("APP_PORT", 5000),
            state_ttl_sec=max(1, get_env_int("STATE_TTL_SEC", 300)),
            quote_cache_ttl_sec=max(1, get_env_int("QUOTE_CACHE_TTL_SEC", 60)),
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)


def configure_logging(log_file_path: Path) -> logging.Logger:
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    configured_path = getattr(logger, "_configured_log_path", None)
    resolved_path = str(log_file_path.resolve())
    if configured_path == resolved_path:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger._configured_log_path = resolved_path  # type: ignore[attr-defined]
    return logger
