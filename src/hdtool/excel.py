"""Write the aggregated result to an Excel workbook matching the reference file
(docs/MVL ...xlsx): 4 product-line-level sheets, plus Bỏ qua / Cần nhập tay.

Sheets:
  * "Hoa don Chi tiet SP" — chi tiết HĐ kèm SP (header HĐ ở dòng đầu mỗi HĐ).
  * "BK mua vao TT80"     — bảng kê mua vào (Thông tư 80) để kê khai GTGT.
  * "DS hoa don"          — danh sách HĐ (1 dòng/HĐ).
  * "DS san pham"         — danh sách sản phẩm (1 dòng/SP).

Số liệu chỉ từ XML. Cột từ cổng tra cứu (KQ kiểm tra, link) để trống. Dòng chiết
khấu (TChat=3) hiển thị số âm; tiền thuế mỗi dòng = round(thành tiền × thuế suất).
Gộp ô (merge) của mẫu KHÔNG tái tạo — thay vào đó header HĐ chỉ ghi ở dòng đầu.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .aggregate import normalize_rate
from .models import Invoice

# --- Constants còn dùng bởi csv_report (định dạng CSV cũ) đến khi T25 chuyển đổi ---
BANG_KE_HEADERS = [
    "Ngày HĐ", "Ký hiệu", "Số HĐ", "MST bán", "Tên bán",
    "Tiền chưa thuế", "Thuế suất", "Tiền thuế", "Tổng tiền",
    "Loại", "Công ty", "Trạng thái", "Link XML", "Link PDF", "Nguồn",
]
SUMMARY_HEADERS = ["Thuế suất", "Tiền chưa thuế", "Tiền thuế"]
RATE_ORDER = ["10%", "8%", "5%", "0%", "KCT", "KKKNT"]

# --- Header 4 sheet giống mẫu ---
DETAIL_SP_HEADERS = [
    "STT", "MẪU SỐ", "KÝ HIỆU HÓA ĐƠN", "SỐ HÓA ĐƠN", "NGÀY LẬP", "MST NGƯỜI BÁN",
    "TÊN NGƯỜI BÁN", "ĐỊA CHỈ NGƯỜI BÁN", "MST NGƯỜI MUA", "TÊN NGƯỜI MUA",
    "ĐỊA CHỈ NGƯỜI MUA", "TỔNG TIỀN CHƯA THUẾ", "TỔNG TIỀN THUẾ",
    "TỔNG TIỀN CHIẾT KHẤU THƯƠNG MẠI", "TỔNG TIỀN PHÍ", "TỔNG TIỀN THANH TOÁN",
    "ĐƠN VỊ TIỀN TỆ", "TỶ GIÁ", "TRẠNG THÁI HÓA ĐƠN", "KẾT QUẢ KIỂM TRA HÓA ĐƠN",
    "HÓA ĐƠN LIÊN QUAN", "TÍNH CHẤT", "MÃ HÀNG", "TÊN HÀNG HÓA, DỊCH VỤ",
    "ĐƠN VỊ TÍNH", "SỐ LƯỢNG", "ĐƠN GIÁ", "THUẾ SUẤT", "THÀNH TIỀN", "TIỀN THUẾ",
]
BK_TT80_HEADERS = [
    "STT", "Mẫu số", "Ký hiệu", "Số", "Ngày, tháng, năm", "Tên người bán",
    "Mã số thuế người bán", "Tên hàng hóa, dịch vụ", "Đơn vị tính", "Số lượng",
    "Đơn giá", "Giá trị HHDV mua vào chưa có thuế GTGT", "Thuế suất (%)",
    "Tiền thuế GTGT", "Ghi chú",
]
DS_HOADON_HEADERS = [
    "LOẠI HÓA ĐƠN", "STT", "MẪU SỐ", "KÝ HIỆU", "SỐ", "NGÀY LẬP", "NGÀY KÝ",
    "MST NGƯỜI BÁN", "TÊN NGƯỜI BÁN", "ĐỊA CHỈ NGƯỜI BÁN", "MST NGƯỜI MUA",
    "TÊN NGƯỜI MUA", "ĐỊA CHỈ NGƯỜI MUA", "TỔNG TIỀN CHƯA THUẾ", "TỔNG TIỀN THUẾ",
    "TỔNG CKTM", "TỔNG PHÍ", "TỔNG THANH TOÁN", "TIỀN TỆ", "TỶ GIÁ", "TRẠNG THÁI",
    "KQ KIỂM TRA", "Hình thức thanh toán", "Link tra cứu", "Mã tra cứu", "Có XML",
    "Hóa đơn liên quan",
]
DS_SANPHAM_HEADERS = [
    "STT", "MẪU SỐ", "KÝ HIỆU HÓA ĐƠN", "SỐ HÓA ĐƠN", "NGÀY LẬP", "MST NGƯỜI BÁN",
    "TÊN NGƯỜI BÁN", "ĐỊA CHỈ NGƯỜI BÁN", "MST NGƯỜI MUA", "TÊN NGƯỜI MUA",
    "ĐỊA CHỈ NGƯỜI MUA", "ĐƠN VỊ TIỀN TỆ", "TỶ GIÁ", "TRẠNG THÁI HÓA ĐƠN",
    "KẾT QUẢ KIỂM TRA HÓA ĐƠN", "TÍNH CHẤT", "MÃ HÀNG", "LOẠI HÀNG HÓA ĐẶC TRƯNG",
    "TÊN HÀNG HÓA, DỊCH VỤ", "ĐƠN VỊ TÍNH", "SỐ LƯỢNG", "ĐƠN GIÁ", "THUẾ SUẤT",
    "THÀNH TIỀN", "TIỀN THUẾ", "THÔNG TIN KHÁC",
]

GROUP_LABELS = {
    "ngoai_ky": "Ngoài kỳ",
    "khong_ngay_lap": "Không có ngày lập",
    "sai_ben_mua": "Sai bên mua (CC nhầm)",
    "cong_ty_khac": "Công ty khác (không thuộc báo cáo này)",
    "trung_forward": "Trùng forward (vô hại)",
    "khong_phai_hoa_don": "Không phải hóa đơn (vd thông báo thuế)",
    "khong_doc_duoc": "KHÔNG đọc được — cần lấy tay",
}

_MONEY = "#,##0"
_DATE = "DD/MM/YYYY"
_HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")

_TINH_CHAT = {
    "1": "Hàng hóa, dịch vụ", "2": "Khuyến mại", "3": "Chiết khấu thương mại",
    "4": "Ghi chú/diễn giải", "5": "Hàng hoá đặc trưng",
}
_STATUS = {
    "goc": "Hóa đơn mới", "thay_the": "Hóa đơn thay thế",
    "dieu_chinh": "Hóa đơn điều chỉnh", "nghi_huy": "Hóa đơn bị thay thế",
}


@dataclass
class _Line:
    """A resolved display line (product line, or synthesized from tax rates)."""
    tinh_chat: str
    ma_hang: str
    ten_hang: str
    dvt: str
    so_luong: Decimal
    don_gia: Decimal
    thue_suat: str
    thanh_tien: Decimal   # signed (negative for discount)
    tien_thue: Decimal    # signed


def _num(d):
    """openpyxl-friendly number: exact int for integral VND, else float."""
    if isinstance(d, Decimal):
        return int(d) if d == d.to_integral_value() else float(d)
    return d


def _tinh_chat_label(code: str) -> str:
    return _TINH_CHAT.get((code or "").strip(), code or "")


def _invoice_type(ky_hieu: str) -> str:
    """Ký hiệu dạng [C/K][YY][loại]… — ký tự thứ 4 = 'M' -> hóa đơn máy tính tiền."""
    return ("HĐ từ máy tính tiền"
            if len(ky_hieu) >= 4 and ky_hieu[3].upper() == "M" else "HĐ điện tử")


def _status_text(inv: Invoice) -> str:
    return _STATUS.get(inv.trang_thai, "Hóa đơn mới")


def _rate_tax(thanh_tien: Decimal, thue_suat: str) -> Decimal:
    """Tiền thuế 1 dòng = round(thành tiền × thuế suất); KCT/KKKNT/0% -> 0."""
    r = normalize_rate(thue_suat)
    if r.endswith("%"):
        pct = Decimal(r[:-1])
        return (thanh_tien * pct / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return Decimal(0)


def _display_lines(inv: Invoice) -> list[_Line]:
    """Resolve an invoice to display lines.

    Prefer real product lines (DSHHDVu); else synthesize one line per tax-rate
    bucket (LTSuat); else a single line from the invoice totals. Discount lines
    (TChat=3) get a negative amount and negative computed tax.
    """
    if inv.product_lines:
        out = []
        for p in inv.product_lines:
            sign = -1 if (p.tinh_chat or "").strip() == "3" else 1
            amount = p.thanh_tien * sign
            out.append(_Line(
                tinh_chat=p.tinh_chat, ma_hang=p.ma_hang, ten_hang=p.ten_hang,
                dvt=p.dvt, so_luong=p.so_luong, don_gia=p.don_gia,
                thue_suat=p.thue_suat, thanh_tien=amount,
                tien_thue=_rate_tax(amount, p.thue_suat),
            ))
        return out
    if inv.tax_lines:
        return [_Line("", "", "", "", Decimal(1), Decimal(0), tl.thue_suat,
                      tl.tien_chua_thue, tl.tien_thue) for tl in inv.tax_lines]
    return [_Line("", "", "", "", Decimal(1), Decimal(0), "",
                  inv.tien_chua_thue, inv.tien_thue)]


def bk_tt80_rows(result) -> list[list]:
    """Rows of the 'BK mua vao TT80' declaration (1 per display line), aligned to
    BK_TT80_HEADERS. Shared by the Excel writer and the CSV export so both match.
    Dates stay as date objects; the caller formats them per output type.
    """
    rows: list[list] = []
    stt = 1
    for inv in result.invoices:
        for ln in _display_lines(inv):
            rows.append([
                stt, inv.ky_hieu_mau_so, inv.ky_hieu, inv.so_hd, inv.ngay_lap,
                inv.ten_ban, inv.mst_ban, ln.ten_hang, ln.dvt, _num(ln.so_luong),
                _num(ln.don_gia), _num(ln.thanh_tien), ln.thue_suat,
                _num(ln.tien_thue), "",
            ])
            stt += 1
    return rows


def _period_line(from_date: Optional[date], to_date: Optional[date]) -> str:
    if from_date and to_date:
        return f"Từ ngày {from_date.strftime('%d/%m/%Y')} đến ngày {to_date.strftime('%d/%m/%Y')}"
    return ""


def write_workbook(result, path, skipped: Optional[list] = None,
                   manual_entry: Optional[list] = None,
                   from_date: Optional[date] = None,
                   to_date: Optional[date] = None) -> Path:
    path = Path(path)
    wb = Workbook()
    period = _period_line(from_date, to_date)

    _write_detail_sp(wb.active, result, period)
    _write_bk_tt80(wb.create_sheet("BK mua vao TT80"), result, period)
    _write_ds_hoadon(wb.create_sheet("DS hoa don"), result, period)
    _write_ds_sanpham(wb.create_sheet("DS san pham"), result, period)
    _write_skipped(wb, skipped or [])
    _write_manual_retrieval(wb, skipped or [])
    _write_manual_entry(wb, manual_entry or [])

    wb.save(path)
    return path


def _titled(ws, title: str, period: str, headers: list, header_row: int):
    ws.cell(row=header_row - 2, column=1, value=title).font = Font(bold=True)
    if period:
        ws.cell(row=header_row - 1, column=1, value=period)
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=c, value=h)
        cell.font = Font(bold=True)
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def _put(ws, row: int, col: int, value, fmt: Optional[str] = None):
    if value is None:
        return
    cell = ws.cell(row=row, column=col, value=value)
    if fmt:
        cell.number_format = fmt


def _autosize(ws, headers: list):
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(len(str(h)) + 2, 12), 45)


def _write_detail_sp(ws, result, period: str):
    ws.title = "Hoa don Chi tiet SP"
    _titled(ws, "DANH SÁCH CHI TIẾT HÓA ĐƠN (kèm sản phẩm)", period, DETAIL_SP_HEADERS, 4)
    r = 5
    for i, inv in enumerate(result.invoices, 1):
        for j, ln in enumerate(_display_lines(inv)):
            if j == 0:   # invoice header only on the first product line
                _put(ws, r, 1, i)
                _put(ws, r, 2, inv.ky_hieu_mau_so)
                _put(ws, r, 3, inv.ky_hieu)
                _put(ws, r, 4, inv.so_hd)
                _put(ws, r, 5, inv.ngay_lap, _DATE)
                _put(ws, r, 6, inv.mst_ban)
                _put(ws, r, 7, inv.ten_ban)
                _put(ws, r, 8, inv.dia_chi_ban)
                _put(ws, r, 9, inv.mst_mua)
                _put(ws, r, 10, inv.ten_mua)
                _put(ws, r, 11, inv.dia_chi_mua)
                _put(ws, r, 12, _num(inv.tien_chua_thue), _MONEY)
                _put(ws, r, 13, _num(inv.tien_thue), _MONEY)
                _put(ws, r, 14, _num(inv.tong_cktm), _MONEY)
                _put(ws, r, 15, _num(inv.tong_phi), _MONEY)
                _put(ws, r, 16, _num(inv.tong_thanh_toan), _MONEY)
                _put(ws, r, 17, inv.don_vi_tien)
                _put(ws, r, 18, _num(inv.ty_gia))
                _put(ws, r, 19, _status_text(inv))
                _put(ws, r, 21, inv.hd_bi_thay_the or None)
            _put(ws, r, 22, _tinh_chat_label(ln.tinh_chat))
            _put(ws, r, 23, ln.ma_hang or None)
            _put(ws, r, 24, ln.ten_hang or None)
            _put(ws, r, 25, ln.dvt or None)
            _put(ws, r, 26, _num(ln.so_luong))
            _put(ws, r, 27, _num(ln.don_gia), _MONEY)
            _put(ws, r, 28, ln.thue_suat or None)
            _put(ws, r, 29, _num(ln.thanh_tien), _MONEY)
            _put(ws, r, 30, _num(ln.tien_thue), _MONEY)
            r += 1
    _autosize(ws, DETAIL_SP_HEADERS)


def _write_bk_tt80(ws, result, period: str):
    _titled(ws, "BẢNG KÊ HOÁ ĐƠN, CHỨNG TỪ HÀNG HOÁ, DỊCH VỤ MUA VÀO", period,
            BK_TT80_HEADERS, 4)
    money_cols = {11, 12, 14}
    for r, row in enumerate(bk_tt80_rows(result), start=5):
        for c, v in enumerate(row, 1):
            fmt = _DATE if c == 5 else (_MONEY if c in money_cols else None)
            _put(ws, r, c, v if v != "" else None, fmt)
    _autosize(ws, BK_TT80_HEADERS)


def _write_ds_hoadon(ws, result, period: str):
    _titled(ws, "DANH SÁCH HÓA ĐƠN", period, DS_HOADON_HEADERS, 3)
    r = 4
    for i, inv in enumerate(result.invoices, 1):
        _put(ws, r, 1, _invoice_type(inv.ky_hieu))
        _put(ws, r, 2, i)
        _put(ws, r, 3, inv.ky_hieu_mau_so)
        _put(ws, r, 4, inv.ky_hieu)
        _put(ws, r, 5, inv.so_hd)
        _put(ws, r, 6, inv.ngay_lap, _DATE)
        _put(ws, r, 7, inv.ngay_ky or inv.ngay_lap, _DATE)
        _put(ws, r, 8, inv.mst_ban)
        _put(ws, r, 9, inv.ten_ban)
        _put(ws, r, 10, inv.dia_chi_ban)
        _put(ws, r, 11, inv.mst_mua)
        _put(ws, r, 12, inv.ten_mua)
        _put(ws, r, 13, inv.dia_chi_mua)
        _put(ws, r, 14, _num(inv.tien_chua_thue), _MONEY)
        _put(ws, r, 15, _num(inv.tien_thue), _MONEY)
        _put(ws, r, 16, _num(inv.tong_cktm), _MONEY)
        _put(ws, r, 17, _num(inv.tong_phi), _MONEY)
        _put(ws, r, 18, _num(inv.tong_thanh_toan), _MONEY)
        _put(ws, r, 19, inv.don_vi_tien)
        _put(ws, r, 20, _num(inv.ty_gia))
        _put(ws, r, 21, _status_text(inv))
        _put(ws, r, 23, inv.hinh_thuc_tt or None)
        _put(ws, r, 25, inv.ma_tra_cuu or None)
        _put(ws, r, 26, "x")               # Có XML (report chỉ gồm HĐ đọc từ XML)
        _put(ws, r, 27, inv.hd_bi_thay_the or None)
        r += 1
    _autosize(ws, DS_HOADON_HEADERS)


def _write_ds_sanpham(ws, result, period: str):
    _titled(ws, "DANH SÁCH SẢN PHẨM", period, DS_SANPHAM_HEADERS, 4)
    r, stt = 5, 1
    for inv in result.invoices:
        for ln in _display_lines(inv):
            _put(ws, r, 1, stt)
            _put(ws, r, 2, inv.ky_hieu_mau_so)
            _put(ws, r, 3, inv.ky_hieu)
            _put(ws, r, 4, inv.so_hd)
            _put(ws, r, 5, inv.ngay_lap, _DATE)
            _put(ws, r, 6, inv.mst_ban)
            _put(ws, r, 7, inv.ten_ban)
            _put(ws, r, 8, inv.dia_chi_ban)
            _put(ws, r, 9, inv.mst_mua)
            _put(ws, r, 10, inv.ten_mua)
            _put(ws, r, 11, inv.dia_chi_mua)
            _put(ws, r, 12, inv.don_vi_tien)
            _put(ws, r, 13, _num(inv.ty_gia))
            _put(ws, r, 14, _status_text(inv))
            _put(ws, r, 16, _tinh_chat_label(ln.tinh_chat))
            _put(ws, r, 17, ln.ma_hang or None)
            _put(ws, r, 19, ln.ten_hang or None)
            _put(ws, r, 20, ln.dvt or None)
            _put(ws, r, 21, _num(ln.so_luong))
            _put(ws, r, 22, _num(ln.don_gia), _MONEY)
            _put(ws, r, 23, ln.thue_suat or None)
            _put(ws, r, 24, _num(ln.thanh_tien), _MONEY)
            _put(ws, r, 25, _num(ln.tien_thue), _MONEY)
            r += 1
            stt += 1
    _autosize(ws, DS_SANPHAM_HEADERS)


def _write_skipped(wb, skipped: list):
    if not skipped:
        return
    headers = ["Định danh", "Nhóm", "Lý do"]
    ws = wb.create_sheet("Bỏ qua")
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True)
        cell.fill = _HEADER_FILL
    for ident, group, reason in skipped:
        ws.append([ident, GROUP_LABELS.get(group, group), reason])
    _autosize(ws, headers)


def _write_manual_retrieval(wb, skipped: list):
    gaps = [(ident, reason) for ident, group, reason in skipped
            if group == "khong_doc_duoc"]
    if not gaps:
        return
    headers = ["Hóa đơn (không đọc được)", "Ghi chú"]
    ws = wb.create_sheet("Cần lấy tay")
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h).font = Font(bold=True)
    for ident, reason in gaps:
        ws.append([ident, reason])
    _autosize(ws, headers)


def _write_manual_entry(wb, manual_entry: list):
    if not manual_entry:
        return
    headers = ["File PDF (không có XML)", "Ghi chú"]
    ws = wb.create_sheet("Cần nhập tay")
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h).font = Font(bold=True)
    for p in manual_entry:
        ws.append([p, "Chỉ có PDF — cần nhập tay/OCR, không lấy số tự động"])
    _autosize(ws, headers)
