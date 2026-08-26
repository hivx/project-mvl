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


# ---------------------------------------------------------------- probe (mock HTTP)

import pytest  # noqa: E402

from hdtool.portal_probe import ProbeResult, probe  # noqa: E402


@pytest.fixture(autouse=True)
def _khong_ngu(monkeypatch):
    """Bỏ nghỉ-giữa-request cho test chạy nhanh."""
    monkeypatch.setattr("hdtool.portal_probe.time.sleep", lambda *_: None)


class FakeResp:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")


class FakeSession:
    """Trả response theo đúng URL được gọi; đếm số request."""

    def __init__(self, by_url):
        self.by_url = by_url
        self.headers = {}
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        return self.by_url.get(url, FakeResp(b"", status=404))

    def post(self, url, data=None, **kw):
        self.calls.append(url)
        return self.by_url.get(url, FakeResp(b"", status=404))


HTML_TRANG = b'<html><a href="/dl?Code=ABC123&Type=xml">Tai XML</a></html>'
CT_HTML = {"content-type": "text/html"}
CT_XML = {"content-type": "application/xml",
          "content-disposition": 'attachment;filename="hd.xml"'}


def test_probe_tai_va_xac_minh_duoc_tu_trang_html_thuan():
    sess = FakeSession({
        "https://x.vn/tra-cuu?c=ABC123": FakeResp(HTML_TRANG, headers=CT_HTML),
        "https://x.vn/dl?Code=ABC123&Type=xml": FakeResp(XML_OK, headers=CT_XML),
    })
    res = probe("https://x.vn/tra-cuu?c=ABC123", "ABC123", lambda: sess)
    assert res.page_kind == "links"
    assert res.download_url == "https://x.vn/dl?Code=ABC123&Type=xml"
    assert [f.kind for f in res.files] == ["xml"]


def test_probe_dung_ngay_khi_gap_captcha_va_khong_tai_gi():
    sess = FakeSession({"https://x.vn/p": FakeResp(
        b'<div class="g-recaptcha"></div>', headers=CT_HTML)})
    res = probe("https://x.vn/p", "ABC123", lambda: sess)
    assert res.page_kind == "captcha" and res.files == []
    assert len(sess.calls) == 1              # KHÔNG thử tải thêm gì
    assert "captcha" in res.chan_doan


def test_probe_khong_nhan_ung_vien_tra_ve_html():
    sess = FakeSession({
        "https://x.vn/p": FakeResp(HTML_TRANG, headers=CT_HTML),
        "https://x.vn/dl?Code=ABC123&Type=xml": FakeResp(b"<html>Het han</html>",
                                                         headers=CT_HTML),
    })
    res = probe("https://x.vn/p", "ABC123", lambda: sess)
    assert res.files == [] and res.chan_doan


def test_probe_link_tra_cuu_chinh_la_link_tai():
    """Ca VNPT/Fast: GET link trong mail ra thẳng XML."""
    sess = FakeSession({"https://x.vn/getinvoice?token=T": FakeResp(XML_OK, headers=CT_XML)})
    res = probe("https://x.vn/getinvoice?token=T", None, lambda: sess)
    assert res.page_kind == "file" and [f.kind for f in res.files] == ["xml"]


def test_probe_dien_form_va_post_kem_hidden_field():
    form = (b'<form action="/tra-cuu" method="post">'
            b'<input name="MaTraCuu" value="">'
            b'<input type="hidden" name="__RequestVerificationToken" value="t1">'
            b'</form>')
    sess = FakeSession({
        "https://x.vn/p": FakeResp(form, headers=CT_HTML),
        "https://x.vn/tra-cuu": FakeResp(HTML_TRANG, headers=CT_HTML),
        "https://x.vn/dl?Code=ABC123&Type=xml": FakeResp(XML_OK, headers=CT_XML),
    })
    res = probe("https://x.vn/p", "ABC123", lambda: sess)
    assert [f.kind for f in res.files] == ["xml"]
    assert "https://x.vn/tra-cuu" in sess.calls


def test_probe_khong_vuot_qua_gioi_han_request():
    many = "".join(f'<a href="/dl{i}?Code=ABC123">Tai XML</a>' for i in range(10))
    sess = FakeSession({"https://x.vn/p": FakeResp(many.encode(), headers=CT_HTML)})
    probe("https://x.vn/p", "ABC123", lambda: sess)
    assert len(sess.calls) <= 5              # MAX_REQUESTS


def test_probe_loi_mang_khong_nem_ngoai_le():
    class SessNo:
        headers = {}

        def get(self, *a, **k):
            raise RuntimeError("timeout giả")

    res = probe("https://x.vn/p", "ABC123", lambda: SessNo())
    assert res.files == [] and "lỗi mạng" in res.chan_doan


# --------------------------------------------- hồi quy trên HTML cổng THẬT (T37)

import pytest as _pytest  # noqa: E402


@_pytest.mark.parametrize("ten,mong_doi", [
    ("meinvoice.html", "captcha"),    # MISA: form txtCode + captcha$captchaTextbox
    ("ehoadon.html", "captcha"),      # BKAV: ASP.NET __VIEWSTATE + captcha
    ("easyinvoice.html", "spa"),      # Thái Sơn: SPA, không anchor tải nào
    ("hilo.html", "form"),            # GSM/hilo: form Filter.SearchKey, KHÔNG captcha
])
def test_classify_tren_trang_that(ten, mong_doi):
    """Khảo sát T37 lấy về HTML thật; mỗi cổng là một ca hồi quy.

    Chống việc sửa regex sau này làm hỏng nhận diện cổng đã biết.
    """
    html = (FIXTURES / "portals" / ten).read_text(encoding="utf-8", errors="replace")
    assert classify_page(200, "text/html", html) == mong_doi


def test_trang_thai_phan_anh_dung_cho_tac_thuc_su():
    """Cột Trạng thái là thứ người dùng đọc trước — không được ghi 'thiếu mã'
    cho một trang thực ra bị chặn bởi captcha."""
    from hdtool.portal_probe import trang_thai
    assert trang_thai(ProbeResult(page_kind="captcha", chan_doan="có captcha")) == "cần trình duyệt"
    assert trang_thai(ProbeResult(page_kind="spa", chan_doan="trang SPA")) == "cần trình duyệt"
    assert trang_thai(ProbeResult(page_kind="form",
                                  chan_doan="trang cần nhập mã nhưng không có mã")) == "thiếu mã"
    assert trang_thai(ProbeResult(page_kind="error",
                                  chan_doan="không có link tra cứu")) == "không có link"
    assert trang_thai(ProbeResult(page_kind="links",
                                  chan_doan="không tìm thấy link tải dùng được")) == "chưa tải được"
    assert trang_thai(ProbeResult(files=[object()], page_kind="links")) == "đã tải"


# ------------------------------------------------- fetch_link_only + tự học (T42)

def test_do_thanh_cong_thi_hoc_va_ghi_registry(tmp_path):
    """Dò ra link tải -> ghi công thức vào registry để lần sau đi tắt."""
    from hdtool.ncc import load_registry
    from hdtool.portal_probe import fetch_link_only

    reg = tmp_path / "ncc.yaml"
    sess = FakeSession({
        "https://x.vn/p": FakeResp(HTML_TRANG, headers=CT_HTML),
        "https://x.vn/dl?Code=ABC123&Type=xml": FakeResp(XML_OK, headers=CT_XML),
    })
    res = fetch_link_only(["https://x.vn/p"], "ABC123", lambda: sess, registry_path=reg)
    assert res.files
    hoc = load_registry(reg)
    assert hoc[-1].tai["xml"] == "https://x.vn/dl?Code={ma}&Type=xml"


def test_cong_thuc_hong_thi_ro_xuong_do_va_hoc_lai(tmp_path):
    """Cổng đổi URL -> công thức cũ hỏng -> tự dò lại và cập nhật. Tự chữa lành."""
    from hdtool.ncc import learn, load_registry, save_registry
    from hdtool.portal_probe import fetch_link_only

    reg = tmp_path / "ncc.yaml"
    save_registry(reg, [learn("https://x.vn/cu?Code=OLD", "OLD", ten="x.vn")])
    sess = FakeSession({
        "https://x.vn/cu?Code=ABC123": FakeResp(b"<html>404</html>", headers=CT_HTML),
        "https://x.vn/p": FakeResp(b'<a href="/moi?Code=ABC123&Type=xml">Tai XML</a>',
                                   headers=CT_HTML),
        "https://x.vn/moi?Code=ABC123&Type=xml": FakeResp(XML_OK, headers=CT_XML),
    })
    res = fetch_link_only(["https://x.vn/p"], "ABC123", lambda: sess, registry_path=reg)
    assert res.files
    assert "moi?Code={ma}" in load_registry(reg)[-1].tai["xml"]


def test_di_tat_bang_cong_thuc_khong_dung_toi_trang_tra_cuu(tmp_path):
    from hdtool.ncc import learn, save_registry
    from hdtool.portal_probe import fetch_link_only

    reg = tmp_path / "ncc.yaml"
    save_registry(reg, [learn("https://x.vn/dl?Code=OLD", "OLD", ten="x.vn")])
    sess = FakeSession({"https://x.vn/dl?Code=ABC123": FakeResp(XML_OK, headers=CT_XML)})
    res = fetch_link_only(["https://x.vn/p"], "ABC123", lambda: sess, registry_path=reg)
    assert res.page_kind == "cong-thuc"
    assert "https://x.vn/p" not in sess.calls      # KHÔNG đụng trang tra cứu
