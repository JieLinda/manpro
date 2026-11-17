"""Memuat konfigurasi dari .env / environment variable."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    chunk_chars: int = 12000
    timeout: float = 120.0
    max_retries: int = 3
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "Settings":
        base_url = os.getenv("LLM_BASE_URL", "").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()

        missing = [k for k, v in {
            "LLM_BASE_URL": base_url,
            "LLM_API_KEY": api_key,
            "LLM_MODEL": model,
        }.items() if not v]
        if missing:
            raise ConfigError(
                "Variabel env belum diisi: " + ", ".join(missing)
                + ". Salin .env.example menjadi .env lalu lengkapi."
            )

        return cls(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            model=model,
            chunk_chars=int(os.getenv("LLM_CHUNK_CHARS", "12000")),
            timeout=float(os.getenv("LLM_TIMEOUT", "120")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        )
