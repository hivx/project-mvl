"""Tests for collecting invoice files from emails."""
import io
import zipfile
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from hdtool.collect import (
    Attachment, slug, iter_attachments, invoice_files, extract_links,
    period_dir, save_invoice_files, has_kind, invoice_dir,
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


def test_invoice_dir_company_month_sender(tmp_path):
    d = invoice_dir(tmp_path, "miyano", date(2026, 6, 15), "no-reply@xanhsm.com")
    parts = d.relative_to(tmp_path).parts
    assert parts[0] == "miyano"
    assert parts[1] == "2026-06"
    assert "xanhsm" in parts[2]


def test_invoice_dir_fallbacks(tmp_path):
    d = invoice_dir(tmp_path, "", None, "")
    parts = d.relative_to(tmp_path).parts
    assert parts[0] == "_chua-ro-cong-ty"
    assert "unknown" in parts[1]
    assert parts[2] == "khong-ro-nguoi-gui"


def test_save_invoice_files_writes_to_dest(tmp_path):
    m = make_email(attachments=[
        ("hd.xml", "xml", b"<HDon></HDon>"),
        ("hd.pdf", "pdf", b"%PDF fake"),
    ])
    files = invoice_files(m)
    dest = invoice_dir(tmp_path, "miyano", date(2026, 6, 15), "no-reply@xanhsm.com")
    saved = save_invoice_files(files, dest)
    assert saved["xml"].exists()
    assert saved["pdf"].exists()
    s = str(saved["xml"])
    assert "miyano" in s and "2026-06" in s and "xanhsm" in s


def test_save_invoice_files_khong_ghi_de_khi_khac_noi_dung(tmp_path):
    """Hai HĐ khác nhau trùng tên file -> phải giữ cả hai."""
    save_invoice_files([Attachment("hoadon.xml", "xml", b"<A/>")], tmp_path)
    save_invoice_files([Attachment("hoadon.xml", "xml", b"<B/>")], tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hoadon-2.xml", "hoadon.xml"]
    assert (tmp_path / "hoadon.xml").read_bytes() == b"<A/>"
    assert (tmp_path / "hoadon-2.xml").read_bytes() == b"<B/>"


def test_save_invoice_files_trung_noi_dung_thi_dung_lai_file_cu(tmp_path):
    """Tải lại đúng file cũ -> không đẻ bản sao (giữ tính idempotent)."""
    a = Attachment("hoadon.xml", "xml", b"<A/>")
    save_invoice_files([a], tmp_path)
    saved = save_invoice_files([a], tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["hoadon.xml"]
    assert saved["xml"].name == "hoadon.xml"
