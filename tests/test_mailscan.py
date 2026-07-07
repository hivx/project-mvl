"""Tests for mailbox scan pure helpers (no network)."""
from datetime import date

from hdtool.mailscan import (
    imap_date, search_window, pick_all_mail, detect_kinds_from_bodystructure,
    extract_uid,
)


def test_imap_date_format():
    assert imap_date(date(2026, 1, 5)) == "05-Jan-2026"
    assert imap_date(date(2026, 12, 31)) == "31-Dec-2026"


def test_search_window_pads_both_sides():
    since, before = search_window(date(2026, 6, 1), date(2026, 6, 30),
                                  pad_before=15, pad_after=45)
    assert since == date(2026, 5, 17)      # from - 15d
    assert before == date(2026, 8, 15)     # to + 45d, +1 (BEFORE is exclusive)


def test_pick_all_mail_finds_special_use():
    lines = [
        rb'(\HasNoChildren) "/" "INBOX"',
        rb'(\HasChildren \Noselect) "/" "[Gmail]"',
        rb'(\All \HasNoChildren) "/" "[Gmail]/T&HqU-t c&HqM- th&AbA-"',
    ]
    assert pick_all_mail(lines) == "[Gmail]/T&HqU-t c&HqM- th&AbA-"


def test_pick_all_mail_none_when_absent():
    lines = [rb'(\HasNoChildren) "/" "INBOX"']
    assert pick_all_mail(lines) is None


def test_detect_kinds_from_bodystructure():
    meta = '123 (UID 123 BODYSTRUCTURE (("text" "plain") ("application" "xml" ("name" "hd.xml"))))'
    xml, pdf = detect_kinds_from_bodystructure(meta)
    assert xml is True
    assert pdf is False


def test_extract_uid_prefers_gmail_uid_over_seqno():
    # FETCH response leads with the SEQUENCE number; the real UID is after "UID".
    meta = '5 (UID 474 INTERNALDATE "06-Jul-2026 03:12:00 +0000" BODYSTRUCTURE (...))'
    assert extract_uid(meta) == "474"


def test_extract_uid_falls_back_to_leading_number():
    meta = '474 (BODYSTRUCTURE (...))'
    assert extract_uid(meta) == "474"


def test_extract_uid_empty_when_absent():
    assert extract_uid("(BODYSTRUCTURE (...))") == ""
