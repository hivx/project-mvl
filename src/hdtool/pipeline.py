"""Orchestration: turn collected XML files into an Excel bảng kê.

report stage = find XML → parse → filter by invoice date (NLap) → aggregate →
Excel. Kept separate from IMAP so it runs and tests without a network.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from .aggregate import AggregateResult, aggregate
from .excel import write_workbook
from .models import Invoice
from .parse_xml import InvoiceParseError, parse_invoice_xml


def find_xml_files(root) -> list[Path]:
    return sorted(Path(root).rglob("*.xml"))


def _sibling_pdf(xml_path: Path) -> Optional[Path]:
    same_stem = xml_path.with_suffix(".pdf")
    if same_stem.exists():
        return same_stem
    pdfs = list(xml_path.parent.glob("*.pdf"))
    if len(pdfs) == 1:
        return pdfs[0]
    return None


def load_invoices(xml_paths: list[Path]) -> tuple[list[Invoice], list[tuple[str, str]]]:
    """Parse each XML into an Invoice. Returns (invoices, skipped[(path, reason)])."""
    invoices: list[Invoice] = []
    skipped: list[tuple[str, str]] = []
    for p in xml_paths:
        try:
            inv = parse_invoice_xml(p.read_bytes())
        except InvoiceParseError as exc:
            skipped.append((str(p), f"Lỗi parse XML: {exc}"))
            continue
        inv.xml_path = str(p)
        pdf = _sibling_pdf(p)
        if pdf is not None:
            inv.pdf_path = str(pdf)
        invoices.append(inv)
    return invoices, skipped


def filter_by_period(
    invoices: list[Invoice], from_date: date, to_date: date
) -> tuple[list[Invoice], list[Invoice]]:
    """Split invoices by whether NLap falls within [from_date, to_date]."""
    keep, dropped = [], []
    for inv in invoices:
        if inv.ngay_lap is not None and from_date <= inv.ngay_lap <= to_date:
            keep.append(inv)
        else:
            dropped.append(inv)
    return keep, dropped


def find_manual_entry_pdfs(data_dir, invoices: list[Invoice]) -> list[str]:
    """PDF files with no XML (not claimed by any parsed invoice).

    These are "cần nhập tay/OCR": we never guess numbers from a PDF.
    """
    claimed = {inv.pdf_path for inv in invoices if inv.pdf_path}
    all_pdfs = [str(p) for p in sorted(Path(data_dir).rglob("*.pdf"))]
    return [p for p in all_pdfs if p not in claimed]


def build_report(
    data_dir, from_date: date, to_date: date, buyer_msts: set[str], out_path
) -> tuple[AggregateResult, list[tuple[str, str]], list[str]]:
    """Full report stage. Returns (aggregate result, skipped items, manual-entry PDFs)."""
    xml_paths = find_xml_files(data_dir)
    invoices, skipped = load_invoices(xml_paths)
    manual_entry = find_manual_entry_pdfs(data_dir, invoices)
    in_period, dropped = filter_by_period(invoices, from_date, to_date)
    for inv in dropped:
        reason = ("Không có ngày lập" if inv.ngay_lap is None
                  else f"Ngày lập {inv.ngay_lap} ngoài kỳ")
        skipped.append((inv.xml_path or inv.so_hd, reason))
    result = aggregate(in_period, buyer_msts=buyer_msts)
    write_workbook(result, out_path, skipped=skipped, manual_entry=manual_entry)
    return result, skipped, manual_entry
