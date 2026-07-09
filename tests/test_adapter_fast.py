"""Tests for the Fast e-Invoice (einvoice.fast.com.vn) portal adapter.

The tra-cứu page ``index.aspx?c=<token>`` is captcha-gated, but each notification
email also carries signed direct-download links that bypass the captcha (proven
by spike): ``index.aspx?type=2&c=<t>&hash=<h>`` -> XML, ``type=1`` -> PDF. The
token ``c`` and ``hash`` are identical across types — only ``type`` differs, so
from any signed link the adapter can fetch both XML (trusted) and the PDF.
Mocks the HTTP layer.
"""
import re

from hdtool.adapters.fast_einvoice import FastEinvoiceAdapter

XML_LINK = "https://einvoice.fast.com.vn/index.aspx?type=2&c=TOK+EN=012407&hash=ABC123"
PDF_LINK = "https://einvoice.fast.com.vn/index.aspx?type=1&c=TOK+EN=012407&hash=ABC123"
CAPTCHA = "https://einvoice.fast.com.vn/index.aspx?c=TOK+EN=012407"


class FakeResp:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}


class FakeSession:
    """Returns a response keyed by the ``type=`` value of the requested URL."""
    def __init__(self, by_type):
        self.by_type = by_type
        self.headers = {}
        self.gets = []

    def get(self, url, **kw):
        self.gets.append(url)
        t = re.search(r"type=(\d)", url).group(1)
        return self.by_type[t]


def test_can_handle_only_claims_signed_links():
    a = FastEinvoiceAdapter()
    assert a.can_handle(XML_LINK)                 # signed type=&hash= link
    assert a.can_handle(PDF_LINK)
    assert not a.can_handle(CAPTCHA)              # bare captcha page -> ignore
    assert not a.can_handle("https://www.meinvoice.vn/tra-cuu/?sc=x")


def test_fetch_gets_xml_and_pdf_even_from_pdf_link():
    xml = FakeResp(b"<HDon><SHDon>736</SHDon></HDon>",
                   headers={"content-type": "application/xml; charset=utf-8",
                            "content-disposition": 'attachment;filename="20260226736.xml"'})
    pdf = FakeResp(b"%PDF-1.3 fake",
                   headers={"content-type": "application/pdf",
                            "content-disposition": 'inline;filename="20260226736.pdf"'})
    sess = FakeSession({"2": xml, "1": pdf})
    a = FastEinvoiceAdapter(session_factory=lambda: sess)
    files = a.fetch(PDF_LINK)                     # given a PDF (type=1) link...
    kinds = sorted(f.kind for f in files)
    assert kinds == ["pdf", "xml"]               # ...still recovers the XML (type=2)
    xmlf = next(f for f in files if f.kind == "xml")
    assert xmlf.filename == "20260226736.xml"
    assert b"<SHDon>736" in xmlf.data
    assert any("type=2" in u for u in sess.gets)  # rewrote type to fetch XML


def test_fetch_rejects_captcha_html():
    html = FakeResp(b"<html>captcha</html>",
                    headers={"content-type": "text/html; charset=utf-8"})
    a = FastEinvoiceAdapter(session_factory=lambda: FakeSession({"2": html, "1": html}))
    assert a.fetch(XML_LINK) == []


def test_registered_and_routes_signed_link_only():
    import importlib
    import hdtool.adapters as ad
    importlib.reload(ad)
    got = ad.get_adapter(XML_LINK)
    assert got is not None and got.name == "einvoice.fast.com.vn"
    # the captcha page must NOT be claimed by the Fast adapter
    cap = ad.get_adapter(CAPTCHA)
    assert cap is None or cap.name != "einvoice.fast.com.vn"
