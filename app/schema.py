"""Definisi skema ekstraksi: kolom apa saja yang ingin diambil dari dokumen."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

ColumnType = Literal["string", "number", "integer", "date", "boolean"]


class Column(BaseModel):
    name: str = Field(..., description="Nama kolom di Excel (juga key JSON)")
    type: ColumnType = "string"
    description: str = ""
    required: bool = False


class ExtractionSchema(BaseModel):
    sheet_name: str = "Data"
    instructions: str = Field(
        "", description="Instruksi tambahan untuk LLM (konteks domain, aturan khusus)"
    )
    columns: list[Column]

    @classmethod
    def load(cls, path: str | Path) -> "ExtractionSchema":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        data = yaml.safe_load(text) if p.suffix.lower() in {".yml", ".yaml"} else json.loads(text)
        return cls.model_validate(data)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def describe_for_prompt(self) -> str:
        lines = []
        for c in self.columns:
            req = " (wajib)" if c.required else ""
            desc = f" — {c.description}" if c.description else ""
            lines.append(f'- "{c.name}": {c.type}{req}{desc}')
        return "\n".join(lines)
