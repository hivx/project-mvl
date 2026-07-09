"""End-to-end OCR check for scanned (image-only) PDFs.

Skipped unless ``tesseract`` + ``gs`` (Ghostscript) are installed AND a real,
text-layer invoice PDF exists under ``data/`` to derive a fixture from. It takes
such a PDF, rasterizes it to an image-only PDF (no text layer) with Ghostscript,
and asserts the OCR path recovers the same invoice number, flagged nguon="PDF-OCR".

Install to enable locally:  sudo apt-get install -y tesseract-ocr tesseract-ocr-vie ghostscript
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from hdtool.pdf_extract import extract_pdf_invoice, parse_pdf_text, pdf_to_text

pytestmark = pytest.mark.skipif(
    not (shutil.which("tesseract") and shutil.which("gs")),
    reason="cần tesseract + ghostscript (gs) để test OCR end-to-end",
)


def _first_text_layer_invoice() -> tuple[Path, str] | None:
    """A data/ PDF whose text layer parses to an Invoice (source for the fixture)."""
    for p in sorted(Path("data").rglob("*.pdf")):
        text = pdf_to_text(p)
        inv = parse_pdf_text(text) if len(text.strip()) > 50 else None
        if inv is not None and inv.so_hd:
            return p, inv.so_hd
    return None


def test_ocr_recovers_scanned_invoice(tmp_path):
    picked = _first_text_layer_invoice()
    if picked is None:
        pytest.skip("không có PDF text-layer trong data/ để dựng fixture OCR")
    src, expected_so_hd = picked

    scanned = tmp_path / "scanned.pdf"
    subprocess.run(
        ["gs", "-sDEVICE=pdfimage24", "-r300", "-o", str(scanned), str(src)],
        capture_output=True, timeout=120, check=True,
    )
    # The rasterized PDF must have no usable text layer -> forces the OCR path.
    assert len(pdf_to_text(scanned).strip()) < 50

    inv = extract_pdf_invoice(scanned)
    assert inv is not None, "OCR không bóc được hóa đơn từ PDF ảnh scan"
    assert inv.nguon == "PDF-OCR"
    assert inv.so_hd == expected_so_hd      # OCR read the same invoice number
