"""Membaca berbagai format dokumen menjadi teks (atau gambar untuk model vision)."""
from __future__ import annotations

import base64
import csv
import io
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".json", ".xml", ".html", ".htm", ".log"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUPPORTED_EXT = TEXT_EXT | IMAGE_EXT | {".pdf", ".docx", ".csv", ".xlsx"}


@dataclass
class Document:
    path: Path
    text: str = ""
    images: list[str] = field(default_factory=list)  # data URL base64

    @property
    def is_image(self) -> bool:
        return bool(self.images) and not self.text.strip()


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        txt = page.extract_text() or ""
        pages.append(f"--- Halaman {i} ---\n{txt.strip()}")
    return "\n\n".join(pages)


def _read_docx(path: Path) -> str:
    import docx

    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for t_idx, table in enumerate(d.tables, 1):
        parts.append(f"--- Tabel {t_idx} ---")
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _read_csv(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.reader(f))
    return "\n".join(" | ".join(r) for r in rows)


def _read_xlsx(path: Path) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(str(path), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"--- Sheet: {ws.title} ---")
        for row in ws.iter_rows(values_only=True):
            if any(v is not None for v in row):
                out.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(out)


def _image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def read_document(path: str | Path) -> Document:
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise ValueError(f"Format tidak didukung: {ext} ({p.name})")

    if ext == ".pdf":
        text = _read_pdf(p)
        if len(text.replace("--- Halaman", "").strip()) < 20:
            # Kemungkinan PDF hasil scan: tidak ada teks yang bisa diambil
            raise ValueError(
                f"{p.name}: tidak ada teks terbaca (kemungkinan hasil scan). "
                "Konversi ke gambar per halaman lalu proses sebagai gambar, atau jalankan OCR dahulu."
            )
        return Document(p, text=text)
    if ext == ".docx":
        return Document(p, text=_read_docx(p))
    if ext == ".csv":
        return Document(p, text=_read_csv(p))
    if ext == ".xlsx":
        return Document(p, text=_read_xlsx(p))
    if ext in IMAGE_EXT:
        return Document(p, images=[_image_to_data_url(p)])
    return Document(p, text=p.read_text(encoding="utf-8", errors="replace"))


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Potong teks per paragraf supaya tidak melebihi batas konteks."""
    if len(text) <= max_chars:
        return [text]
    chunks, buf = [], io.StringIO()
    for para in text.split("\n"):
        if buf.tell() + len(para) + 1 > max_chars and buf.tell() > 0:
            chunks.append(buf.getvalue())
            buf = io.StringIO()
        while len(para) > max_chars:  # paragraf sangat panjang
            chunks.append(para[:max_chars])
            para = para[max_chars:]
        buf.write(para + "\n")
    if buf.tell():
        chunks.append(buf.getvalue())
    return chunks
