"""Aggregate parsed invoices: dedup, replacement handling, buyer filter, grouping.

Business rules (see design doc):
  * Dedup by (seller MST, symbol, number); keep the latest by issue date.
  * A "thay thế" (replacement) invoice supersedes the original it references,
    which is then marked ``nghi_huy`` and dropped from totals.
  * If buyer MSTs are configured, keep only "mua vào" invoices (buyer == us);
    otherwise keep everything and mark ``khong_ro`` (degrade safely).
  * Totals and per-rate groups are computed over active invoices only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .models import Invoice


@dataclass
class AggregateResult:
    invoices: list[Invoice]                       # kept (deduped + buyer-filtered)
    excluded: list[tuple[Invoice, str]] = field(default_factory=list)
    by_rate: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    total_chua_thue: Decimal = Decimal(0)
    total_thue: Decimal = Decimal(0)
    total_thanh_toan: Decimal = Decimal(0)


def normalize_rate(s: Optional[str]) -> str:
    """Map raw tax-rate text to a canonical bucket: 10% / 8% / 5% / 0% / KCT / KKKNT."""
    if s is None:
        return "KHÁC"
    t = s.strip().upper().replace(" ", "")
    if t in ("KCT", "KHÔNGCHỊUTHUẾ"):
        return "KCT"
    if t == "KKKNT":
        return "KKKNT"
    num = t[:-1] if t.endswith("%") else t
    try:
        val = Decimal(num)
    except Exception:
        return t or "KHÁC"
    if val == val.to_integral_value():
        return f"{int(val)}%"
    return f"{val.normalize()}%"


def aggregate(invoices: list[Invoice], buyer_msts: Optional[set[str]] = None,
              companies: Optional[dict] = None,
              only_company: Optional[str] = None) -> AggregateResult:
    """Aggregate invoices.

    ``only_company`` (a company name from ``companies``) narrows the report to a
    single buyer: invoices of the *other* buyer company are valid mua-vào but
    moved to ``excluded`` — they keep ``loai == "mua_vao"`` so the caller can tell
    them apart from genuine wrong-buyer (CC nhầm) rows. ``None`` keeps every
    configured company (previous behaviour).
    """
    companies = companies or {}
    if not buyer_msts and companies:
        buyer_msts = set(companies)
    buyer_msts = buyer_msts or set()

    kept = _dedup_latest(invoices)
    filtered, excluded = _apply_buyer_filter(kept, buyer_msts, companies)
    # Mark replacements over BOTH companies before narrowing, so a replacement is
    # never missed just because we later report only one company.
    _mark_replacements(filtered)
    if only_company is not None:
        selected, others = [], []
        for inv in filtered:
            (selected if inv.cong_ty == only_company else others).append(inv)
        for inv in others:
            excluded.append((inv, f"Công ty {inv.cong_ty or 'khác'} — "
                                  f"không thuộc báo cáo công ty {only_company}"))
        filtered = selected

    active = [inv for inv in filtered if inv.trang_thai != "nghi_huy"]
    by_rate, tc, tt, ttt = _summarize(active)

    return AggregateResult(
        invoices=filtered,
        excluded=excluded,
        by_rate=by_rate,
        total_chua_thue=tc,
        total_thue=tt,
        total_thanh_toan=ttt,
    )


def _dedup_latest(invoices: list[Invoice]) -> list[Invoice]:
    dedup: dict[tuple[str, str, str], Invoice] = {}
    for inv in invoices:
        k = inv.dedup_key
        cur = dedup.get(k)
        if cur is None or (inv.ngay_lap or date.min) >= (cur.ngay_lap or date.min):
            dedup[k] = inv
    return list(dedup.values())


def _apply_buyer_filter(kept, buyer_msts, companies=None):
    companies = companies or {}
    filtered: list[Invoice] = []
    excluded: list[tuple[Invoice, str]] = []
    for inv in kept:
        if not buyer_msts:
            inv.loai = "khong_ro"
            filtered.append(inv)
        elif inv.mst_mua in buyer_msts:
            inv.loai = "mua_vao"
            inv.cong_ty = companies.get(inv.mst_mua, "")
            filtered.append(inv)
        else:
            inv.loai = "ban_ra" if inv.mst_ban in buyer_msts else "khong_ro"
            excluded.append((inv, f"Bên mua {inv.mst_mua} không thuộc MST Miyano"))
    return filtered, excluded


def _mark_replacements(filtered: list[Invoice]) -> None:
    by_ref = {(inv.mst_ban, inv.so_hd): inv for inv in filtered}
    for inv in filtered:
        if inv.trang_thai == "thay_the" and inv.hd_bi_thay_the:
            orig = by_ref.get((inv.mst_ban, inv.hd_bi_thay_the))
            if orig is not None and orig is not inv:
                orig.trang_thai = "nghi_huy"


def _summarize(active: list[Invoice]):
    by_rate: dict[str, dict[str, Decimal]] = {}
    tc = tt = ttt = Decimal(0)
    for inv in active:
        tc += inv.tien_chua_thue
        tt += inv.tien_thue
        ttt += inv.tong_thanh_toan
        for line in inv.tax_lines:
            r = normalize_rate(line.thue_suat)
            bucket = by_rate.setdefault(
                r, {"tien_chua_thue": Decimal(0), "tien_thue": Decimal(0)}
            )
            bucket["tien_chua_thue"] += line.tien_chua_thue
            bucket["tien_thue"] += line.tien_thue
    return by_rate, tc, tt, ttt
