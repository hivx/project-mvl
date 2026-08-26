"""Phân loại trang tra cứu + tìm link tải. Phần thuần: không mạng."""
from pathlib import Path

from hdtool.collect import Attachment
from hdtool.portal_probe import (accept_files, candidate_download_links,
                                 classify_page, find_form)

FIXTURES = Path(__file__).parent / "fixtures"
XML_OK = (FIXTURES / "inv_10pct.xml").read_bytes()


def test_classify_file_khi_content_type_khong_phai_html():
    assert classify_page(200, "application/xml; charset=utf-8", "") == "file"
    assert classify_page(200, "application/zip", "") == "file"


def test_classify_error_khi_http_loi():
    assert classify_page(404, "text/html", "<h1>Not found</h1>") == "error"


def test_classify_captcha_thang_truoc_moi_thu_khac():
    """Trang có captcha thường CŨNG có form -> captcha phải được xét trước."""
    html = ('<form action="/tra-cuu"><input name="MaTraCuu">'
            '<div class="g-recaptcha"></div></form>')
    assert classify_page(200, "text/html", html) == "captcha"


def test_classify_spa_khi_toan_script_khong_anchor_nao_chua_ma():
    html = ("<html><body><div id='app'></div>"
            + "<script src='/bundle.js'></script>" * 3 + "</body></html>")
    assert classify_page(200, "text/html", html, ma="ABC123") == "spa"


def test_classify_links_khi_anchor_chua_ma():
    html = '<a href="/dl?Code=ABC123&Type=xml">Tải XML</a>'
    assert classify_page(200, "text/html", html, ma="ABC123") == "links"


def test_classify_form_khi_co_o_nhap_ma():
    html = ('<form action="/tra-cuu" method="post"><input name="MaTraCuu">'
            '<input type="hidden" name="__RequestVerificationToken" value="t1"></form>')
    assert classify_page(200, "text/html", html) == "form"


def test_find_form_mang_theo_hidden_field():
    html = ('<form action="/tra-cuu" method="post"><input name="MaTraCuu" value="">'
            '<input type="hidden" name="__RequestVerificationToken" value="t1"></form>')
    f = find_form(html, "https://x.vn/trang")
    assert f["action"] == "https://x.vn/tra-cuu"
    assert f["method"] == "post"
    assert f["fields"]["__RequestVerificationToken"] == "t1"
    assert "MaTraCuu" in f["fields"]


def test_find_form_tra_none_khi_khong_co_form():
    assert find_form("<p>không có form</p>", "https://x.vn/") is None


def test_candidate_uu_tien_link_chua_ma_va_bo_link_khong_lien_quan():
    html = ('<a href="/help">Hướng dẫn</a>'
            '<a href="/tai-ve?id=9">Tải hóa đơn</a>'
            '<a href="/dl?Code=ABC123&Type=xml">Tải XML</a>')
    out = candidate_download_links(html, "https://x.vn/trang", "ABC123")
    assert out[0] == "https://x.vn/dl?Code=ABC123&Type=xml"
    assert "https://x.vn/help" not in out


def test_accept_files_nhan_xml_hop_le():
    inv = accept_files([Attachment("hd.xml", "xml", XML_OK)])
    assert inv is not None and inv.so_hd == "123"


def test_accept_files_tu_choi_trang_html_gia_dang():
    assert accept_files([Attachment("hd.xml", "xml", b"<html><body>Loi</body></html>")]) is None


def test_accept_files_tu_choi_pdf_don_doc():
    """Nguyên tắc: số liệu chỉ từ XML. PDF đơn độc KHÔNG tính là thành công."""
    assert accept_files([Attachment("hd.pdf", "pdf", b"%PDF-1.4 fake")]) is None
