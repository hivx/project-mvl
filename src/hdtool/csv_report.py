"""Write the aggregated result to CSV as the 'BK mua vào TT80' declaration.

The main file (`<path>.csv`) holds the same columns as the Excel "BK mua vao
TT80" sheet — one row per product line. A sibling `<base>-bo-qua.csv` lists the
skipped rows + PDF-only invoices so nothing is lost. All UTF-8 with BOM
(`utf-8-sig`) so Excel shows Vietnamese right.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional

from .aggregate import AggregateResult
from .excel import BK_TT80_HEADERS, GROUP_LABELS, bk_tt80_rows

SKIPPED_HEADERS = ["Định danh", "Nhóm", "Lý do"]


def _fmt(v):
    """Render a cell for CSV: dates as dd/mm/yyyy, everything else as-is."""
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return v


def _write_csv(path: Path, header: list, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for r in rows:
            writer.writerow([_fmt(v) for v in r])
    return path


def _sibling(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.stem}-{suffix}.csv")


def _skipped_rows(skipped: list, manual_entry: list) -> list[list]:
    rows = [[ident, GROUP_LABELS.get(group, group), reason]
            for ident, group, reason in skipped]
    for p in manual_entry:
        rows.append([p, "Cần nhập tay", "Chỉ có PDF — cần nhập tay/OCR, không lấy số tự động"])
    return rows


def write_bang_ke_csv(result: AggregateResult, path, skipped: Optional[list] = None,
                      manual_entry: Optional[list] = None) -> Path:
    """Write the TT80 bảng kê to ``path`` + a sibling bo-qua CSV. Returns main path."""
    path = Path(path)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")
    _write_csv(path, BK_TT80_HEADERS, bk_tt80_rows(result))
    _write_csv(_sibling(path, "bo-qua"), SKIPPED_HEADERS,
               _skipped_rows(skipped or [], manual_entry or []))
    return path
