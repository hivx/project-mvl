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
    data_dir, from_date: date, to_date: date, buyer_msts: set[str],
    companies: Optional[dict] = None, only_company: Optional[str] = None,
) -> tuple[AggregateResult, list[tuple[str, str, str]], list[str]]:
    """Aggregate collected XML into a report — WITHOUT writing any file.

    Returns (aggregate result, skipped[(ident, group, reason)], manual-entry PDFs).
    Call ``write_report`` to render the result to Excel or CSV.

    A parse-failed XML whose filename matches a successfully parsed invoice is a
    harmless forwarded duplicate ("trung_forward"); one with no readable original
    is a real gap ("khong_doc_duoc") that needs manual retrieval. When
    ``only_company`` is set, a valid mua-vào invoice belonging to the *other*
    buyer company is grouped as "cong_ty_khac" (distinct from a genuine
    wrong-buyer "sai_ben_mua").
    """
    xml_paths = find_xml_files(data_dir)
    invoices, parse_errs = load_invoices(xml_paths)
    # PDF-only "cần nhập tay" list: scope to the selected company's folder so a
    # miyano report doesn't list medcons/_chua-ro PDFs (folders are data/<công ty>/).
    manual_root = Path(data_dir) / only_company if only_company else data_dir
    manual_entry = find_manual_entry_pdfs(manual_root, invoices)
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

    result = aggregate(in_period, buyer_msts=buyer_msts, companies=companies,
                       only_company=only_company)
    for inv, reason in result.excluded:
        # A valid buyer of the *other* company keeps loai="mua_vao": it is not a
        # CC-nhầm, just outside this company's report.
        group = "cong_ty_khac" if inv.loai == "mua_vao" else "sai_ben_mua"
        skipped.append((inv.xml_path or inv.so_hd, group, reason))

    return result, skipped, manual_entry


def write_report(result: AggregateResult, out_path, fmt: str = "xlsx",
                 skipped: Optional[list] = None, manual_entry: Optional[list] = None,
                 from_date: Optional[date] = None, to_date: Optional[date] = None):
    """Render an aggregated result to ``out_path`` in ``fmt`` ("xlsx" or "csv").

    ``from_date``/``to_date`` fill the "Từ ngày … đến ngày …" title of each sheet.
    """
    fmt = (fmt or "xlsx").lower()
    if fmt in ("csv",):
        from .csv_report import write_bang_ke_csv
        return write_bang_ke_csv(result, out_path, skipped=skipped,
                                 manual_entry=manual_entry)
    if fmt not in ("xlsx", "excel"):
        raise ValueError(f"Định dạng không hỗ trợ: {fmt} (chỉ xlsx hoặc csv)")
    return write_workbook(result, out_path, skipped=skipped, manual_entry=manual_entry,
                          from_date=from_date, to_date=to_date)
