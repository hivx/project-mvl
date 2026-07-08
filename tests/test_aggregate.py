"""Tests for aggregation: dedup, replacement handling, buyer filter, grouping."""
from datetime import date
from decimal import Decimal

from hdtool.aggregate import aggregate, normalize_rate
from hdtool.models import Invoice, TaxLine

MIYANO = "0301234567"


def make_inv(so_hd, mst_ban="0312345678", ky_hieu="C22TAA", mst_mua=MIYANO,
             chua_thue="1000000", thue="100000", tong="1100000",
             ngay=date(2026, 6, 15), trang_thai="goc", hd_bi_thay_the=None,
             tax_lines=None):
    if tax_lines is None:
        tax_lines = [TaxLine("10%", Decimal(chua_thue), Decimal(thue))]
    return Invoice(
        so_hd=so_hd, ky_hieu_mau_so="1", ky_hieu=ky_hieu, ngay_lap=ngay,
        mst_ban=mst_ban, ten_ban="Người bán", mst_mua=mst_mua, ten_mua="Người mua",
        don_vi_tien="VND", tien_chua_thue=Decimal(chua_thue), tien_thue=Decimal(thue),
        tong_thanh_toan=Decimal(tong), tax_lines=tax_lines,
        trang_thai=trang_thai, hd_bi_thay_the=hd_bi_thay_the,
    )


def test_normalize_rate_variants():
    assert normalize_rate("10%") == "10%"
    assert normalize_rate("10") == "10%"
    assert normalize_rate("kct") == "KCT"
    assert normalize_rate("KCT") == "KCT"
    assert normalize_rate("0%") == "0%"
    assert normalize_rate("KKKNT") == "KKKNT"


def test_dedup_keeps_single_and_latest():
    a = make_inv("123", tong="1100000", ngay=date(2026, 6, 15))
    b = make_inv("123", tong="9999999", ngay=date(2026, 6, 18))  # same key, later
    res = aggregate([a, b], buyer_msts={MIYANO})
    keys = [inv.dedup_key for inv in res.invoices]
    assert keys.count(("0312345678", "C22TAA", "123")) == 1
    kept = res.invoices[0]
    assert kept.tong_thanh_toan == Decimal("9999999")  # latest kept


def test_replacement_supersedes_original():
    original = make_inv("123", ngay=date(2026, 6, 15))
    replacement = make_inv("200", ngay=date(2026, 7, 2),
                           trang_thai="thay_the", hd_bi_thay_the="123",
                           chua_thue="1200000", thue="120000", tong="1320000")
    res = aggregate([original, replacement], buyer_msts={MIYANO})
    by_so = {inv.so_hd: inv for inv in res.invoices}
    assert by_so["123"].trang_thai == "nghi_huy"
    # only the replacement counts toward totals
    assert res.total_thanh_toan == Decimal("1320000")


def test_buyer_filter_excludes_other_buyer():
    mine = make_inv("123", mst_mua=MIYANO)
    other = make_inv("77", mst_mua="0400000000", ky_hieu="C22TBB")
    res = aggregate([mine, other], buyer_msts={MIYANO})
    kept_numbers = {inv.so_hd for inv in res.invoices}
    assert kept_numbers == {"123"}
    assert res.invoices[0].loai == "mua_vao"
    assert any(inv.so_hd == "77" for inv, _ in res.excluded)


def test_aggregate_labels_company_and_keeps_both_companies():
    a = make_inv("1", mst_mua="0109529507")
    b = make_inv("2", ky_hieu="C22TBB", mst_mua="0108186705")
    other = make_inv("3", ky_hieu="C22TCC", mst_mua="0400000000")  # not one of ours
    res = aggregate([a, b, other],
                    companies={"0109529507": "miyano", "0108186705": "medcons"})
    kept = {inv.so_hd: inv.cong_ty for inv in res.invoices}
    assert kept == {"1": "miyano", "2": "medcons"}
    assert all(inv.loai == "mua_vao" for inv in res.invoices)
    assert any(inv.so_hd == "3" for inv, _ in res.excluded)


def test_only_company_narrows_report_and_flags_other_company():
    a = make_inv("1", mst_mua="0109529507")                     # miyano
    b = make_inv("2", ky_hieu="C22TBB", mst_mua="0108186705")   # medcons
    other = make_inv("3", ky_hieu="C22TCC", mst_mua="0400000000")  # not ours
    res = aggregate([a, b, other],
                    companies={"0109529507": "miyano", "0108186705": "medcons"},
                    only_company="miyano")
    # report holds only the selected company
    assert {inv.so_hd for inv in res.invoices} == {"1"}
    assert res.invoices[0].cong_ty == "miyano"
    assert res.total_thanh_toan == Decimal("1100000")
    assert res.by_rate["10%"]["tien_chua_thue"] == Decimal("1000000")

    excluded = {inv.so_hd: inv for inv, _ in res.excluded}
    # medcons: valid mua_vao but not this report -> stays loai=mua_vao (=> cong_ty_khac)
    assert excluded["2"].loai == "mua_vao"
    assert excluded["2"].cong_ty == "medcons"
    # a genuine wrong-buyer stays excluded and is NOT mua_vao (=> sai_ben_mua)
    assert excluded["3"].loai != "mua_vao"


def test_only_company_none_keeps_both_companies():
    a = make_inv("1", mst_mua="0109529507")
    b = make_inv("2", ky_hieu="C22TBB", mst_mua="0108186705")
    res = aggregate([a, b],
                    companies={"0109529507": "miyano", "0108186705": "medcons"},
                    only_company=None)
    assert {inv.so_hd for inv in res.invoices} == {"1", "2"}


def test_buyer_filter_disabled_keeps_all():
    mine = make_inv("123", mst_mua=MIYANO)
    other = make_inv("77", mst_mua="0400000000", ky_hieu="C22TBB")
    res = aggregate([mine, other], buyer_msts=set())
    assert len(res.invoices) == 2
    assert all(inv.loai == "khong_ro" for inv in res.invoices)


def test_group_by_rate_sums_across_invoices():
    a = make_inv("1", tax_lines=[TaxLine("10%", Decimal("1000000"), Decimal("100000"))])
    b = make_inv("2", ky_hieu="C22TAA", tax_lines=[
        TaxLine("10%", Decimal("2000000"), Decimal("200000")),
        TaxLine("5%", Decimal("1000000"), Decimal("50000")),
        TaxLine("KCT", Decimal("500000"), Decimal("0")),
    ])
    res = aggregate([a, b], buyer_msts={MIYANO})
    assert res.by_rate["10%"]["tien_chua_thue"] == Decimal("3000000")
    assert res.by_rate["10%"]["tien_thue"] == Decimal("300000")
    assert res.by_rate["5%"]["tien_thue"] == Decimal("50000")
    assert res.by_rate["KCT"]["tien_chua_thue"] == Decimal("500000")


def test_superseded_invoice_excluded_from_rate_totals():
    original = make_inv("123", ngay=date(2026, 6, 15),
                        tax_lines=[TaxLine("10%", Decimal("1000000"), Decimal("100000"))])
    replacement = make_inv("200", ngay=date(2026, 7, 2), trang_thai="thay_the",
                           hd_bi_thay_the="123",
                           tax_lines=[TaxLine("10%", Decimal("1200000"), Decimal("120000"))])
    res = aggregate([original, replacement], buyer_msts={MIYANO})
    assert res.by_rate["10%"]["tien_chua_thue"] == Decimal("1200000")
