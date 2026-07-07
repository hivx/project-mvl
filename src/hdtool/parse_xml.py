"""Parse Vietnamese e-invoice XML (TCT standard: NĐ123/TT78, QĐ1450/QĐ-TCT).

Only structured XML fields are trusted as data. The parser is
namespace-agnostic (see xmlutil) so it tolerates issuer variations.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from . import xmlutil as X
from .models import Invoice, TaxLine


class InvoiceParseError(Exception):
    """Raised when XML is malformed or lacks the core invoice structure."""


class MalformedXMLError(InvoiceParseError):
    """XML is not well-formed (corrupt / truncated attachment)."""


class NotAnInvoiceError(InvoiceParseError):
    """Well-formed XML but not a TCT invoice (e.g. a tax notification)."""


def _dec(s: Optional[str], default: str = "0") -> Decimal:
    if s is None:
        s = default
    s = s.replace(",", "").replace(" ", "").strip()
    if not s:
        s = default
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal(default)


def _date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = s.strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_invoice_xml(data: bytes) -> Invoice:
    """Parse invoice XML bytes into an :class:`Invoice`.

    Raises :class:`InvoiceParseError` on malformed XML or missing core blocks.
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise MalformedXMLError(f"Malformed XML: {exc}") from exc

    ttchung = X.find_first(root, "TTChung")
    ndhdon = X.find_first(root, "NDHDon")
    if ttchung is None or ndhdon is None:
        raise NotAnInvoiceError("Không có TTChung/NDHDon — không phải hóa đơn TCT")

    so_hd = X.text(ttchung, "SHDon", default="") or ""
    mau_so = X.text(ttchung, "KHMSHDon", default="") or ""
    ky_hieu = X.text(ttchung, "KHHDon", default="") or ""
    ngay_lap = _date(X.text(ttchung, "NLap"))
    dvt = X.text(ttchung, "DVTTe", default="VND") or "VND"

    nban = X.find_first(ndhdon, "NBan")
    nmua = X.find_first(ndhdon, "NMua")
    mst_ban = X.text(nban, "MST", default="") or ""
    ten_ban = X.text(nban, "Ten", default="") or ""
    mst_mua = X.text(nmua, "MST", default="") or ""
    ten_mua = X.text(nmua, "Ten", default="") or ""

    ttoan = X.find_first(ndhdon, "TToan")
    tax_lines: list[TaxLine] = []
    if ttoan is not None:
        for ls in X.find_all(ttoan, "LTSuat"):
            tax_lines.append(
                TaxLine(
                    thue_suat=(X.text(ls, "TSuat", default="") or "").strip(),
                    tien_chua_thue=_dec(X.text(ls, "ThTien")),
                    tien_thue=_dec(X.text(ls, "TThue")),
                )
            )
    tien_chua_thue = _dec(X.text(ttoan, "TgTCThue")) if ttoan is not None else Decimal(0)
    tien_thue = _dec(X.text(ttoan, "TgTThue")) if ttoan is not None else Decimal(0)
    tong = _dec(X.text(ttoan, "TgTTTBSo")) if ttoan is not None else Decimal(0)

    trang_thai, hd_bi_thay_the = _detect_status(ttchung)

    return Invoice(
        so_hd=so_hd,
        ky_hieu_mau_so=mau_so,
        ky_hieu=ky_hieu,
        ngay_lap=ngay_lap,
        mst_ban=mst_ban,
        ten_ban=ten_ban,
        mst_mua=mst_mua,
        ten_mua=ten_mua,
        don_vi_tien=dvt,
        tien_chua_thue=tien_chua_thue,
        tien_thue=tien_thue,
        tong_thanh_toan=tong,
        tax_lines=tax_lines,
        trang_thai=trang_thai,
        hd_bi_thay_the=hd_bi_thay_the,
    )


def _detect_status(ttchung: ET.Element) -> tuple[str, Optional[str]]:
    """Detect replacement/adjustment via the related-invoice block.

    Cancellation ("hủy") is recorded at the tax authority, not reliably in the
    XML itself, so it is never asserted here — only replacement/adjustment.
    """
    rel = X.find_first(ttchung, "TTHDLQuan")
    if rel is None:
        return "goc", None
    referenced = X.text(rel, "SHDCLQuan", default=None)
    code = (X.text(rel, "TCHDon", "LHDCLQuan", "TCHDCLQuan", default="") or "").strip()
    note = (X.text(rel, "GChu", default="") or "").lower()
    if code == "2" or "điều chỉnh" in note or "dieu chinh" in note:
        return "dieu_chinh", referenced
    # code == "1" or anything else with a related block -> treat as replacement
    return "thay_the", referenced
