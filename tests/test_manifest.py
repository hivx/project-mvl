"""Tests for the collect manifest (idempotent downloads)."""
from datetime import date

from hdtool.manifest import (
    load_manifest, save_manifest, is_collected, mark_collected, filter_uncollected,
)
from hdtool.models import EmailCandidate


def _cand(mid):
    return EmailCandidate(message_id=mid, uid="1", sender="x@sinvoice.vn",
                          subject="Hóa đơn", internal_date=date(2026, 6, 1),
                          score=5, bucket="certain")


def test_load_missing_returns_empty(tmp_path):
    assert load_manifest(tmp_path / "nope.json") == {}


def test_save_then_load_roundtrips(tmp_path):
    p = tmp_path / "m.json"
    m = {"<a@x>": {"xml": "/data/a.xml"}}
    save_manifest(p, m)
    assert load_manifest(p) == m


def test_is_collected_before_and_after_mark():
    m = {}
    assert is_collected(m, "<a@x>") is False
    mark_collected(m, "<a@x>", {"xml": "/data/a.xml"})
    assert is_collected(m, "<a@x>") is True


def test_mark_stores_paths():
    m = {}
    mark_collected(m, "<a@x>", {"xml": "/d/a.xml", "pdf": "/d/a.pdf"})
    assert m["<a@x>"]["xml"] == "/d/a.xml"
    assert m["<a@x>"]["pdf"] == "/d/a.pdf"


def test_blank_message_id_never_collected():
    m = {}
    assert is_collected(m, "") is False
    mark_collected(m, "", {"xml": "/d/a.xml"})   # no-op, cannot dedup without id
    assert is_collected(m, "") is False
    assert m == {}


def test_filter_uncollected_splits():
    m = {}
    mark_collected(m, "<already@x>", {"xml": "/d/a.xml"})
    cands = [_cand("<already@x>"), _cand("<new@x>"), _cand("")]
    to_collect, skipped = filter_uncollected(cands, m)
    assert [c.message_id for c in skipped] == ["<already@x>"]
    # new + blank-id both go to to_collect (blank can't be deduped)
    assert [c.message_id for c in to_collect] == ["<new@x>", ""]
