"""Tests for Excel output (bảng kê + tổng hợp theo thuế suất)."""
from datetime import date
from decimal import Decimal

import openpyxl

from hdtool.aggregate import aggregate
from hdtool.excel import write_workbook, BANG_KE_HEADERS
from hdtool.models import Invoice, TaxLine

MIYANO = "0301234567"


def make_inv(so_hd, ky_hieu="C22TAA", tax_lines=None, chua="1000000",
             thue="100000", tong="1100000", cong_ty=""):
    if tax_lines is None:
        tax_lines = [TaxLine("10%", Decimal(chua), Decimal(thue))]
    return Invoice(
        so_hd=so_hd, ky_hieu_mau_so="1", ky_hieu=ky_hieu, ngay_lap=date(2026, 6, 15),
        mst_ban="0312345678", ten_ban="CÔNG TY ABC", mst_mua=MIYANO, ten_mua="MIYANO",
        don_vi_tien="VND", tien_chua_thue=Decimal(chua), tien_thue=Decimal(thue),
        tong_thanh_toan=Decimal(tong), tax_lines=tax_lines, cong_ty=cong_ty,
    )


def test_writes_two_sheets(tmp_path):
    res = aggregate([make_inv("123")], buyer_msts={MIYANO})
    out = tmp_path / "report.xlsx"
    write_workbook(res, out)
    wb = openpyxl.load_workbook(out)
    assert "Bảng kê" in wb.sheetnames
    assert "Tổng hợp theo thuế suất" in wb.sheetnames


def test_bang_ke_header_and_row(tmp_path):
    res = aggregate([make_inv("123", tong="1100000")], buyer_msts={MIYANO})
    out = tmp_path / "report.xlsx"
    write_workbook(res, out)
    ws = openpyxl.load_workbook(out)["Bảng kê"]
    header = [c.value for c in ws[1]]
    assert header == BANG_KE_HEADERS
    row2 = {header[i]: c.value for i, c in enumerate(ws[2])}
    assert row2["Số HĐ"] == "123"
    assert row2["MST bán"] == "0312345678"
    assert Decimal(str(row2["Tổng tiền"])) == Decimal("1100000")
    assert row2["Loại"] == "mua_vao"


def test_bang_ke_has_company_column(tmp_path):
    res = aggregate([make_inv("123")], companies={MIYANO: "miyano"})
    out = tmp_path / "report.xlsx"
    write_workbook(res, out)
    ws = openpyxl.load_workbook(out)["Bảng kê"]
    header = [c.value for c in ws[1]]
    assert "Công ty" in header
    row2 = {header[i]: c.value for i, c in enumerate(ws[2])}
    assert row2["Công ty"] == "miyano"


def test_totals_row_present(tmp_path):
    res = aggregate([make_inv("123", tong="1100000"),
                     make_inv("124", tong="2200000")], buyer_msts={MIYANO})
    out = tmp_path / "report.xlsx"
    write_workbook(res, out)
    ws = openpyxl.load_workbook(out)["Bảng kê"]
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "TỔNG CỘNG" in labels
    tot_row = labels.index("TỔNG CỘNG") + 1
    header = [c.value for c in ws[1]]
    tong_col = header.index("Tổng tiền") + 1
    assert Decimal(str(ws.cell(row=tot_row, column=tong_col).value)) == Decimal("3300000")


def test_summary_notes_unallocated_difference(tmp_path):
    # TgTCThue (26038) exceeds the rate-line sum (24538) by 1500 -> summary notes it
    inv = make_inv("1", tax_lines=[TaxLine("8%", Decimal("24538"), Decimal("1962"))],
                   chua="26038", thue="1962", tong="28000")
    res = aggregate([inv], buyer_msts={MIYANO})
    out = tmp_path / "r.xlsx"
    write_workbook(res, out)
    ws = openpyxl.load_workbook(out)["Tổng hợp theo thuế suất"]
    text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "1500" in text or "1,500" in text          # the 1500 difference is shown
    assert "hóa đơn" in text.lower() or "chênh" in text.lower() or "bảng kê" in text.lower()


def test_summary_no_note_when_reconciled(tmp_path):
    inv = make_inv("1", tax_lines=[TaxLine("10%", Decimal("1000000"), Decimal("100000"))],
                   chua="1000000", thue="100000", tong="1100000")
    res = aggregate([inv], buyer_msts={MIYANO})
    out = tmp_path / "r.xlsx"
    write_workbook(res, out)
    ws = openpyxl.load_workbook(out)["Tổng hợp theo thuế suất"]
    text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "chênh" not in text.lower()


def test_summary_sheet_groups_rates(tmp_path):
    inv = make_inv("9", tax_lines=[
        TaxLine("10%", Decimal("2000000"), Decimal("200000")),
        TaxLine("5%", Decimal("1000000"), Decimal("50000")),
    ], chua="3000000", thue="250000", tong="3250000")
    res = aggregate([inv], buyer_msts={MIYANO})
    out = tmp_path / "report.xlsx"
    write_workbook(res, out)
    ws = openpyxl.load_workbook(out)["Tổng hợp theo thuế suất"]
    rows = {ws.cell(row=r, column=1).value: r for r in range(1, ws.max_row + 1)}
    assert "10%" in rows and "5%" in rows
    header = [c.value for c in ws[1]]
    thue_col = header.index("Tiền thuế") + 1
    assert Decimal(str(ws.cell(row=rows["10%"], column=thue_col).value)) == Decimal("200000")
