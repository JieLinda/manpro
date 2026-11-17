"""Menulis hasil ekstraksi ke file .xlsx yang rapi."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .schema import ExtractionSchema

HEADER_FILL = PatternFill("solid", start_color="1F4E78")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

NUMBER_FMT = {
    "number": "#,##0.00;(#,##0.00);-",
    "integer": "#,##0;(#,##0);-",
    "date": "yyyy-mm-dd",
}


def write_xlsx(
    rows: list[dict],
    schema: ExtractionSchema,
    out_path: str | Path,
    errors: list[tuple[str, str]] | None = None,
) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = schema.sheet_name[:31]

    headers = ["No"] + schema.column_names + ["Sumber"]
    types = ["integer"] + [c.type for c in schema.columns] + ["string"]
    ws.append(headers)

    for i, r in enumerate(rows, 1):
        ws.append([i] + [r.get(c) for c in schema.column_names] + [r.get("_sumber")])

    # Gaya header
    for cell in ws[1]:
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Gaya isi + format angka/tanggal
    for row in ws.iter_rows(min_row=2):
        for cell, t in zip(row, types):
            cell.font, cell.border = BODY_FONT, BORDER
            if t in NUMBER_FMT and isinstance(cell.value, (int, float, date, datetime)):
                cell.number_format = NUMBER_FMT[t]
            cell.alignment = Alignment(vertical="top", wrap_text=(t == "string"))

    # Lebar kolom otomatis (dibatasi)
    for idx, h in enumerate(headers, 1):
        values = [h] + [str(ws.cell(row=r, column=idx).value or "") for r in range(2, min(ws.max_row, 200) + 1)]
        width = min(max(len(v) for v in values) + 2, 50)
        ws.column_dimensions[get_column_letter(idx)].width = max(width, 6)

    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions

    # Sheet log error per file (jika ada)
    if errors:
        es = wb.create_sheet("Log Error")
        es.append(["File", "Pesan"])
        for c in es[1]:
            c.fill, c.font = HEADER_FILL, HEADER_FONT
        for f, msg in errors:
            es.append([f, msg])
        es.column_dimensions["A"].width = 40
        es.column_dimensions["B"].width = 100

    wb.save(out)
    return out
