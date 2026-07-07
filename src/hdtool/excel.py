"""Write the aggregated result to an Excel workbook (bảng kê hóa đơn đầu vào)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .aggregate import AggregateResult, normalize_rate
from .models import Invoice

BANG_KE_HEADERS = [
    "Ngày HĐ", "Ký hiệu", "Số HĐ", "MST bán", "Tên bán",
    "Tiền chưa thuế", "Thuế suất", "Tiền thuế", "Tổng tiền",
    "Loại", "Trạng thái", "Link XML", "Link PDF", "Nguồn",
]

SUMMARY_HEADERS = ["Thuế suất", "Tiền chưa thuế", "Tiền thuế"]

# Order tax-rate groups the way a VAT declaration expects them.
RATE_ORDER = ["10%", "8%", "5%", "0%", "KCT", "KKKNT"]

_MONEY = "#,##0"
_HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
_TOTAL_FILL = PatternFill("solid", fgColor="FCE4D6")


def _num(d: Decimal):
    """openpyxl handles int/float; keep integers exact for VND."""
    if d == d.to_integral_value():
        return int(d)
    return float(d)


def _rate_display(inv: Invoice) -> str:
    rates = []
    for line in inv.tax_lines:
        r = normalize_rate(line.thue_suat)
        if r not in rates:
            rates.append(r)
    return ", ".join(rates)


def write_workbook(result: AggregateResult, path, skipped: Optional[list] = None,
                   manual_entry: Optional[list] = None) -> Path:
    path = Path(path)
    wb = Workbook()

    _write_bang_ke(wb, result)
    _write_summary(wb, result)
    _write_skipped(wb, result, skipped or [])
    _write_manual_entry(wb, manual_entry or [])

    wb.save(path)
    return path


def _style_header(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True)
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def _write_bang_ke(wb, result: AggregateResult):
    ws = wb.active
    ws.title = "Bảng kê"
    ws.append(BANG_KE_HEADERS)
    _style_header(ws, len(BANG_KE_HEADERS))

    money_cols = {6, 8, 9}  # 1-indexed: chưa thuế, thuế, tổng
    for inv in result.invoices:
        ws.append([
            inv.ngay_lap.isoformat() if inv.ngay_lap else "",
            inv.ky_hieu,
            inv.so_hd,
            inv.mst_ban,
            inv.ten_ban,
            _num(inv.tien_chua_thue),
            _rate_display(inv),
            _num(inv.tien_thue),
            _num(inv.tong_thanh_toan),
            inv.loai,
            inv.trang_thai,
            inv.xml_path or "",
            inv.pdf_path or "",
            inv.source_message_id or "",
        ])

    total_row = ws.max_row + 1
    ws.cell(row=total_row, column=1, value="TỔNG CỘNG").font = Font(bold=True)
    ws.cell(row=total_row, column=6, value=_num(result.total_chua_thue))
    ws.cell(row=total_row, column=8, value=_num(result.total_thue))
    ws.cell(row=total_row, column=9, value=_num(result.total_thanh_toan))
    for c in (1, 6, 8, 9):
        ws.cell(row=total_row, column=c).fill = _TOTAL_FILL
        ws.cell(row=total_row, column=c).font = Font(bold=True)

    for c in money_cols:
        for r in range(2, total_row + 1):
            ws.cell(row=r, column=c).number_format = _MONEY
    _autosize(ws, BANG_KE_HEADERS)


def _write_summary(wb, result: AggregateResult):
    ws = wb.create_sheet("Tổng hợp theo thuế suất")
    ws.append(SUMMARY_HEADERS)
    _style_header(ws, len(SUMMARY_HEADERS))

    ordered = [r for r in RATE_ORDER if r in result.by_rate]
    ordered += [r for r in result.by_rate if r not in RATE_ORDER]

    tot_chua = tot_thue = Decimal(0)
    for r in ordered:
        b = result.by_rate[r]
        ws.append([r, _num(b["tien_chua_thue"]), _num(b["tien_thue"])])
        tot_chua += b["tien_chua_thue"]
        tot_thue += b["tien_thue"]

    trow = ws.max_row + 1
    ws.cell(row=trow, column=1, value="TỔNG CỘNG").font = Font(bold=True)
    ws.cell(row=trow, column=2, value=_num(tot_chua)).font = Font(bold=True)
    ws.cell(row=trow, column=3, value=_num(tot_thue)).font = Font(bold=True)
    for c in (1, 2, 3):
        ws.cell(row=trow, column=c).fill = _TOTAL_FILL

    for c in (2, 3):
        for r in range(2, trow + 1):
            ws.cell(row=r, column=c).number_format = _MONEY
    _autosize(ws, SUMMARY_HEADERS)


def _write_skipped(wb, result: AggregateResult, skipped: list):
    """Invoices excluded (wrong buyer) + any external skipped items."""
    if not result.excluded and not skipped:
        return
    ws = wb.create_sheet("Bỏ qua")
    ws.append(["Số HĐ", "MST bán", "MST mua", "Lý do"])
    _style_header(ws, 4)
    for inv, reason in result.excluded:
        ws.append([inv.so_hd, inv.mst_ban, inv.mst_mua, reason])
    for item in skipped:
        # item: (identifier, reason)
        ident, reason = item if isinstance(item, tuple) else (str(item), "")
        ws.append([ident, "", "", reason])
    _autosize(ws, ["Số HĐ", "MST bán", "MST mua", "Lý do"])


def _write_manual_entry(wb, manual_entry: list):
    """PDF-only invoices that need manual entry / OCR (no XML to read numbers)."""
    if not manual_entry:
        return
    headers = ["File PDF (không có XML)", "Ghi chú"]
    ws = wb.create_sheet("Cần nhập tay")
    ws.append(headers)
    _style_header(ws, len(headers))
    for p in manual_entry:
        ws.append([p, "Chỉ có PDF — cần nhập tay/OCR, không lấy số tự động"])
    _autosize(ws, headers)


def _autosize(ws, headers):
    for i, h in enumerate(headers, start=1):
        width = max(len(str(h)) + 2, 12)
        ws.column_dimensions[get_column_letter(i)].width = min(width, 40)
