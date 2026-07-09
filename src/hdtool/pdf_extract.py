"""Best-effort extraction of invoice fields from a PDF *bản thể hiện*.

Only for invoices that have NO XML (the trusted source). Most VN e-invoice PDFs
carry a text layer, so `pdftotext -layout` recovers the labeled fields without
image OCR. This targets the Thái Sơn / einvoice.vn layout (very common); other
layouts that don't yield a total line return ``None`` → caller keeps them as
"cần nhập tay" rather than fabricating numbers.

Numbers extracted here are flagged ``nguon="PDF"`` so the report marks them for
reconciliation (they are NOT as trustworthy as XML).
"""
from __future__ import annotations

import re
import subprocess
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from .models import Invoice, TaxLine

_NUM = re.compile(r"-?\d[\d.,]*")


def _money(s: str) -> Decimal:
    """Parse a VN-formatted amount ('818.000' or '818,000') to Decimal."""
    s = s.strip().replace(".", "").replace(",", "").replace(" ", "")
    try:
        return Decimal(s or "0")
    except InvalidOperation:
        return Decimal(0)


def _nums(line: str) -> list[Decimal]:
    return [_money(m.group()) for m in _NUM.finditer(line)]


def _first(pattern: str, text: str, flags=0) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def parse_pdf_text(text: str) -> Optional[Invoice]:
    """Parse pdftotext output into an Invoice, or None if not confidently parseable.

    Requires at least an invoice number and a total-payment line — otherwise we
    refuse to guess.
    """
    tm = re.search(r"(?im)^.*Tổng cộng tiền thanh toán.*$", text)
    total_line = tm.group(0) if tm else None
    so_hd = _first(r"Số\s*\(No\.?\)\s*:\s*(\d+)", text)
    if not total_line or not so_hd:
        return None

    totals = _nums(total_line)
    if len(totals) < 3:
        return None
    tien_chua_thue, tien_thue, tong = totals[-3], totals[-2], totals[-1]

    serial = _first(r"Ký hiệu\s*\(Serial\)\s*:\s*(\S+)", text) or ""
    mau_so, ky_hieu = (serial[:1], serial[1:]) if serial else ("", "")

    ngay_lap = None
    md = re.search(r"Ngày\(Date\)\s*(\d{1,2})\s*tháng\(month\)\s*(\d{1,2})\s*năm\(year\)\s*(\d{4})", text)
    if md:
        ngay_lap = date(int(md.group(3)), int(md.group(2)), int(md.group(1)))

    # Seller MST = first Tax code (top block), buyer MST = second, spaces stripped.
    msts = [re.sub(r"[ ]", "", m) for m in re.findall(r"Mã số thuế\s*\(Tax code\)\s*:\s*([0-9 ]+(?:-[0-9 ]+)?)", text)]
    msts = [m.strip("-") for m in msts if m.strip()]
    mst_ban = msts[0] if msts else ""
    mst_mua = msts[1] if len(msts) > 1 else ""

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    ten_ban = lines[0] if lines else ""
    ten_mua = _first(r"Tên đơn vị\s*\(Company\)\s*:\s*(.+)", text) or ""
    ma_tra_cuu = _first(r"Mã cơ quan Thuế\s*:\s*(\S+)", text) or ""
    hinh_thuc_tt = _first(r"Hình thức thanh toán\s*\(Payment method\)\s*:\s*(\S+)", text) or ""

    tax_lines = []
    for m in re.finditer(r"(?im)^.*Tổng tiền chịu thuế suất\s*(\d+)%.*$", text):
        nums = _nums(m.group(0))
        # Empty rate rows contain only the rate digit repeated; a real line has a
        # money-sized amount. Skip rows whose largest number is just the rate.
        if len(nums) >= 3 and max(nums) >= 100:
            tax_lines.append(TaxLine(f"{m.group(1)}%", nums[-3], nums[-2]))

    return Invoice(
        so_hd=so_hd, ky_hieu_mau_so=mau_so, ky_hieu=ky_hieu, ngay_lap=ngay_lap,
        mst_ban=mst_ban, ten_ban=ten_ban, mst_mua=mst_mua, ten_mua=ten_mua,
        don_vi_tien="VND", tien_chua_thue=tien_chua_thue, tien_thue=tien_thue,
        tong_thanh_toan=tong, tax_lines=tax_lines,
        ma_tra_cuu=ma_tra_cuu, hinh_thuc_tt=hinh_thuc_tt.strip(), nguon="PDF",
    )


# A PDF whose embedded text layer is shorter than this is treated as a scanned
# image (nothing to parse) → fall back to OCR.
_MIN_TEXT_LEN = 50


def pdf_to_text(pdf_path) -> str:
    """Run `pdftotext -layout` on a PDF; empty string if it fails / no text layer."""
    try:
        out = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"],
                             capture_output=True, timeout=30)
        return out.stdout.decode("utf-8", "replace")
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def pdf_to_ocr_text(pdf_path, lang: str = "vie") -> str:
    """OCR a scanned (image-only) PDF: pdftoppm (page 1, 300dpi PNG) → tesseract.

    Returns '' on any failure or missing binary (tesseract/pdftoppm) — the caller
    then keeps the invoice as "cần nhập tay" rather than crashing. Only page 1 is
    OCR'd: the header/totals a VN e-invoice needs live there, and piping a single
    PNG to stdout avoids multi-page concatenation.
    """
    try:
        ppm = subprocess.run(
            ["pdftoppm", "-r", "300", "-png", "-f", "1", "-l", "1", str(pdf_path), "-"],
            capture_output=True, timeout=120)
        if ppm.returncode != 0 or not ppm.stdout:
            return ""
        ocr = subprocess.run(["tesseract", "stdin", "stdout", "-l", lang],
                             input=ppm.stdout, capture_output=True, timeout=120)
        if ocr.returncode != 0:
            return ""
        return ocr.stdout.decode("utf-8", "replace")
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def extract_pdf_invoice(pdf_path) -> Optional[Invoice]:
    """Extract an Invoice from a PDF-only bản thể hiện, or None if not parseable.

    Prefer the embedded text layer (fast, exact). If the PDF has essentially no
    text — a scanned image — fall back to OCR and flag ``nguon="PDF-OCR"`` so the
    report marks it for closer đối soát (OCR can misread digits).
    """
    text = pdf_to_text(pdf_path)
    nguon = "PDF"
    if len(text.strip()) < _MIN_TEXT_LEN:
        text = pdf_to_ocr_text(pdf_path)
        nguon = "PDF-OCR"
    inv = parse_pdf_text(text)
    if inv is not None:
        inv.pdf_path = str(pdf_path)
        inv.nguon = nguon
    return inv
