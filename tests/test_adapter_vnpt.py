"""Tests for the VNPT (vnpt-invoice.com.vn) portal adapter.

The tra-cứu page has ReCaptcha, but the email carries a direct download link
``invoice/getinvoice?token=...`` that returns the XML with no captcha (proven by
spike). The adapter GETs that link and returns the XML. Mocks the HTTP layer.
"""
from hdtool.adapters.vnpt_invoice import VnptInvoiceAdapter


class FakeResp:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}


class FakeSession:
    def __init__(self, resp):
        self._r = resp
        self.headers = {}
        self.got = None

    def get(self, url, **kw):
        self.got = url
        return self._r


GET_XML = "https://5801201370-tt78.vnpt-invoice.com.vn/invoice/getinvoice?token=ABC%3d%3d"
PDF_LINK = "https://5801201370-tt78.vnpt-invoice.com.vn/Email/PdfDownload?token=ABC"
LOGO = "https://clienttool-cadmin.vnpt-invoice.com.vn/Plugins/logo_hd_01.png"


def test_can_handle_only_claims_getinvoice_link():
    a = VnptInvoiceAdapter()
    assert a.can_handle(GET_XML)          # direct XML endpoint -> claim
    assert not a.can_handle(PDF_LINK)     # prefer XML: don't claim the PDF link
    assert not a.can_handle(LOGO)         # logo image -> ignore
    assert not a.can_handle("https://www.meinvoice.vn/tra-cuu/?sc=x")


def test_fetch_returns_xml():
    resp = FakeResp(content=b"<?xml version='1.0'?><HDon><SHDon>97148</SHDon></HDon>",
                    headers={"content-type": "text/plain",
                             "content-disposition": 'attachment; filename="1/001_C26MDT_97148_18500.xml"'})
    sess = FakeSession(resp)
    a = VnptInvoiceAdapter(session_factory=lambda: sess)
    files = a.fetch(GET_XML)
    assert len(files) == 1
    assert files[0].kind == "xml"
    assert files[0].filename == "1_001_C26MDT_97148_18500.xml"   # slash sanitized
    assert b"<SHDon>97148" in files[0].data


def test_fetch_rejects_html_captcha_page():
    resp = FakeResp(content=b"<html>captcha</html>",
                    headers={"content-type": "text/html; charset=utf-8"})
    a = VnptInvoiceAdapter(session_factory=lambda: FakeSession(resp))
    assert a.fetch(GET_XML) == []


def test_registered_and_routes_from_link_list():
    import importlib
    import hdtool.adapters as ad
    importlib.reload(ad)
    # given the email's link list, the getinvoice link is claimed by VNPT adapter
    links = [LOGO, "https://5801201370-tt78.vnpt-invoice.com.vn",
             PDF_LINK, GET_XML]
    claimed = [l for l in links if ad.get_adapter(l) and
               ad.get_adapter(l).name == "vnpt-invoice.com.vn"]
    assert claimed == [GET_XML]
