"""Bóc LINK TRA CỨU và MÃ TRA CỨU ra khỏi email hóa đơn.

Một email hóa đơn thường có 5–15 URL (logo, website, mạng xã hội, hủy đăng ký).
Lấy cái đầu tiên là sai — phải chấm điểm. Mã thì thường KHÔNG nằm trong link:
mail ghi "Mã tra cứu: ABC123" còn link chỉ dẫn tới form trống.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

#: Tham số query thường chứa mã tra cứu.
_CODE_PARAMS = ("code", "ma", "matracuu", "mst", "key", "id", "token", "hash", "c", "sc")

#: Nhãn đứng trước mã trong nội dung mail (chịu được thiếu dấu tiếng Việt).
_CODE_LABELS = (r"M[ãa]\s+tra\s+c[ứu]u", r"M[ãa]\s+nh[ậa]n\s+h[óo]a\s+[đd]\S*n",
                r"M[ãa]\s+s[ốo]\s+b[íi]\s+m[ậa]t", r"M[ãa]\s+b[ảa]o\s+m[ậa]t",
                r"M[ãa]\s+H[ĐD]", r"MTC", r"Lookup\s+code", r"Code")

#: Hình dạng mã: 6–24 ký tự, CHỮ HOA + số + _ - (đủ để loại chữ tiếng Việt).
_CODE_SHAPE = r"[A-Z0-9][A-Z0-9_-]{5,23}"

_BAD_URL = ("unsubscribe", "facebook.", "zalo.", "youtube.", "linkedin.", "twitter.")
_IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")


def code_from_url(url: str) -> Optional[str]:
    """Mã trong URL: ưu tiên query (?Code=/?ma=/?c=…), rồi tới path.

    ehoadon đặt mã thẳng vào path (``tracuu.ehoadon.vn/UTAWCE3X5A5``) nên chỉ
    đọc query là trượt. Đoạn path chỉ được nhận khi khớp đúng dáng mã (CHỮ HOA +
    số) — ``/tra-cuu`` hay ``/DownloadHandler.ashx`` có chữ thường nên không dính.
    """
    try:
        parsed = urlparse(url or "")
        qs = parse_qs(parsed.query)
    except ValueError:
        return None
    for key, values in qs.items():
        if key.lower() in _CODE_PARAMS:
            for v in values:
                v = v.strip()
                if re.fullmatch(_CODE_SHAPE, v):
                    return v
    duoi = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return duoi if re.fullmatch(_CODE_SHAPE, duoi) else None


def find_code(text: str, html: str = "") -> Optional[str]:
    """Mã trong nội dung: 'Mã tra cứu: ABC123' hoặc ô <td> kế bên nhãn."""
    for label in _CODE_LABELS:
        m = re.search(label + r"\s*[:\-]?\s*(" + _CODE_SHAPE + r")\b", text or "")
        if m:
            return m.group(1)
    for label in _CODE_LABELS:
        m = re.search(label + r"\s*</t[dh]>\s*<t[dh][^>]*>\s*(" + _CODE_SHAPE + r")\s*<",
                      html or "", re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _score(url: str, sender_domain: str, issuer_domains: list) -> int:
    parsed = urlparse((url or "").lower())
    score = 0
    if code_from_url(url):
        score += 5
    if any(k + "=" in parsed.query for k in _CODE_PARAMS):
        score += 2
    if re.search(r"tra-?cuu|lookup|invoice|hoadon|hddt", parsed.path):
        score += 3
    if any(d and d in parsed.netloc for d in issuer_domains):
        score += 3
    if not parsed.query and sender_domain and sender_domain in parsed.netloc:
        score -= 3        # thường là trang chủ của NCC, không phải link tra cứu
    return score


def rank_links(urls: list, sender: str, issuer_domains: list) -> list:
    """URL trong mail, xếp theo khả năng là link tra cứu (cao -> thấp)."""
    m = re.search(r"@([\w.\-]+)", sender or "")
    sender_domain = m.group(1).lower() if m else ""
    ung_vien = []
    for url in urls or []:
        low = (url or "").lower()
        if not low.startswith("http"):
            continue
        if low.endswith(_IMG_EXT) or any(b in low for b in _BAD_URL):
            continue
        diem = _score(url, sender_domain, issuer_domains or [])
        if diem > 0:
            ung_vien.append((diem, url))
    ung_vien.sort(key=lambda x: -x[0])
    return [u for _, u in ung_vien]
