"""Tests for the einvoice.com.vn portal adapter (HTTP download).

Mocks the HTTP layer — never hits the live portal. Mirrors the real flow proven
by spike: GET tra-cứu page -> __RequestVerificationToken + idHoaDon -> POST
/tai-ve-hoa-don -> ZIP of invoice files.
"""
import io
import zipfile

from hdtool.adapters.einvoice_com_vn import EinvoiceComVnAdapter, parse_download_form

FORM_HTML = """
<form action="/tai-ve-hoa-don" method="post">
  <input name="__RequestVerificationToken" type="hidden" value="TOK123">
  <input name="idHoaDon" type="hidden" value="ID456">
</form>
"""


def _zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("244213_1_C25MSD/244213.xml", b"<HDon><SHDon>244213</SHDon></HDon>")
        z.writestr("244213_1_C25MSD/244213.pdf", b"%PDF fake")
    return buf.getvalue()


class FakeResp:
    def __init__(self, text="", content=b"", status=200, headers=None):
        self.text = text
        self.content = content
        self.status_code = status
        self.headers = headers or {}


class FakeSession:
    def __init__(self, get_resp, post_resp):
        self._g, self._p = get_resp, post_resp
        self.headers = {}
        self.posted = None

    def get(self, url, **kw):
        self.got = url
        return self._g

    def post(self, url, data=None, **kw):
        self.posted = (url, data)
        return self._p


def test_parse_download_form():
    tok, idh = parse_download_form(FORM_HTML)
    assert tok == "TOK123" and idh == "ID456"


def test_can_handle_matches_platform_only():
    a = EinvoiceComVnAdapter()
    assert a.can_handle("https://saigoncoop.einvoice.com.vn/tra-cuu-hoa-don?token=x")
    assert not a.can_handle("https://www.meinvoice.vn/tra-cuu/?sc=x")


def test_fetch_downloads_and_unzips_xml():
    post = FakeResp(content=_zip_bytes(),
                    headers={"content-disposition": "attachment; filename=244213_1_C25MSD.zip",
                             "content-type": "application/zip"})
    sess = FakeSession(FakeResp(text=FORM_HTML), post)
    a = EinvoiceComVnAdapter(session_factory=lambda: sess)
    files = a.fetch("https://saigoncoop.einvoice.com.vn/tra-cuu-hoa-don?token=T")
    xml = [f for f in files if f.kind == "xml"]
    assert xml and b"<SHDon>244213" in xml[0].data
    # POST hit the right base + carried the CSRF token and invoice id
    assert sess.posted[0] == "https://saigoncoop.einvoice.com.vn/tai-ve-hoa-don"
    assert sess.posted[1]["idHoaDon"] == "ID456"
    assert sess.posted[1]["__RequestVerificationToken"] == "TOK123"


def test_fetch_returns_empty_when_no_form():
    sess = FakeSession(FakeResp(text="<html>no form</html>"), FakeResp())
    a = EinvoiceComVnAdapter(session_factory=lambda: sess)
    assert a.fetch("https://x.einvoice.com.vn/tra-cuu-hoa-don?token=T") == []


def test_fetch_rejects_html_error_response():
    # Expired token / 500 -> server returns an HTML error page, not a file.
    post = FakeResp(content=b"<html>Loi he thong</html>", status=200,
                    headers={"content-type": "text/html; charset=utf-8"})
    sess = FakeSession(FakeResp(text=FORM_HTML), post)
    a = EinvoiceComVnAdapter(session_factory=lambda: sess)
    assert a.fetch("https://x.einvoice.com.vn/tra-cuu-hoa-don?token=T") == []


def test_adapter_is_registered_by_default():
    # Importing the adapters package should register a live einvoice.com.vn adapter.
    import importlib
    import hdtool.adapters as ad
    importlib.reload(ad)   # re-run package init to restore registration after other tests cleared it
    assert ad.get_adapter("https://saigoncoop.einvoice.com.vn/tra-cuu-hoa-don?token=x") is not None
