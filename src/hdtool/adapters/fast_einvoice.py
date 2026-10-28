"""Adapter for Fast e-Invoice (``einvoice.fast.com.vn``).

The tra-cứu page ``index.aspx?c=<token>`` is captcha-gated, but each notification
email also carries signed direct-download links that bypass the captcha (proven
by spike 2026-07-09):

    GET index.aspx?type=2&c=<t>&hash=<h>  -> XML  (application/xml attachment)
    GET index.aspx?type=1&c=<t>&hash=<h>  -> PDF  (bản thể hiện)

``type=1/2/3`` share the same ``c`` and ``hash`` — only ``type`` differs. So from
any signed link we fetch the XML (type=2, trusted) plus the PDF (type=1). We claim
ONLY the signed links (``type=`` & ``hash=``), never the bare captcha page. Any
failure / an HTML captcha page returns ``[]`` -> "cần tải tay" (never breaks batch).
"""
from __future__ import annotations

import re
from typing import Optional

from ..collect import Attachment, _kind
from ..http import new_session as _new_session


def _filename(content_disposition: str) -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', content_disposition or "")
    return m.group(1).strip() if m else ""


def _with_type(url: str, type_value: str) -> str:
    """Rewrite the ``type=`` param by string surgery (keeps ``c``/``hash`` literal).

    The token ``c`` carries ``+`` and ``=`` — re-encoding the query would corrupt
    it — so we replace only the ``type`` value and leave the rest of the URL as-is.
    """
    if re.search(r"[?&]type=", url):
        return re.sub(r"([?&]type=)[^&]*", r"\g<1>" + type_value, url, count=1)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}type={type_value}"


class FastEinvoiceAdapter:
    name = "einvoice.fast.com.vn"
    match_hints = ["einvoice.fast.com.vn"]

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or _new_session

    def can_handle(self, url: str) -> bool:
        u = (url or "").lower()
        # Only the signed direct-download links, never the captcha lookup page.
        return "einvoice.fast.com.vn" in u and "type=" in u and "hash=" in u

    def fetch(self, url: str, code: Optional[str] = None) -> list[Attachment]:
        sess = self._session_factory()
        out: list[Attachment] = []
        # XML first (trusted source), then the PDF bản thể hiện.
        for type_value, fallback in (("2", "hoadon.xml"), ("1", "hoadon.pdf")):
            try:
                r = sess.get(_with_type(url, type_value), timeout=30)
            except Exception:  # noqa: BLE001 - a bad type must not sink the other
                continue
            if getattr(r, "status_code", 0) != 200 or not getattr(r, "content", b""):
                continue
            if "text/html" in r.headers.get("content-type", "").lower():
                continue   # captcha / error page, not a file
            fname = (_filename(r.headers.get("content-disposition", "")) or fallback)
            fname = fname.replace("/", "_").replace("\\", "_")
            out.append(Attachment(fname, _kind(fname), r.content))
        return out
