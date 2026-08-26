"""Dò cổng tra cứu: phân loại trang, đọc form, tìm link tải, XÁC MINH kết quả.

Bằng chứng duy nhất được chấp nhận là bytes tải về parse ra ``Invoice`` hợp lệ —
nhờ vậy việc tool tự đoán "link nào là link tải" không bao giờ ghi rác vào
``data/``. Đoán sai thì tự biết ngay và bỏ qua.

Phần thuần (phân loại/đọc form/liệt kê ứng viên/xác minh) tách khỏi phần chạm
mạng để test được offline — theo đúng lối `mailscan` tách helper thuần.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

import requests

from .collect import Attachment, _kind, expand_zips
from .models import Invoice
from .parse_xml import InvoiceParseError, parse_invoice_xml

#: Trần request cho MỖI hóa đơn — không dò lan man trên cổng của người ta.
MAX_REQUESTS = 5
#: Số ứng viên link tải thử tối đa.
MAX_CANDIDATES = 3

_CAPTCHA = ("recaptcha", "g-recaptcha", "hcaptcha", "captcha")
_DL_HINT = ("xml", "download", "tai-ve", "taive", "export", "downloadhandler")
_DL_TEXT = re.compile(r">\s*(t[ảa]i\s+xml|t[ảa]i\s+h[óo]a\s+[đd]\S*n|xml)\s*<",
                      re.IGNORECASE)
#: Tên ô input nhận mã tra cứu trên form của cổng.
MA_INPUT = re.compile(r"(ma|code|key)", re.IGNORECASE)


def _anchors(html: str, base_url: str, ma: str = "") -> list:
    """Anchor có dáng link tải, xếp theo độ tin cậy giảm dần."""
    found: list = []
    # Tách 2 bước (thẻ -> href) thay vì một regex có [^>]* ở cả hai phía href:
    # trang tra cứu thật nặng ~80KB, kiểu regex đó backtrack siêu tuyến tính.
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", html or "",
                         re.IGNORECASE | re.DOTALL):
        attrs, text = m.group(1), m.group(2)
        href_m = re.search(r'href="([^"]+)"', attrs, re.IGNORECASE)
        if not href_m:
            continue
        href = href_m.group(1)
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


_CHAN_DOAN = {
    "captcha": "có captcha — cần trình duyệt",
    "spa": "trang SPA — cần trình duyệt",
    "error": "link hỏng hoặc hết hạn",
}


@dataclass
class ProbeResult:
    """Kết quả dò một hóa đơn chỉ-link."""
    files: list = field(default_factory=list)
    download_url: Optional[str] = None
    page_kind: str = ""
    chan_doan: str = ""


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _filename(cd: str, fallback: str = "hoadon.xml") -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd or "")
    return m.group(1).strip() if m else fallback


def _as_files(resp) -> list:
    """Response -> Attachment (giải nén zip nếu cần). Trang HTML -> []."""
    ct = (resp.headers.get("content-type") or "").lower()
    if "html" in ct or not getattr(resp, "content", b""):
        return []
    fname = _filename(resp.headers.get("content-disposition", ""))
    return expand_zips([Attachment(fname, _kind(fname), resp.content)])


def probe(url: str, ma: Optional[str] = None, session_factory=None) -> ProbeResult:
    """Dò một link tra cứu: lấy trang -> phân loại -> (POST form) -> tải -> xác minh.

    Không bao giờ ném ngoại lệ: lỗi nào cũng thành ``ProbeResult`` rỗng kèm chẩn
    đoán, để một hóa đơn hỏng không làm sập cả batch.
    """
    try:
        session = (session_factory or _new_session)()
        used = 0
        resp = session.get(url, timeout=30)
        used += 1
        kind = classify_page(resp.status_code, resp.headers.get("content-type", ""),
                             getattr(resp, "text", ""), ma or "")
        if kind == "file":
            files = _as_files(resp)
            if accept_files(files):
                return ProbeResult(files, url, kind)
            return ProbeResult([], None, kind,
                               "tải được file nhưng không parse ra hóa đơn")
        if kind in _CHAN_DOAN:
            return ProbeResult([], None, kind, _CHAN_DOAN[kind])

        html, base = getattr(resp, "text", ""), url
        if kind == "form":
            form = find_form(html, url)
            if not form or not ma:
                return ProbeResult([], None, kind, "trang cần nhập mã nhưng không có mã")
            for ten, gia_tri in list(form["fields"].items()):
                if not gia_tri and MA_INPUT.search(ten):
                    form["fields"][ten] = ma
            resp = (session.post(form["action"], data=form["fields"], timeout=30)
                    if form["method"] == "post"
                    else session.get(form["action"], params=form["fields"], timeout=30))
            used += 1
            html, base = getattr(resp, "text", ""), form["action"]

        for cand in candidate_download_links(html, base, ma or "")[:MAX_CANDIDATES]:
            if used >= MAX_REQUESTS:
                break
            time.sleep(1)                      # lịch sự với cổng của nhà cung cấp
            dl = session.get(cand, timeout=30)
            used += 1
            files = _as_files(dl)
            if accept_files(files):
                return ProbeResult(files, cand, "links")
        return ProbeResult([], None, kind or "links", "không tìm thấy link tải dùng được")
    except Exception as exc:  # noqa: BLE001 - không bao giờ làm sập batch
        return ProbeResult([], None, "error", f"lỗi mạng: {exc}")


def fetch_link_only(links: list, ma: Optional[str] = None,
                    session_factory=None) -> ProbeResult:
    """Adapter code sẵn có trước (nhanh, đã kiểm chứng), không được thì mới dò."""
    from .adapters import try_fetch_links

    files = try_fetch_links(links or [], ma)
    if files and accept_files(files):
        return ProbeResult(files, (links or [None])[0], "adapter")
    res = ProbeResult([], None, "error", "không có link tra cứu")
    for url in (links or [])[:2]:
        res = probe(url, ma, session_factory)
        if res.files:
            break
    return res
