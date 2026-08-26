"""Sổ hóa đơn CHỈ-CÓ-LINK — tích lũy qua mọi lần chạy, người dùng sửa tay được.

Khác `reports.write_manual_links_csv` (ghi đè mỗi lần chạy, mất dấu): sổ này giữ
lịch sử, và giữ nguyên các ô người dùng tự điền (mã tra cứu, ghi chú) khi tool
ghi lại. Nhờ vậy quy trình "tool bóc không ra mã -> người dùng gõ vào -> chạy
lại -> tool tải được" mới hoạt động. UTF-8 BOM để Excel đọc tiếng Việt đúng.
"""
from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

HEADERS = ["Message-ID", "Ngày mail", "Hộp thư", "Người gửi", "Tiêu đề", "NCC",
           "Mã tra cứu", "Link tra cứu", "Trạng thái", "Chẩn đoán", "File", "Ghi chú"]

#: Ô do NGƯỜI DÙNG điền — tool không bao giờ ghi đè khi đã có giá trị.
USER_FIELDS = ("ma_tra_cuu", "ghi_chu")


@dataclass
class WorkRow:
    """Một hóa đơn chỉ có link tra cứu. Khóa dòng là ``message_id``."""
    message_id: str
    ngay_mail: str = ""
    hop_thu: str = ""
    nguoi_gui: str = ""
    tieu_de: str = ""
    ncc: str = ""
    ma_tra_cuu: str = ""
    link_tra_cuu: str = ""
    trang_thai: str = ""
    chan_doan: str = ""
    file: str = ""
    ghi_chu: str = ""


_ORDER = [f.name for f in fields(WorkRow)]


def load(path) -> dict:
    """Đọc sổ -> {message_id: WorkRow}. File chưa có -> {}."""
    p = Path(path)
    if not p.exists():
        return {}
    out: dict = {}
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if not row or row[0] == HEADERS[0]:
                continue
            row = (list(row) + [""] * len(_ORDER))[:len(_ORDER)]
            item = WorkRow(**dict(zip(_ORDER, row)))
            out[item.message_id] = item
    return out


def merge(cu: dict, moi: list) -> list:
    """Gộp dòng mới vào sổ cũ. Ô người dùng đã điền thì GIỮ NGUYÊN.

    Dòng cũ không xuất hiện trong lần chạy mới vẫn được giữ lại — sổ là lịch sử,
    không phải ảnh chụp một lần chạy.
    """
    ket_qua = dict(cu)
    for row in moi:
        truoc = ket_qua.get(row.message_id)
        if truoc is None:
            ket_qua[row.message_id] = row
            continue
        gop = asdict(row)
        for ten in USER_FIELDS:
            if getattr(truoc, ten, ""):
                gop[ten] = getattr(truoc, ten)
        ket_qua[row.message_id] = WorkRow(**gop)
    return list(ket_qua.values())


def save(path, rows: list) -> Path:
    """Ghi qua file tạm rồi thay thế — Excel đang mở thì báo lỗi rõ, không mất dữ liệu."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADERS)
        for r in rows:
            writer.writerow([getattr(r, name, "") for name in _ORDER])
    try:
        os.replace(tmp, p)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OSError(f"Không ghi được sổ {p} (Excel đang mở file?): {exc}") from exc
    return p


def upsert(path, rows: list) -> Path:
    """load + merge + save."""
    return save(path, merge(load(path), rows))
