"""Score an email on how likely it carries a Vietnamese e-invoice.

Signals (strongest first): .xml attachment > issuer domain > subject keyword >
tra-cứu link. A whitelisted sender is always trusted. Scores map to three
buckets so ambiguous mail lands in a human-review list rather than being
silently kept or dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .models import EmailCandidate

W_XML = 5
W_ISSUER = 3
W_KEYWORD = 2
W_PDF = 1
W_LINK = 1
W_WHITELIST = 100


@dataclass
class ClassifierConfig:
    issuer_domains: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    whitelist_senders: list[str] = field(default_factory=list)
    # Senders that never send VAT invoices (e.g. bank payment-receipt notifiers).
    # A match forces "ignore" UNLESS the mail carries an XML (then keep it, to
    # never lose a real invoice).
    exclude_senders: list[str] = field(default_factory=list)
    # Subjects that are never a VAT invoice (login alerts, prepaid-account
    # notices…). Needed when the SENDER is a real issuer: blocking
    # hoadondientu@vnpt-invoice.vn wholesale would drop genuine VNPT invoices.
    # Same override applies: an XML in the mail always wins.
    exclude_subjects: list[str] = field(default_factory=list)
    certain_threshold: int = 5
    suspect_threshold: int = 2


def score_email(
    sender: str,
    subject: str,
    has_xml: bool,
    has_pdf: bool,
    has_link: bool,
    cfg: ClassifierConfig,
    uid: str = "",
    message_id: str = "",
    internal_date: Optional[date] = None,
    account: str = "",
) -> EmailCandidate:
    sender_l = (sender or "").lower()
    subject_l = (subject or "").lower()
    score = 0
    reasons: list[str] = []

    # Excluded sender + no XML -> not a VAT invoice (bank receipt, statement…).
    # XML present overrides: never drop a mail that actually carries invoice data.
    excluded = any(x.lower() in sender_l for x in cfg.exclude_senders if x)
    subject_excluded = any(x.lower() in subject_l for x in cfg.exclude_subjects if x)
    if (excluded or subject_excluded) and not has_xml:
        ly_do = ("Tiêu đề trong danh sách loại trừ (không phải HĐ GTGT)"
                 if subject_excluded and not excluded
                 else "Người gửi trong danh sách loại trừ (không phải HĐ GTGT)")
        return EmailCandidate(
            message_id=message_id, uid=uid, sender=sender, subject=subject,
            internal_date=internal_date, score=0, reasons=[ly_do],
            has_xml=has_xml, has_pdf=has_pdf, has_link=has_link,
            bucket="ignore", account=account,
        )

    whitelisted = any(w.lower() in sender_l for w in cfg.whitelist_senders if w)
    if whitelisted:
        score += W_WHITELIST
        reasons.append("Người gửi trong whitelist")

    if has_xml:
        score += W_XML
        reasons.append("Có file XML đính kèm")

    if any(dom.lower() in sender_l for dom in cfg.issuer_domains if dom):
        score += W_ISSUER
        reasons.append("Người gửi từ domain nhà phát hành")

    if any(kw.lower() in subject_l for kw in cfg.keywords if kw):
        score += W_KEYWORD
        reasons.append("Tiêu đề chứa từ khóa hóa đơn")

    if has_pdf:
        score += W_PDF
        reasons.append("Có file PDF đính kèm")

    if has_link:
        score += W_LINK
        reasons.append("Có link tra cứu")

    if score >= cfg.certain_threshold:
        bucket = "certain"
    elif score >= cfg.suspect_threshold:
        bucket = "suspect"
    else:
        bucket = "ignore"

    return EmailCandidate(
        message_id=message_id,
        uid=uid,
        sender=sender,
        subject=subject,
        internal_date=internal_date,
        score=score,
        reasons=reasons,
        has_xml=has_xml,
        has_pdf=has_pdf,
        has_link=has_link,
        bucket=bucket,
        account=account,
    )
