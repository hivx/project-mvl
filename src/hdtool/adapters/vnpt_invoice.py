"""Adapter for VNPT invoice portals (``*-tt78.vnpt-invoice.com.vn``).

The tra-cứu page has ReCaptcha, but each notification email carries a direct
download link that bypasses it (proven by spike):

    GET .../invoice/getinvoice?token=<t>   -> XML (text/plain attachment)
    GET .../Email/PdfDownload?token=<t>    -> PDF

We claim ONLY the ``getinvoice`` link so we always get the trusted XML (not the
PDF). Any failure / an HTML captcha page returns ``[]`` -> "cần tải tay".
"""
from __future__ import annotations

import re
from typing import Optional

import requests

from ..collect import Attachment, _kind, expand_zips


def _filename(content_disposition: str) -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', content_disposition or "")
    return m.group(1).strip() if m else ""


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


class VnptInvoiceAdapter:
    name = "vnpt-invoice.com.vn"
    match_hints = ["vnpt-invoice"]

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or _new_session

    def can_handle(self, url: str) -> bool:
        u = (url or "").lower()
        # Only the direct XML download link (prefer XML over the PDF link).
        return "vnpt-invoice" in u and "getinvoice" in u

    def fetch(self, url: str, code: Optional[str] = None) -> list[Attachment]:
        try:
            r = self._session_factory().get(url, timeout=30)
            if getattr(r, "status_code", 0) != 200 or not getattr(r, "content", b""):
                return []
            if "text/html" in r.headers.get("content-type", "").lower():
                return []   # captcha / error page, not a file
            fname = (_filename(r.headers.get("content-disposition", "")) or "hoadon.xml")
            fname = fname.replace("/", "_").replace("\\", "_")
            att = Attachment(fname, _kind(fname), r.content)
            return expand_zips([att]) if att.kind == "zip" else [att]
        except Exception:  # noqa: BLE001 - never break the collect batch
            return []
