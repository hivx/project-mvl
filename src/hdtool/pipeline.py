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
from .parse_xml import InvoiceParseError, NotAnInvoiceError, parse_invoice_xml


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


def load_invoices(xml_paths: list[Path]) -> tuple[list[Invoice], list[tuple[str, str, str]]]:
    """Parse each XML into an Invoice.

    Returns (invoices, skipped[(path, reason, kind)]) where kind is
    "malformed" (corrupt XML) or "not_invoice" (valid XML, not a TCT invoice).
    """
    invoices: list[Invoice] = []
    skipped: list[tuple[str, str, str]] = []   # (path, reason, kind)
    for p in xml_paths:
        try:
            inv = parse_invoice_xml(p.read_bytes())
        except NotAnInvoiceError as exc:
            skipped.append((str(p), str(exc), "not_invoice"))
            continue
        except InvoiceParseError as exc:
            skipped.append((str(p), f"Lỗi parse XML: {exc}", "malformed"))
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
    data_dir, from_date: date, to_date: date, buyer_msts: set[str], out_path,
    companies: Optional[dict] = None,
) -> tuple[AggregateResult, list[tuple[str, str, str]], list[str]]:
    """Full report stage.

    Returns (aggregate result, skipped[(ident, group, reason)], manual-entry PDFs).
    A parse-failed XML whose filename matches a successfully parsed invoice is a
    harmless forwarded duplicate ("trung_forward"); one with no readable original
    is a real gap ("khong_doc_duoc") that needs manual retrieval.
    """
    xml_paths = find_xml_files(data_dir)
    invoices, parse_errs = load_invoices(xml_paths)
    manual_entry = find_manual_entry_pdfs(data_dir, invoices)
    parsed_names = {Path(inv.xml_path).name for inv in invoices if inv.xml_path}

    skipped: list[tuple[str, str, str]] = []
    for path, _reason, kind in parse_errs:
        if kind == "not_invoice":
            skipped.append((path, "khong_phai_hoa_don",
                            "Không phải hóa đơn (vd thông báo thuế) — bỏ qua"))
        elif Path(path).name in parsed_names:
            skipped.append((path, "trung_forward",
                            "Bản forward trùng — đã có bản gốc trong bảng kê"))
        else:
            skipped.append((path, "khong_doc_duoc",
                            "XML không đọc được và không có bản gốc — cần lấy tay"))

    in_period, dropped = filter_by_period(invoices, from_date, to_date)
    for inv in dropped:
        if inv.ngay_lap is None:
            skipped.append((inv.xml_path or inv.so_hd, "khong_ngay_lap", "Không có ngày lập"))
        else:
            skipped.append((inv.xml_path or inv.so_hd, "ngoai_ky",
                            f"Ngày lập {inv.ngay_lap} ngoài kỳ"))

    result = aggregate(in_period, buyer_msts=buyer_msts, companies=companies)
    for inv, reason in result.excluded:
        skipped.append((inv.xml_path or inv.so_hd, "sai_ben_mua", reason))

    write_workbook(result, out_path, skipped=skipped, manual_entry=manual_entry)
    return result, skipped, manual_entry
