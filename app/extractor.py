"""Inti ekstraksi: dokumen -> prompt -> LLM -> baris data tervalidasi."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from .llm_client import LLMClient
from .readers import Document, chunk_text
from .schema import ExtractionSchema

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Anda adalah mesin ekstraksi data terstruktur.
Tugas: baca dokumen dan ambil SEMUA record yang sesuai skema kolom.
Aturan:
- Jawab HANYA dengan JSON objek: {"rows": [ {<kolom>: <nilai>, ...}, ... ]}
- Gunakan nama kolom PERSIS seperti di skema sebagai key.
- Jika nilai tidak ditemukan, isi null. Jangan mengarang data.
- number/integer: angka murni tanpa pemisah ribuan atau simbol mata uang.
- date: format YYYY-MM-DD.
- boolean: true/false.
- Jika tidak ada record sama sekali, kembalikan {"rows": []}."""


def _build_user_prompt(schema: ExtractionSchema, content: str, part: str) -> str:
    extra = f"\nInstruksi tambahan:\n{schema.instructions}\n" if schema.instructions else ""
    return (
        f"Skema kolom:\n{schema.describe_for_prompt()}\n{extra}\n"
        f"Dokumen{part}:\n<<<\n{content}\n>>>"
    )


# ---------- normalisasi tipe ----------

def _to_number(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return None
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "," in s and "." in s:
        # pemisah yang muncul terakhir = desimal (1.234.567,89 atau 1,234,567.89)
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        # hanya pemisah ribuan: 45.000 / 1.250.000 / 45,000
        s = s.replace(".", "").replace(",", "")
    else:
        s = s.replace(",", ".")  # 12,5 -> 12.5
    s = ("-" if neg else "") + s
    try:
        return float(s)
    except ValueError:
        return None


def _to_date(v: Any) -> date | str | None:
    if v in (None, ""):
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return s  # biarkan apa adanya bila tak terbaca


def _coerce(value: Any, col_type: str) -> Any:
    if col_type == "number":
        return _to_number(value)
    if col_type == "integer":
        n = _to_number(value)
        return int(round(n)) if n is not None else None
    if col_type == "date":
        return _to_date(value)
    if col_type == "boolean":
        if isinstance(value, bool) or value is None:
            return value
        return str(value).strip().lower() in {"true", "ya", "yes", "1", "y"}
    return None if value is None else str(value).strip()


def normalize_rows(rows: list[dict], schema: ExtractionSchema) -> list[dict]:
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        clean = {c.name: _coerce(r.get(c.name), c.type) for c in schema.columns}
        if all(v in (None, "") for v in clean.values()):
            continue
        out.append(clean)
    return out


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = tuple(str(v) for v in r.values())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ---------- orkestrasi ----------

class Extractor:
    def __init__(self, llm: LLMClient, schema: ExtractionSchema, chunk_chars: int = 12000):
        self.llm = llm
        self.schema = schema
        self.chunk_chars = chunk_chars

    def extract(self, doc: Document) -> list[dict]:
        rows: list[dict] = []

        if doc.is_image:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": _build_user_prompt(self.schema, "(lihat gambar terlampir)", "")},
                    *({"type": "image_url", "image_url": {"url": u}} for u in doc.images),
                ]},
            ]
            rows.extend(self._call(messages))
        else:
            chunks = chunk_text(doc.text, self.chunk_chars)
            for i, chunk in enumerate(chunks, 1):
                part = f" (bagian {i}/{len(chunks)})" if len(chunks) > 1 else ""
                log.info("%s: memproses bagian %d/%d", doc.path.name, i, len(chunks))
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(self.schema, chunk, part)},
                ]
                rows.extend(self._call(messages))

        rows = _dedupe(normalize_rows(rows, self.schema))
        for r in rows:
            r["_sumber"] = doc.path.name
        return rows

    def _call(self, messages: list[dict]) -> list[dict]:
        data = self.llm.chat_json(messages)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            rows = data.get("rows")
            if isinstance(rows, list):
                return rows
            # model mengembalikan satu record tanpa pembungkus
            if any(k in data for k in self.schema.column_names):
                return [data]
        log.warning("Format respons tidak dikenali, diabaikan: %s", str(data)[:200])
        return []
