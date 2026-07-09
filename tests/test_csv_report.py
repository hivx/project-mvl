"""Tests for CSV export — bảng kê theo BK mua vào TT80 (+ bo-qua sibling)."""
import csv
from datetime import date
from decimal import Decimal

from hdtool.aggregate import aggregate
from hdtool.csv_report import write_bang_ke_csv
from hdtool.excel import BK_TT80_HEADERS
from hdtool.models import Invoice, TaxLine, ProductLine

MIYANO = "0301234567"


def _inv(so_hd="123", chua="1000000", thue="100000", tong="1100000", product_lines=None):
    return Invoice(
        so_hd=so_hd, ky_hieu_mau_so="1", ky_hieu="C22TAA", ngay_lap=date(2026, 6, 15),
        mst_ban="0312345678", ten_ban="Người bán", mst_mua=MIYANO, ten_mua="Người mua",
        don_vi_tien="VND", tien_chua_thue=Decimal(chua), tien_thue=Decimal(thue),
        tong_thanh_toan=Decimal(tong),
        tax_lines=[TaxLine("10%", Decimal(chua), Decimal(thue))],
        product_lines=product_lines or [],
    )


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def test_csv_uses_tt80_header_and_bom(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    ret = write_bang_ke_csv(res, out)
    assert ret == out and out.exists()
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")     # Excel-friendly BOM
    rows = _rows(out)
    assert rows[0] == BK_TT80_HEADERS
    # one declaration line for the single-rate invoice
    r1 = {BK_TT80_HEADERS[i]: v for i, v in enumerate(rows[1])}
    assert r1["Số"] == "123"
    assert r1["Mã số thuế người bán"] == "0312345678"
    assert r1["Thuế suất (%)"] == "10%"
    assert r1["Ngày, tháng, năm"] == "15/06/2026"          # dd/mm/yyyy


def test_csv_nguon_column_carries_pdf_ocr(tmp_path):
    """An OCR-sourced invoice surfaces nguon='PDF-OCR' in the Nguồn column so the
    accountant knows to đối soát — not collapsed to 'PDF' nor dropped (T32)."""
    inv = _inv()
    inv.nguon = "PDF-OCR"
    res = aggregate([inv], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    write_bang_ke_csv(res, out)
    rows = _rows(out)
    nguon_i = BK_TT80_HEADERS.index("Nguồn")
    assert rows[1][nguon_i] == "PDF-OCR"


def test_csv_expands_product_lines_with_negative_discount(tmp_path):
    pls = [
        ProductLine("1", "F", "Cước", "Chuyến", Decimal(1), Decimal("17278"), Decimal("17278"), "8%"),
        ProductLine("3", "D", "Chiết khấu", "Chuyến", Decimal(1), Decimal("3704"), Decimal("3704"), "8%"),
    ]
    res = aggregate([_inv(product_lines=pls)], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    write_bang_ke_csv(res, out)
    rows = _rows(out)
    ten_i = BK_TT80_HEADERS.index("Tên hàng hóa, dịch vụ")
    gia_i = BK_TT80_HEADERS.index("Giá trị HHDV mua vào chưa có thuế GTGT")
    by_name = {r[ten_i]: r for r in rows[1:]}
    assert set(by_name) == {"Cước", "Chiết khấu"}
    assert by_name["Chiết khấu"][gia_i] == "-3704"          # discount negative


def test_csv_writes_bo_qua_sibling(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    write_bang_ke_csv(res, out,
                      skipped=[("x.xml", "cong_ty_khac", "công ty medcons")],
                      manual_entry=["scan_only.pdf"])
    boqua = out.with_name("bang-ke-bo-qua.csv")
    assert boqua.exists()
    joined = " ".join(c for r in _rows(boqua) for c in r)
    assert "Công ty khác" in joined
    assert "scan_only.pdf" in joined


def test_write_bang_ke_csv_forces_csv_suffix(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    ret = write_bang_ke_csv(res, tmp_path / "bang-ke.xlsx")   # wrong suffix
    assert ret.suffix == ".csv"
    assert ret.exists()
