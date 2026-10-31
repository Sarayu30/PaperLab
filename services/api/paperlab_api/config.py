"""Server-only configuration. Never return environment values to the browser."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


def load_settings() -> None:
    load_dotenv(ROOT / ".env", override=False, encoding="utf-8-sig")


def groq_settings() -> tuple[str, str]:
    load_settings()
    return os.getenv("GROQ_API_KEY", "").strip(), os.getenv(
        "GROQ_MODEL", "openai/gpt-oss-120b"
    ).strip()
