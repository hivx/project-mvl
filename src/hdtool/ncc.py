"""Sổ công thức tải theo nhà cung cấp — BỘ NHỚ ĐỆM của quy trình dò.

Cổng chưa từng gặp vẫn tải được (``portal_probe.probe`` chạy đủ các bước). Có
công thức chỉ để đi tắt: đỡ request, đỡ phụ thuộc giao diện cổng. Công thức hỏng
thì rơi ngược về nhánh dò để học lại — tự chữa lành.

File ``config/ncc-registry.yaml`` **có commit** (công thức đi theo repo), khác
với sổ hóa đơn nằm trong ``data/`` (dữ liệu cục bộ, gitignored).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml


@dataclass
class NccEntry:
    """Một nhà cung cấp / cổng tra cứu trong sổ công thức."""
    ten: str
    nhan_dien: list = field(default_factory=list)
    bat_ma: dict = field(default_factory=dict)
    tai: dict = field(default_factory=dict)
    can_phien: bool = False        # True -> phải GET trang tra cứu trước để lấy cookie
    dung_adapter: str = ""         # cổng phức tạp -> dùng adapter code sẵn có
    phai_do_lai: bool = False      # link ký theo phiên -> không template hóa được
    hoc_tu: str = ""               # link mẫu đã học, giữ để đối chứng
    ngay_hoc: str = ""


_TEN_FIELD = {f.name for f in fields(NccEntry)}


def load_registry(path) -> list:
    """Đọc registry. File chưa có -> []. Khóa lạ (người sửa tay) -> bỏ qua, không sập."""
    p = Path(path)
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    out = []
    for item in raw:
        item = {k: v for k, v in (item or {}).items() if k in _TEN_FIELD}
        if item.get("ten"):
            out.append(NccEntry(**item))
    return out


def save_registry(path, entries: list) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump([asdict(e) for e in entries],
                                allow_unicode=True, sort_keys=False),
                 encoding="utf-8")
    return p


def match(entries: list, url: str) -> Optional[NccEntry]:
    """Mục đầu tiên nhận URL này theo ``nhan_dien``."""
    low = (url or "").lower()
    for e in entries or []:
        if any(h and h.lower() in low for h in e.nhan_dien):
            return e
    return None


def learn(download_url: str, ma: str, ten: str = "", ngay: str = "") -> NccEntry:
    """Thay mã trong URL đã XÁC MINH bằng ``{ma}`` -> công thức.

    URL không chứa mã (token sinh theo phiên) -> ``phai_do_lai=True``: vẫn ghi
    nhận nhà cung cấp, chỉ là mỗi hóa đơn phải dò lại thay vì đi tắt.
    """
    host = urlparse(download_url or "").netloc.lower()
    entry = NccEntry(ten=ten or host, nhan_dien=[host] if host else [],
                     hoc_tu=download_url or "", ngay_hoc=ngay)
    if not ma or not download_url or ma not in download_url:
        entry.phai_do_lai = True
        return entry
    mau = download_url.replace(ma, "{ma}")
    entry.tai = {"xml": mau}
    pdf = re.sub(r"(?i)((?:type|format|loai)=)xml", r"\g<1>pdf", mau)
    if pdf != mau:
        entry.tai["pdf"] = pdf          # chưa kiểm chứng cho tới lần tải PDF đầu tiên
    entry.bat_ma = {"tu_link": re.escape(mau.split("{ma}")[0]) + r"([A-Za-z0-9_-]+)"}
    return entry


def build_url(entry: NccEntry, ma: str, loai: str = "xml") -> Optional[str]:
    """Dựng URL tải từ công thức + mã. Chưa có công thức -> None."""
    mau = (entry.tai or {}).get(loai)
    return mau.replace("{ma}", ma) if (mau and ma) else None
