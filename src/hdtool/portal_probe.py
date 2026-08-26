"""Dò cổng tra cứu: phân loại trang, đọc form, tìm link tải, XÁC MINH kết quả.

Bằng chứng duy nhất được chấp nhận là bytes tải về parse ra ``Invoice`` hợp lệ —
nhờ vậy việc tool tự đoán "link nào là link tải" không bao giờ ghi rác vào
``data/``. Đoán sai thì tự biết ngay và bỏ qua.

Phần thuần (phân loại/đọc form/liệt kê ứng viên/xác minh) tách khỏi phần chạm
mạng để test được offline — theo đúng lối `mailscan` tách helper thuần.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from .models import Invoice
from .parse_xml import InvoiceParseError, parse_invoice_xml

_CAPTCHA = ("recaptcha", "g-recaptcha", "hcaptcha", "captcha")
_DL_HINT = ("xml", "download", "tai-ve", "taive", "export", "downloadhandler")
_DL_TEXT = re.compile(r">\s*(t[ảa]i\s+xml|t[ảa]i\s+h[óo]a\s+[đd]\S*n|xml)\s*<",
                      re.IGNORECASE)
#: Tên ô input nhận mã tra cứu trên form của cổng.
MA_INPUT = re.compile(r"(ma|code|key)", re.IGNORECASE)


def _anchors(html: str, base_url: str, ma: str = "") -> list:
    """Anchor có dáng link tải, xếp theo độ tin cậy giảm dần."""
    found: list = []
    for m in re.finditer(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                         html or "", re.IGNORECASE | re.DOTALL):
        href, text = m.group(1), m.group(2)
        diem = 0
        if ma and ma in href:
            diem += 5                                  # tin cậy nhất
        if any(h in href.lower() for h in _DL_HINT):
            diem += 3
        if _DL_TEXT.search(">" + text + "<"):
            diem += 2
        if diem:
            found.append((diem, urljoin(base_url, href)))
    found.sort(key=lambda x: -x[0])
    return [u for _, u in found]


def classify_page(status: int, content_type: str, html: str, ma: str = "") -> str:
    """-> 'file' | 'captcha' | 'links' | 'form' | 'spa' | 'error'.

    Thứ tự xét quan trọng: trang có captcha thường CŨNG có form, nên captcha
    phải chặn trước — tool không bao giờ tìm cách vượt captcha.
    """
    if status >= 400:
        return "error"
    ct = (content_type or "").lower()
    if ct and "html" not in ct and "text/plain" not in ct:
        return "file"
    doc = html or ""
    low = doc.lower()
    if any(k in low for k in _CAPTCHA):
        return "captcha"
    if _anchors(doc, "", ma):
        return "links"
    if "<form" in low:
        return "form"
    if low.count("<script") >= 2:
        return "spa"
    return "error"


def find_form(html: str, base_url: str) -> Optional[dict]:
    """Form đầu tiên: action tuyệt đối, method, và TOÀN BỘ input (kể cả hidden).

    Mang theo hidden field là bắt buộc — cổng dựng trên ASP.NET đòi
    ``__RequestVerificationToken`` (xem `einvoice_com_vn.parse_download_form`).
    """
    m = re.search(r"<form\b([^>]*)>(.*?)</form>", html or "", re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    attrs, body = m.group(1), m.group(2)
    action = re.search(r'action="([^"]*)"', attrs, re.IGNORECASE)
    method = re.search(r'method="([^"]*)"', attrs, re.IGNORECASE)
    fields: dict = {}
    for inp in re.findall(r"<input\b[^>]*>", body, re.IGNORECASE):
        name = re.search(r'name="([^"]+)"', inp, re.IGNORECASE)
        if not name:
            continue
        value = re.search(r'value="([^"]*)"', inp, re.IGNORECASE)
        fields[name.group(1)] = value.group(1) if value else ""
    return {
        "action": urljoin(base_url, action.group(1) if action else ""),
        "method": (method.group(1) if method else "get").lower(),
        "fields": fields,
    }


def candidate_download_links(html: str, base_url: str, ma: str = "") -> list:
    """Link tải ứng viên: anchor trước, rồi URL nằm trong <script> có chứa mã."""
    out = _anchors(html, base_url, ma)
    if ma:
        for m in re.finditer(r"[\"'](/?[^\"'\s]*" + re.escape(ma) + r"[^\"'\s]*)[\"']",
                             html or ""):
            url = urljoin(base_url, m.group(1))
            if url not in out:
                out.append(url)
    return out


def accept_files(files: list) -> Optional[Invoice]:
    """Chỉ nhận khi có XML parse ra Invoice hợp lệ. PDF đơn độc -> None.

    Đây là chốt chặn của cả quy trình dò: không có Invoice thì không ghi gì.
    """
    for f in files or []:
        if f.kind != "xml":
            continue
        try:
            inv = parse_invoice_xml(f.data)
        except InvoiceParseError:
            continue
        if inv.so_hd and inv.ngay_lap and inv.mst_ban:
            return inv
    return None
