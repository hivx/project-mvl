"""Tests for parsing Vietnamese e-invoice XML (TCT standard)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from hdtool.parse_xml import parse_invoice_xml, InvoiceParseError

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_bytes()


def test_parses_basic_10pct_invoice_fields():
    inv = parse_invoice_xml(load("inv_10pct.xml"))
    assert inv.so_hd == "123"
    assert inv.ky_hieu_mau_so == "1"
    assert inv.ky_hieu == "C22TAA"
    assert inv.ngay_lap == date(2026, 6, 15)
    assert inv.mst_ban == "0312345678"
    assert inv.ten_ban == "CÔNG TY TNHH THIẾT BỊ ABC"
    assert inv.mst_mua == "0301234567"
    assert inv.don_vi_tien == "VND"


def test_parses_totals_as_decimal():
    inv = parse_invoice_xml(load("inv_10pct.xml"))
    assert inv.tien_chua_thue == Decimal("1000000")
    assert inv.tien_thue == Decimal("100000")
    assert inv.tong_thanh_toan == Decimal("1100000")


def test_parses_single_tax_line():
    inv = parse_invoice_xml(load("inv_10pct.xml"))
    assert len(inv.tax_lines) == 1
    line = inv.tax_lines[0]
    assert line.thue_suat == "10%"
    assert line.tien_chua_thue == Decimal("1000000")
    assert line.tien_thue == Decimal("100000")


def test_basic_invoice_status_is_goc():
    inv = parse_invoice_xml(load("inv_10pct.xml"))
    assert inv.trang_thai == "goc"


def test_parses_namespaced_multi_rate_invoice():
    inv = parse_invoice_xml(load("inv_multi_rate_ns.xml"))
    assert inv.so_hd == "9"
    assert inv.mst_ban == "0399999999"
    rates = {l.thue_suat: l.tien_thue for l in inv.tax_lines}
    assert rates["10%"] == Decimal("200000")
    assert rates["5%"] == Decimal("50000")
    assert rates["KCT"] == Decimal("0")
    assert inv.tong_thanh_toan == Decimal("3750000")


def test_detects_replacement_invoice():
    inv = parse_invoice_xml(load("inv_replacement.xml"))
    assert inv.trang_thai == "thay_the"
    assert inv.so_hd == "200"           # this invoice's own number
    assert inv.hd_bi_thay_the == "123"  # references the original it replaces


def test_dedup_key_combines_seller_symbol_number():
    inv = parse_invoice_xml(load("inv_10pct.xml"))
    assert inv.dedup_key == ("0312345678", "C22TAA", "123")


def test_malformed_xml_raises_parse_error():
    with pytest.raises(InvoiceParseError):
        parse_invoice_xml(load("inv_malformed.xml"))
