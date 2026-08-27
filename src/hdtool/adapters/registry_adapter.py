"""Adapter dựng từ MỘT DÒNG registry — không phải code riêng cho từng cổng.

Thêm nhà cung cấp mới = thêm dữ liệu vào ``config/ncc-registry.yaml`` (tool tự
ghi sau khi dò thành công), không phải viết file Python mới. Cổng phức tạp
(CSRF + POST + zip như einvoice.com.vn) vẫn dùng adapter code riêng, khai trong
registry qua ``dung_adapter``.

Lỗi gì cũng trả ``[]`` để rơi về nhánh dò — công thức hỏng thì tự học lại.
"""
from __future__ import annotations

import re
from typing import Optional

from ..collect import Attachment, _kind, expand_zips
from ..http import new_session as _new_session
from ..ncc import NccEntry, build_url


def _filename(cd: str, fallback: str) -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd or "")
    return m.group(1).strip() if m else fallback


class RegistryAdapter:
    """Tải theo công thức đã học trong registry."""

    def __init__(self, entry: NccEntry, session_factory=None):
        self.entry = entry
        self.name = entry.ten
        self.match_hints = list(entry.nhan_dien or [])
        self._session_factory = session_factory or _new_session

    def can_handle(self, url: str) -> bool:
        """Chỉ nhận khi ĐÃ có công thức — chưa học thì để nhánh dò lo."""
        low = (url or "").lower()
        return bool(self.entry.tai) and any(h.lower() in low for h in self.match_hints)

    def fetch(self, url: str, code: Optional[str] = None) -> list:
        if not code:
            return []
        try:
            session = self._session_factory()
            out: list = []
            for loai, fallback in (("xml", "hoadon.xml"), ("pdf", "hoadon.pdf")):
                target = build_url(self.entry, code, loai)
                if not target:
                    continue
                resp = session.get(target, timeout=30)
                if getattr(resp, "status_code", 0) != 200:
                    continue
                ct = (resp.headers.get("content-type") or "").lower()
                if "html" in ct or not getattr(resp, "content", b""):
                    continue          # trang lỗi/hết hạn, không phải file
                fname = _filename(resp.headers.get("content-disposition", ""), fallback)
                out.extend(expand_zips([Attachment(fname, _kind(fname), resp.content)]))
            return out
        except Exception:  # noqa: BLE001 - không bao giờ làm sập batch
            return []
