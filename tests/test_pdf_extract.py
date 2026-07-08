"""Tests for extracting invoice fields from PDF text (pdftotext output).

Uses synthetic text mimicking the Thái Sơn / einvoice.vn layout (the most common
VN e-invoice PDF) so no real invoice data is committed.
"""
from datetime import date
from decimal import Decimal

from hdtool.pdf_extract import parse_pdf_text

SAMPLE = """\
CÔNG TY TNHH BÁN HÀNG TEST
Địa chỉ (Add): 123 Đường Test, Hà Nội          Ký hiệu (Serial): 1C26TAB
Mã số thuế (Tax code): 0 3 1 2 3 4 5 6 7 8            Số (No.): 999999
                            HÓA ĐƠN GIÁ TRỊ GIA TĂNG
                Ngày(Date) 04 tháng(month) 06 năm(year) 2026
Mã cơ quan Thuế: M1-26-TEST0-00000001
Họ tên người mua hàng (Buyer): Công ty Mua Test
Tên đơn vị (Company): CÔNG TY TNHH MIYANO VIỆT NAM
Mã số thuế (Tax code): 0109529507          Hình thức thanh toán (Payment method): TM/CK
Tổng tiền chịu thuế suất 8% (Amount at 8% VAT)     8%    500.000       500.000    40.000    540.000
Tổng cộng tiền thanh toán (Total amount)                 500.000       500.000    40.000    540.000
Số tiền viết bằng chữ (Amount in words): Năm trăm bốn mươi nghìn đồng
"""


def test_parse_pdf_header_fields():
    inv = parse_pdf_text(SAMPLE)
    assert inv is not None
    assert inv.so_hd == "999999"
    assert inv.ky_hieu_mau_so == "1"
    assert inv.ky_hieu == "C26TAB"
    assert inv.ngay_lap == date(2026, 6, 4)
    assert inv.mst_ban == "0312345678"        # spaced digits collapsed
    assert inv.ten_ban == "CÔNG TY TNHH BÁN HÀNG TEST"
    assert inv.mst_mua == "0109529507"
    assert inv.ma_tra_cuu == "M1-26-TEST0-00000001"
    assert inv.hinh_thuc_tt == "TM/CK"


def test_parse_pdf_totals_and_source_flag():
    inv = parse_pdf_text(SAMPLE)
    assert inv.tien_chua_thue == Decimal("500000")
    assert inv.tien_thue == Decimal("40000")
    assert inv.tong_thanh_toan == Decimal("540000")
    assert inv.nguon == "PDF"          # flagged as PDF-sourced, not XML


def test_parse_pdf_tax_line():
    inv = parse_pdf_text(SAMPLE)
    assert len(inv.tax_lines) == 1
    tl = inv.tax_lines[0]
    assert tl.thue_suat == "8%"
    assert tl.tien_chua_thue == Decimal("500000")
    assert tl.tien_thue == Decimal("40000")


def test_parse_pdf_returns_none_when_unparseable():
    # A PDF with no invoice-total line -> we don't fabricate numbers.
    assert parse_pdf_text("Đây chỉ là văn bản linh tinh, không có tổng tiền.") is None
