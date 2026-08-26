"""Hóa đơn gửi bằng ZIP MÃ HÓA, mật khẩu nằm ở một email KHÁC cùng tiêu đề.

Mẫu SMBC eInvoice (kiểm chứng thật 2026-08-26 — 4/4 hóa đơn phí dịch vụ ngân
hàng, 02→07/2026):

    Email 1: "[ SMBC HN - eInvoice] [8754440] [0005301][30062026] …"
             đính kèm invoice.zip (mã hóa) -> 01GTKT.xml + invoice.pdf
    Email 2: tiêu đề Y HỆT, không đính kèm
             body: "Password unzip file: ya0N1ZzrPPxp"

Trước đây `collect` bỏ qua zip mã hóa nên MẤT TRẮNG cả lớp hóa đơn này.

Zip dùng ZipCrypto cũ (``compress_type=8``), không phải AES — nên ``zipfile``
của thư viện chuẩn giải được, không cần thêm phụ thuộc.

Mật khẩu chỉ tồn tại trong bộ nhớ: giải nén xong chỉ ghi XML/PDF ra đĩa.
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Optional

from .collect import Attachment, _kind

_TIEN_TO = re.compile(r"^(?:\s*(?:fwd|fw|re)\s*:\s*)+", re.IGNORECASE)
_MAT_KHAU = re.compile(
    r"password\s*unzip\s*file\s*:\s*(?:<[^>]+>\s*)*([A-Za-z0-9]{8,20})", re.IGNORECASE)


def chuan_hoa_tieu_de(s: str) -> str:
    """Bỏ mọi tiền tố Fwd:/Fw:/Re: (kể cả lồng nhau) + gộp khoảng trắng, hạ hoa.

    Đây là khóa ghép cặp: email zip và email mật khẩu có cùng tiêu đề gốc, chỉ
    khác tiền tố khi được forward.
    """
    truoc = None
    ra = (s or "").strip()
    while ra != truoc:                      # "Fwd: Fw: RE: ..." lột từng lớp
        truoc = ra
        ra = _TIEN_TO.sub("", ra).strip()
    return re.sub(r"\s+", " ", ra).lower()


def tim_mat_khau(body: str) -> Optional[str]:
    """'Password unzip file: ABC123' -> 'ABC123'. Chịu được thẻ HTML xen giữa."""
    m = _MAT_KHAU.search(body or "")
    return m.group(1) if m else None


def giai_nen_co_mat_khau(zip_bytes: bytes, mat_khau: str) -> list:
    """Giải nén zip có mật khẩu -> Attachment. Sai mật khẩu / hỏng / AES -> []."""
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
        ra = []
        for ten in z.namelist():
            if ten.endswith("/"):
                continue
            data = z.read(ten, pwd=(mat_khau or "").encode())
            ra.append(Attachment(ten.rsplit("/", 1)[-1], _kind(ten), data))
        return ra
    except Exception:  # noqa: BLE001 - RuntimeError sai mật khẩu, BadZipFile, NotImplemented (AES)
        return []


def ghep_cap(emails: list) -> dict:
    """Ghép email-mang-zip với email-mang-mật-khẩu theo tiêu đề chuẩn hóa.

    ``emails``: list các tuple ``(message_id, tieu_de, zip_bytes|None, mat_khau|None)``.
    Trả ``{message_id_của_email_zip: (zip_bytes, mat_khau)}``.

    Phải gom hết rồi mới ghép: hai email đến theo thứ tự bất kỳ, và email mật
    khẩu thường tới sau. Zip không tìm được mật khẩu thì KHÔNG có trong kết quả
    (người dùng sẽ tự điền vào sổ).
    """
    zips: dict = {}          # khóa -> (message_id, zip_bytes)
    mat_khau: dict = {}      # khóa -> mật khẩu
    for message_id, tieu_de, zip_bytes, mk in emails or []:
        khoa = chuan_hoa_tieu_de(tieu_de)
        if zip_bytes and khoa not in zips:
            zips[khoa] = (message_id, zip_bytes)
        if mk and khoa not in mat_khau:
            mat_khau[khoa] = mk
    return {mid: (data, mat_khau[khoa])
            for khoa, (mid, data) in zips.items() if khoa in mat_khau}


def la_zip_ma_hoa(zip_bytes: bytes) -> bool:
    """Zip có ít nhất một thành viên bị mã hóa (bit 0x1 của flag_bits)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
        return any(i.flag_bits & 0x1 for i in z.infolist())
    except Exception:  # noqa: BLE001 - không phải zip
        return False
