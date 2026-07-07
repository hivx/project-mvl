"""Collect invoice files from emails into a local period/supplier tree.

Two branches (see design):
  * Attachment branch: pull .xml/.pdf (and unzip .zip bundles). XML preferred.
  * Link branch: extract tra-cứu URLs so a portal adapter can fetch them later.
    Until an adapter exists for an issuer, such invoices are listed as
    "cần tải tay".
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date
from email.message import Message
from pathlib import Path
from typing import Optional

_URL_RE = re.compile(r'https?://[^\s"\'<>)\]]+')


@dataclass
class Attachment:
    filename: str
    kind: str   # xml | pdf | zip | other
    data: bytes


def slug(text: str, maxlen: int = 60) -> str:
    """Filesystem-safe, diacritic-free slug for supplier folder names."""
    t = (text or "").replace("đ", "d").replace("Đ", "D")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t[:maxlen] or "unknown"


def _kind(filename: str) -> str:
    low = filename.lower()
    if low.endswith(".xml"):
        return "xml"
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(".zip"):
        return "zip"
    return "other"


def iter_attachments(msg: Message) -> list[Attachment]:
    """All attachment parts of an email (not yet expanding zips)."""
    out: list[Attachment] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        disposition = (part.get("Content-Disposition") or "").lower()
        if not filename and "attachment" not in disposition:
            continue
        data = part.get_payload(decode=True)
        if data is None:
            continue
        filename = filename or "attachment"
        out.append(Attachment(filename, _kind(filename), data))
    return out


def expand_zips(atts: list[Attachment]) -> list[Attachment]:
    """Replace .zip attachments with their inner .xml/.pdf members.

    Encrypted or unreadable members are skipped (never crash the batch). If a
    zip yields nothing extractable, the original zip is kept so the file isn't
    lost — the user can open it manually.
    """
    result: list[Attachment] = []
    for a in atts:
        if a.kind != "zip":
            result.append(a)
            continue
        try:
            zf = zipfile.ZipFile(io.BytesIO(a.data))
        except zipfile.BadZipFile:
            result.append(a)
            continue
        extracted: list[Attachment] = []
        for name in zf.namelist():
            k = _kind(name)
            if k not in ("xml", "pdf"):
                continue
            try:
                extracted.append(Attachment(Path(name).name, k, zf.read(name)))
            except (RuntimeError, zipfile.BadZipFile):
                # encrypted / corrupt member -> skip, keep going
                continue
        result.extend(extracted if extracted else [a])
    return result


def invoice_files(msg: Message) -> list[Attachment]:
    """Attachments with zip bundles expanded — the real invoice files."""
    return expand_zips(iter_attachments(msg))


def has_kind(atts: list[Attachment], kind: str) -> bool:
    return any(a.kind == kind for a in atts)


def _body_text(msg: Message) -> str:
    chunks = []
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                chunks.append(payload.decode(charset, "replace"))
    return " ".join(chunks)


def extract_links(msg: Message, hint_substrings: list[str]) -> list[str]:
    """URLs in the body whose text matches any issuer/tra-cứu hint."""
    text = _body_text(msg)
    hints = [h.lower() for h in hint_substrings if h]
    found = []
    for url in _URL_RE.findall(text):
        low = url.lower()
        if any(h in low for h in hints):
            if url not in found:
                found.append(url)
    return found


def period_dir(base, ngay_lap: Optional[date]) -> Path:
    """base/<YYYY-MM of invoice date>, or base/unknown-period."""
    period = ngay_lap.strftime("%Y-%m") if ngay_lap else "unknown-period"
    return Path(base) / period


def save_invoice_files(
    files: list[Attachment], base_dir, ngay_lap: Optional[date], supplier_name: str
) -> dict:
    """Write invoice files to base/<period>/<supplier-slug>/ and return paths."""
    dest = period_dir(base_dir, ngay_lap) / slug(supplier_name)
    dest.mkdir(parents=True, exist_ok=True)
    saved: dict = {}
    for a in files:
        target = dest / a.filename
        target.write_bytes(a.data)
        saved.setdefault(a.kind, target)
    return saved
