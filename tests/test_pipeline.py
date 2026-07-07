"""End-to-end tests for the disk->Excel pipeline (no network)."""
import shutil
from datetime import date
from pathlib import Path

import openpyxl

from hdtool.pipeline import (
    find_xml_files, load_invoices, filter_by_period, build_report,
    find_manual_entry_pdfs,
)

FIXTURES = Path(__file__).parent / "fixtures"
MIYANO = "0301234567"


def _tree(tmp_path, *names):
    """Copy fixtures into a period folder and return the data dir."""
    data = tmp_path / "data"
    dest = data / "2026-06" / "abc"
    dest.mkdir(parents=True)
    for n in names:
        shutil.copy(FIXTURES / n, dest / n)
    return data


def test_find_xml_files_recursive(tmp_path):
    data = _tree(tmp_path, "inv_10pct.xml", "inv_other_buyer.xml")
    found = find_xml_files(data)
    assert len(found) == 2


def test_load_invoices_attaches_paths_and_sibling_pdf(tmp_path):
    data = _tree(tmp_path, "inv_10pct.xml")
    # add a sibling pdf with the same stem
    (data / "2026-06" / "abc" / "inv_10pct.pdf").write_bytes(b"%PDF fake")
    invoices, skipped = load_invoices(find_xml_files(data))
    assert len(invoices) == 1
    assert invoices[0].xml_path.endswith("inv_10pct.xml")
    assert invoices[0].pdf_path.endswith("inv_10pct.pdf")


def test_load_invoices_records_malformed(tmp_path):
    data = _tree(tmp_path, "inv_10pct.xml", "inv_malformed.xml")
    invoices, skipped = load_invoices(find_xml_files(data))
    assert len(invoices) == 1
    assert len(skipped) == 1
    assert "malformed" in skipped[0][0].lower()


def test_filter_by_period_uses_invoice_date():
    from hdtool.models import Invoice
    from decimal import Decimal

    def inv(d):
        return Invoice("1", "1", "K", d, "0312345678", "S", MIYANO, "M", "VND",
                       Decimal(0), Decimal(0), Decimal(0))

    inside = inv(date(2026, 6, 15))
    outside = inv(date(2026, 7, 20))
    undated = inv(None)
    keep, dropped = filter_by_period([inside, outside, undated],
                                     date(2026, 6, 1), date(2026, 6, 30))
    assert keep == [inside]
    assert outside in dropped and undated in dropped


def test_build_report_end_to_end(tmp_path):
    data = _tree(tmp_path, "inv_10pct.xml", "inv_other_buyer.xml")
    out = tmp_path / "bangke.xlsx"
    result, skipped, manual = build_report(data, date(2026, 6, 1), date(2026, 6, 30),
                                            buyer_msts={MIYANO}, out_path=out)
    assert out.exists()
    # only the Miyano-buyer invoice survives the buyer filter
    assert {inv.so_hd for inv in result.invoices} == {"123"}
    wb = openpyxl.load_workbook(out)
    assert "Bảng kê" in wb.sheetnames


def test_find_manual_entry_pdfs_flags_orphan_pdf(tmp_path):
    data = _tree(tmp_path, "inv_10pct.xml")
    dest = data / "2026-06" / "abc"
    (dest / "inv_10pct.pdf").write_bytes(b"%PDF paired")   # paired with the xml
    (dest / "scan_only.pdf").write_bytes(b"%PDF orphan")   # no xml -> manual entry
    invoices, _ = load_invoices(find_xml_files(data))
    manual = find_manual_entry_pdfs(data, invoices)
    assert [Path(m).name for m in manual] == ["scan_only.pdf"]


def test_build_report_writes_manual_entry_sheet(tmp_path):
    data = _tree(tmp_path, "inv_10pct.xml")
    dest = data / "2026-06" / "abc"
    (dest / "inv_10pct.pdf").write_bytes(b"%PDF paired")
    (dest / "scan_only.pdf").write_bytes(b"%PDF orphan")
    out = tmp_path / "r.xlsx"
    result, skipped, manual = build_report(data, date(2026, 6, 1), date(2026, 6, 30),
                                           buyer_msts={MIYANO}, out_path=out)
    assert any("scan_only.pdf" in m for m in manual)
    assert all("inv_10pct.pdf" not in m for m in manual)
    wb = openpyxl.load_workbook(out)
    assert "Cần nhập tay" in wb.sheetnames
