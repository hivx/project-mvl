"""Tests for the collect manifest (idempotent downloads)."""
from datetime import date

from hdtool.manifest import (
    load_manifest, save_manifest, is_collected, mark_collected, filter_uncollected,
    tieu_de_da_tai,
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


def test_email_chi_luu_duoc_zip_thi_CHUA_coi_la_da_tai():
    """Zip mã hóa chưa giải nén không phải là hóa đơn -> phải tải lại để thử ghép
    mật khẩu, nếu không những HĐ SMBC sẽ mắc kẹt vĩnh viễn trong manifest."""
    m = {}
    mark_collected(m, "m-zip", {"zip": "data/_chua-ro-cong-ty/2026-06/x/invoice.zip"})
    assert is_collected(m, "m-zip") is False


def test_email_co_xml_van_coi_la_da_tai():
    m = {}
    mark_collected(m, "m-xml", {"xml": "data/miyano/2026-06/x/hd.xml"})
    assert is_collected(m, "m-xml") is True


def test_email_co_zip_va_xml_thi_da_tai():
    m = {}
    mark_collected(m, "m2", {"zip": "a.zip", "xml": "b.xml"})
    assert is_collected(m, "m2") is True


def test_manifest_luu_tieu_de_de_nhan_ban_forward_trung():
    """Hóa đơn đến bằng đính kèm KHÔNG có dòng trong sổ, nên tiêu đề phải lưu ở
    manifest thì bản Re:/Fwd: các lần chạy sau mới nhận ra là bản sao."""
    m = {}
    mark_collected(m, "m1", {"xml": "data/miyano/2026-06/x/hd.xml"},
                   tieu_de="ABC gửi hóa đơn 123")
    assert tieu_de_da_tai(m) == {"ABC gửi hóa đơn 123": "data/miyano/2026-06/x/hd.xml"}


def test_khoa_phu_khong_lam_hong_kiem_tra_zip_only():
    m = {}
    mark_collected(m, "m-zip", {"zip": "x.zip"}, tieu_de="SMBC")
    assert is_collected(m, "m-zip") is False      # vẫn phải là "chưa tải"
