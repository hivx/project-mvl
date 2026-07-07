"""Read-only IMAP scanning of the invoice mailbox.

Absolutely never mutates the mailbox: SELECT is readonly, fetches use BODY.PEEK,
nothing is marked, moved, or deleted. The wide email-date window is filtered
later by invoice date (NLap) in the aggregation step.
"""
from __future__ import annotations

import email
import imaplib
import re
import ssl
from datetime import date, datetime, timedelta
from email.header import decode_header
from email.message import Message
from typing import Iterable, Optional

from .classify import score_email
from .config import Settings
from .models import EmailCandidate

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def imap_date(d: date) -> str:
    """Format a date as IMAP expects, e.g. 05-Jan-2026."""
    return f"{d.day:02d}-{_MONTHS[d.month - 1]}-{d.year}"


def search_window(from_date: date, to_date: date, pad_before: int, pad_after: int):
    """Return (since, before) dates for IMAP SEARCH SINCE/BEFORE.

    ``before`` is exclusive, so we add one extra day past the padded end.
    """
    since = from_date - timedelta(days=pad_before)
    before = to_date + timedelta(days=pad_after) + timedelta(days=1)
    return since, before


def pick_all_mail(list_lines: Iterable[bytes]) -> Optional[str]:
    """Find the \\All special-use mailbox name from a LIST response."""
    for line in list_lines:
        s = line.decode("utf-8", "replace") if isinstance(line, (bytes, bytearray)) else str(line)
        if "\\All" in s:
            m = re.search(r'"([^"]+)"\s*$', s)
            if m:
                return m.group(1)
    return None


def detect_kinds_from_bodystructure(meta: str) -> tuple[bool, bool]:
    """Cheap attachment detection from a BODYSTRUCTURE metadata string."""
    low = meta.lower()
    return (".xml" in low, ".pdf" in low)


def extract_uid(meta: str) -> str:
    """The IMAP UID from a FETCH metadata line.

    The line leads with the message SEQUENCE number; the real UID follows
    "UID". We must use the UID (fetches use UID FETCH), never the seqno.
    """
    m = re.search(r"UID (\d+)", meta)
    if m:
        return m.group(1)
    m = re.match(r"(\d+) ", meta)
    return m.group(1) if m else ""


def _decode(s: Optional[str]) -> str:
    if not s:
        return ""
    out = []
    for txt, enc in decode_header(s):
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", "replace"))
        else:
            out.append(txt)
    return "".join(out)


class MailScanner:
    """Thin read-only IMAP client for scanning and fetching invoice emails."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.imap: Optional[imaplib.IMAP4_SSL] = None
        self.folder = "INBOX"

    def connect(self) -> None:
        self.imap = imaplib.IMAP4_SSL(
            self.s.imap_host, self.s.imap_port, ssl_context=ssl.create_default_context()
        )
        self.imap.login(self.s.imap_user, self.s.imap_password)
        typ, data = self.imap.list()
        all_mail = pick_all_mail(data) if typ == "OK" else None
        self.folder = all_mail or "INBOX"
        box = f'"{self.folder}"' if " " in self.folder else self.folder
        typ, _ = self.imap.select(box, readonly=True)
        if typ != "OK":
            self.folder = "INBOX"
            self.imap.select("INBOX", readonly=True)

    def scan(self, from_date: date, to_date: date) -> list[EmailCandidate]:
        """Scan the padded email window and score each message (read-only)."""
        assert self.imap is not None, "call connect() first"
        since, before = search_window(
            from_date, to_date, self.s.pad_before_days, self.s.pad_after_days
        )
        typ, data = self.imap.uid(
            "SEARCH", None, "SINCE", imap_date(since), "BEFORE", imap_date(before)
        )
        uids = data[0].split() if (typ == "OK" and data and data[0]) else []

        candidates: list[EmailCandidate] = []
        for chunk in _batches(uids, 300):
            uidset = b",".join(chunk).decode()
            typ, data = self.imap.uid(
                "FETCH", uidset,
                "(BODYSTRUCTURE INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT MESSAGE-ID)])",
            )
            if typ != "OK":
                continue
            for item in data:
                if not isinstance(item, tuple):
                    continue
                cand = self._candidate_from_fetch(item)
                if cand is not None:
                    candidates.append(cand)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _candidate_from_fetch(self, item) -> Optional[EmailCandidate]:
        meta = item[0].decode("utf-8", "replace")
        msg = email.message_from_bytes(item[1] if len(item) > 1 else b"")
        sender = _decode(msg.get("From", ""))
        subject = _decode(msg.get("Subject", ""))
        message_id = (msg.get("Message-ID", "") or "").strip()
        has_xml, has_pdf = detect_kinds_from_bodystructure(meta)
        uid = extract_uid(meta)
        internal = None
        dm = re.search(r'INTERNALDATE "(\d{2}-[A-Za-z]{3}-\d{4})', meta)
        if dm:
            try:
                internal = datetime.strptime(dm.group(1), "%d-%b-%Y").date()
            except ValueError:
                internal = None
        cand = score_email(
            sender=sender, subject=subject, has_xml=has_xml, has_pdf=has_pdf,
            has_link=False, cfg=self.s.classifier, uid=uid, message_id=message_id,
            internal_date=internal,
        )
        return cand if cand.bucket != "ignore" else None

    def fetch_message(self, uid: str) -> Message:
        """Fetch a full message (read-only, BODY.PEEK) for collection."""
        assert self.imap is not None, "call connect() first"
        typ, data = self.imap.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            raise RuntimeError(f"Cannot fetch uid {uid}")
        return email.message_from_bytes(data[0][1])

    def close(self) -> None:
        if self.imap is not None:
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None


def _batches(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
