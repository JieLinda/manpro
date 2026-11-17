"""Klien LLM untuk endpoint yang kompatibel dengan OpenAI Chat Completions."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from .config import Settings

log = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_loose(raw: str) -> Any:
    """Ambil JSON dari jawaban LLM, termasuk bila dibungkus ```json ... ```."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = _FENCE_RE.search(raw)
    if m:
        return json.loads(m.group(1).strip())
    # fallback: potongan dari { pertama s/d } terakhir
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        return json.loads(raw[start : end + 1])
    raise ValueError("Respons LLM bukan JSON yang valid")


class LLMClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=0,  # retry ditangani sendiri di bawah
        )
        self._json_mode_supported = True

    def chat_json(self, messages: list[dict]) -> Any:
        last_err: Exception | None = None
        for attempt in range(1, self.s.max_retries + 1):
            try:
                kwargs: dict[str, Any] = dict(
                    model=self.s.model,
                    messages=messages,
                    temperature=self.s.temperature,
                )
                if self._json_mode_supported:
                    kwargs["response_format"] = {"type": "json_object"}

                resp = self.client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content or ""
                return parse_json_loose(content)

            except APIError as e:
                # Beberapa provider tidak mendukung response_format -> matikan & ulangi
                if self._json_mode_supported and "response_format" in str(e).lower():
                    log.warning("Endpoint tidak mendukung JSON mode, beralih ke mode biasa.")
                    self._json_mode_supported = False
                    continue
                last_err = e
                if not isinstance(e, (RateLimitError, APITimeoutError)) and getattr(e, "status_code", 500) < 500:
                    raise
            except (ValueError, json.JSONDecodeError) as e:
                last_err = e
                log.warning("Percobaan %d: JSON tidak valid (%s)", attempt, e)

            wait = 2 ** attempt
            log.info("Mencoba ulang dalam %ds (percobaan %d/%d)", wait, attempt, self.s.max_retries)
            time.sleep(wait)

        raise RuntimeError(f"Gagal memanggil LLM setelah {self.s.max_retries} percobaan: {last_err}")
