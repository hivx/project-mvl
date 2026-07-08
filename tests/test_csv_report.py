"""Tests for CSV export of the bảng kê (+ sibling tong-hop / bo-qua files)."""
import csv
from datetime import date
from decimal import Decimal

from hdtool.aggregate import aggregate
from hdtool.csv_report import write_bang_ke_csv
from hdtool.models import Invoice, TaxLine

MIYANO = "0301234567"


def _inv(so_hd="123", chua="1000000", thue="100000", tong="1100000"):
    return Invoice(
        so_hd=so_hd, ky_hieu_mau_so="1", ky_hieu="C22TAA", ngay_lap=date(2026, 6, 15),
        mst_ban="0312345678", ten_ban="Người bán", mst_mua=MIYANO, ten_mua="Người mua",
        don_vi_tien="VND", tien_chua_thue=Decimal(chua), tien_thue=Decimal(thue),
        tong_thanh_toan=Decimal(tong),
        tax_lines=[TaxLine("10%", Decimal(chua), Decimal(thue))],
    )


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def test_write_bang_ke_csv_creates_main_and_siblings(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    ret = write_bang_ke_csv(res, out,
                            skipped=[("x.xml", "cong_ty_khac", "công ty medcons")],
                            manual_entry=["scan_only.pdf"])
    assert ret == out and out.exists()
    tong = out.with_name("bang-ke-tong-hop.csv")
    boqua = out.with_name("bang-ke-bo-qua.csv")
    assert tong.exists() and boqua.exists()


def test_bang_ke_csv_is_utf8_bom_with_header_and_total(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    write_bang_ke_csv(res, out)
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")  # Excel-friendly BOM
    rows = _rows(out)
    assert rows[0][:3] == ["Ngày HĐ", "Ký hiệu", "Số HĐ"]
    assert any(len(r) > 2 and r[2] == "123" for r in rows)   # invoice row (Số HĐ col)
    assert any(r and r[0] == "TỔNG CỘNG" for r in rows)      # totals row


def test_csv_siblings_have_summary_and_skipped(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    out = tmp_path / "bang-ke.csv"
    write_bang_ke_csv(res, out,
                      skipped=[("x.xml", "cong_ty_khac", "công ty medcons")],
                      manual_entry=["scan_only.pdf"])
    tong = _rows(out.with_name("bang-ke-tong-hop.csv"))
    assert any(r and r[0] == "10%" for r in tong)
    boqua = " ".join(c for r in _rows(out.with_name("bang-ke-bo-qua.csv")) for c in r)
    assert "Công ty khác" in boqua       # cong_ty_khac label
    assert "scan_only.pdf" in boqua       # manual-entry PDFs not lost


def test_write_bang_ke_csv_forces_csv_suffix(tmp_path):
    res = aggregate([_inv()], buyer_msts={MIYANO})
    ret = write_bang_ke_csv(res, tmp_path / "bang-ke.xlsx")   # wrong suffix
    assert ret.suffix == ".csv"
    assert ret.exists()
