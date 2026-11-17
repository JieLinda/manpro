"""CLI: python -m app.main -s schemas/contoh_invoice.yaml -i input/ -o output/hasil.xlsx"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import ConfigError, Settings
from .extractor import Extractor
from .llm_client import LLMClient
from .readers import SUPPORTED_EXT, read_document
from .schema import ExtractionSchema
from .xlsx_writer import write_xlsx


def collect_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_EXT)
        elif p.is_file():
            files.append(p)
        else:
            logging.warning("Tidak ditemukan: %s", item)
    return files


def run(schema_path: str, inputs: list[str], output: str | None) -> Path:
    settings = Settings.from_env()
    schema = ExtractionSchema.load(schema_path)
    extractor = Extractor(LLMClient(settings), schema, settings.chunk_chars)

    files = collect_files(inputs)
    if not files:
        raise SystemExit("Tidak ada file yang bisa diproses.")

    all_rows, errors = [], []
    for f in files:
        try:
            doc = read_document(f)
            rows = extractor.extract(doc)
            logging.info("%s -> %d baris", f.name, len(rows))
            all_rows.extend(rows)
        except Exception as e:  # satu file gagal tidak menghentikan batch
            logging.error("%s gagal: %s", f.name, e)
            errors.append((f.name, str(e)))

    out = output or f"output/hasil_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    path = write_xlsx(all_rows, schema, out, errors)
    logging.info("Selesai: %d baris dari %d file -> %s", len(all_rows), len(files), path)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ekstraksi data dokumen ke XLSX via LLM")
    ap.add_argument("-s", "--schema", required=True, help="File skema (.yaml/.json)")
    ap.add_argument("-i", "--input", required=True, nargs="+", help="File atau folder input")
    ap.add_argument("-o", "--output", help="Path file .xlsx keluaran")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        run(args.schema, args.input, args.output)
    except ConfigError as e:
        logging.error(str(e))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
