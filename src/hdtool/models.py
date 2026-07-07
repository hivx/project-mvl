"""Data models for parsed invoices and email candidates."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class TaxLine:
    """One tax-rate breakdown line (THTTLTSuat/LTSuat)."""
    thue_suat: str          # "10%", "8%", "5%", "0%", "KCT", "KKKNT"
    tien_chua_thue: Decimal
    tien_thue: Decimal


@dataclass
class Invoice:
    """A parsed e-invoice. Amounts come only from XML (never guessed)."""
    so_hd: str
    ky_hieu_mau_so: str
    ky_hieu: str
    ngay_lap: Optional[date]
    mst_ban: str
    ten_ban: str
    mst_mua: str
    ten_mua: str
    don_vi_tien: str
    tien_chua_thue: Decimal
    tien_thue: Decimal
    tong_thanh_toan: Decimal
    tax_lines: list[TaxLine] = field(default_factory=list)
    # goc | thay_the | dieu_chinh | nghi_huy
    trang_thai: str = "goc"
    hd_bi_thay_the: Optional[str] = None
    # loai: mua_vao | ban_ra | khong_ro
    loai: str = "khong_ro"
    xml_path: Optional[str] = None
    pdf_path: Optional[str] = None
    source_message_id: Optional[str] = None

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """Uniqueness key: seller MST + invoice symbol + invoice number."""
        return (self.mst_ban, self.ky_hieu, self.so_hd)


@dataclass
class EmailCandidate:
    """An email that scored as a possible invoice during scan."""
    message_id: str
    uid: str
    sender: str
    subject: str
    internal_date: Optional[date]
    score: int
    reasons: list[str] = field(default_factory=list)
    has_xml: bool = False
    has_pdf: bool = False
    has_link: bool = False
    bucket: str = "suspect"   # certain | suspect | ignore
