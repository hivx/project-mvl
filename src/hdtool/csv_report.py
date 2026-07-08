"""Write the aggregated result to CSV (bảng kê hóa đơn đầu vào).

Excel packs several sheets in one file; CSV can't, so the main bảng kê goes to
``path`` and two sibling files sit next to it:
  * ``<base>-tong-hop.csv`` — tổng hợp theo thuế suất (như sheet Tổng hợp).
  * ``<base>-bo-qua.csv``   — các dòng bỏ qua + PDF cần nhập tay (không mất gì).
All files use UTF-8 with BOM (``utf-8-sig``) so Excel renders Vietnamese right.
Columns and group labels are shared with ``excel.py`` to stay in lock-step.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .aggregate import AggregateResult, normalize_rate
from .excel import BANG_KE_HEADERS, GROUP_LABELS, RATE_ORDER, SUMMARY_HEADERS
from .models import Invoice

SKIPPED_HEADERS = ["Định danh", "Nhóm", "Lý do"]


def _num(d):
    """Keep VND integers exact; leave non-integral Decimals as-is for the writer."""
    if isinstance(d, Decimal) and d == d.to_integral_value():
        return int(d)
    return d


def _rate_display(inv: Invoice) -> str:
    rates: list[str] = []
    for line in inv.tax_lines:
        r = normalize_rate(line.thue_suat)
        if r not in rates:
            rates.append(r)
    return ", ".join(rates)


def _bang_ke_rows(result: AggregateResult) -> list[list]:
    rows = [[
        inv.ngay_lap.isoformat() if inv.ngay_lap else "",
        inv.ky_hieu, inv.so_hd, inv.mst_ban, inv.ten_ban,
        _num(inv.tien_chua_thue), _rate_display(inv), _num(inv.tien_thue),
        _num(inv.tong_thanh_toan), inv.loai, inv.cong_ty, inv.trang_thai,
        inv.xml_path or "", inv.pdf_path or "", inv.source_message_id or "",
    ] for inv in result.invoices]
    total = ["TỔNG CỘNG", "", "", "", "", _num(result.total_chua_thue), "",
             _num(result.total_thue), _num(result.total_thanh_toan),
             "", "", "", "", "", ""]
    rows.append(total)
    return rows


def _summary_rows(result: AggregateResult) -> list[list]:
    ordered = [r for r in RATE_ORDER if r in result.by_rate]
    ordered += [r for r in result.by_rate if r not in RATE_ORDER]
    return [[r, _num(result.by_rate[r]["tien_chua_thue"]),
             _num(result.by_rate[r]["tien_thue"])] for r in ordered]


def _skipped_rows(skipped: list, manual_entry: list) -> list[list]:
    rows = [[ident, GROUP_LABELS.get(group, group), reason]
            for ident, group, reason in skipped]
    for p in manual_entry:
        rows.append([p, "Cần nhập tay", "Chỉ có PDF — cần nhập tay/OCR, không lấy số tự động"])
    return rows


def _write_csv(path: Path, header: list, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _sibling(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.stem}-{suffix}.csv")


def write_bang_ke_csv(result: AggregateResult, path, skipped: Optional[list] = None,
                      manual_entry: Optional[list] = None) -> Path:
    """Write bảng kê + sibling tong-hop/bo-qua CSVs. Returns the main .csv path."""
    path = Path(path)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")
    _write_csv(path, BANG_KE_HEADERS, _bang_ke_rows(result))
    _write_csv(_sibling(path, "tong-hop"), SUMMARY_HEADERS, _summary_rows(result))
    _write_csv(_sibling(path, "bo-qua"), SKIPPED_HEADERS,
               _skipped_rows(skipped or [], manual_entry or []))
    return path
