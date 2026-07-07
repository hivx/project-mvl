"""Tests for collecting invoice files from emails."""
import io
import zipfile
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from hdtool.collect import (
    slug, iter_attachments, invoice_files, extract_links,
    period_dir, save_invoice_files, has_kind,
)


def make_email(body="body", attachments=None):
    m = EmailMessage()
    m["From"] = "hoadon@sinvoice.com.vn"
    m["Subject"] = "Hóa đơn"
    m["Message-ID"] = "<abc@x>"
    m.set_content(body)
    for filename, subtype, data in (attachments or []):
        m.add_attachment(data, maintype="application", subtype=subtype, filename=filename)
    return m


def test_slug_strips_vietnamese_diacritics():
    assert slug("CÔNG TY TNHH Điện Máy ABC") == "cong-ty-tnhh-dien-may-abc"


def test_slug_fallback_for_empty():
    assert slug("") == "unknown"


def test_iter_attachments_returns_xml_and_pdf():
    m = make_email(attachments=[
        ("hd123.xml", "xml", b"<HDon></HDon>"),
        ("hd123.pdf", "pdf", b"%PDF-1.4 fake"),
    ])
    atts = iter_attachments(m)
    kinds = sorted(a.kind for a in atts)
    assert kinds == ["pdf", "xml"]
    assert has_kind(atts, "xml")


def test_encrypted_zip_does_not_crash():
    # An encrypted zip member must be skipped gracefully, not crash the batch.
    data = (Path(__file__).parent / "fixtures" / "encrypted_invoice.zip").read_bytes()
    m = make_email(attachments=[("encrypted_invoice.zip", "zip", data)])
    files = invoice_files(m)  # must not raise RuntimeError
    # nothing extractable -> keep the original zip so the file isn't lost
    assert [f.kind for f in files] == ["zip"]


def test_invoice_files_unzips_inner_xml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hoadon.xml", "<HDon></HDon>")
        zf.writestr("hoadon.pdf", "%PDF fake")
    m = make_email(attachments=[("bundle.zip", "zip", buf.getvalue())])
    files = invoice_files(m)
    kinds = sorted(f.kind for f in files)
    assert kinds == ["pdf", "xml"]
    xml = [f for f in files if f.kind == "xml"][0]
    assert b"HDon" in xml.data


def test_extract_links_filters_by_hint():
    body = ("Kính gửi quý khách, tra cứu tại "
            "https://tracuu.sinvoice.com.vn/xem?ma=ABC123 và "
            "https://unrelated.example.com/promo")
    m = make_email(body=body)
    links = extract_links(m, ["sinvoice", "tracuu", "hoadon"])
    assert any("sinvoice.com.vn" in u for u in links)
    assert all("unrelated.example.com" not in u for u in links)


def test_period_dir_uses_invoice_month(tmp_path):
    d = period_dir(tmp_path, date(2026, 6, 15))
    assert d.name == "2026-06"


def test_period_dir_unknown_when_no_date(tmp_path):
    d = period_dir(tmp_path, None)
    assert "unknown" in d.name


def test_save_invoice_files_writes_tree(tmp_path):
    m = make_email(attachments=[
        ("hd.xml", "xml", b"<HDon></HDon>"),
        ("hd.pdf", "pdf", b"%PDF fake"),
    ])
    files = invoice_files(m)
    saved = save_invoice_files(files, tmp_path, date(2026, 6, 15), "CÔNG TY ABC")
    assert saved["xml"].exists()
    assert saved["pdf"].exists()
    assert "2026-06" in str(saved["xml"])
    assert "cong-ty-abc" in str(saved["xml"])
