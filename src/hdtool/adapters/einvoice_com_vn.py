"""Adapter for the einvoice.com.vn platform (VNPT/Thái Sơn white-label).

Many issuers publish tra-cứu links under ``<company>.einvoice.com.vn`` (e.g.
``saigoncoop.einvoice.com.vn``). The invoice download is a plain server-rendered
form (no captcha, no SPA), proven by spike:

  GET  tra-cứu page (token in URL) -> hidden __RequestVerificationToken + idHoaDon
  POST /tai-ve-hoa-don {token, idHoaDon}                      -> ZIP of XML + PDF

We unpack the ZIP with ``collect.expand_zips`` and return XML (preferred) + PDF.
Any failure returns ``[]`` so ``collect`` falls back to "cần tải tay" — never
crashes the batch.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

import requests

from ..collect import Attachment, _kind, expand_zips


def parse_download_form(html: str) -> tuple[Optional[str], Optional[str]]:
    """Pull (__RequestVerificationToken, idHoaDon) out of the tra-cứu page."""
    tok = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html or "")
    idh = re.search(r'name="idHoaDon"[^>]*value="([^"]+)"', html or "")
    return (tok.group(1) if tok else None, idh.group(1) if idh else None)


def _filename(content_disposition: str) -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', content_disposition or "")
    return m.group(1).strip() if m else ""


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


class EinvoiceComVnAdapter:
    name = "einvoice.com.vn"
    match_hints = ["einvoice.com.vn"]

    def __init__(self, session_factory=None):
        # session_factory injected in tests; production builds a real session.
        self._session_factory = session_factory or _new_session

    def can_handle(self, url: str) -> bool:
        return any(h in url.lower() for h in self.match_hints)

    def fetch(self, url: str, code: Optional[str] = None) -> list[Attachment]:
        try:
            session = self._session_factory()
            page = session.get(url, timeout=30)
            token, id_hd = parse_download_form(getattr(page, "text", ""))
            if not token or not id_hd:
                return []
            p = urlparse(url)
            dl = session.post(
                f"{p.scheme}://{p.netloc}/tai-ve-hoa-don",
                data={"__RequestVerificationToken": token, "idHoaDon": id_hd},
                timeout=30,
            )
            if getattr(dl, "status_code", 0) != 200 or not getattr(dl, "content", b""):
                return []
            # An error/expired-token response is an HTML page, not a file. Only a
            # real download (zip/xml/pdf attachment) should be accepted.
            ct = dl.headers.get("content-type", "").lower()
            if "text/html" in ct:
                return []
            fname = _filename(dl.headers.get("content-disposition", "")) or "hoadon.zip"
            return expand_zips([Attachment(fname, _kind(fname), dl.content)])
        except Exception:  # noqa: BLE001 - never break the collect batch
            return []
