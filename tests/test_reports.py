"""Tests for exporting the scan candidate/suspect list to CSV."""
import csv
from datetime import date

from hdtool.models import EmailCandidate
from hdtool.reports import write_candidates_csv, CANDIDATE_HEADERS


def _cand(bucket="certain", score=5, reasons=None, sender="x@sinvoice.com.vn",
          subject="Hóa đơn GTGT", d=date(2026, 7, 2), has_xml=True, has_pdf=False):
    return EmailCandidate(
        message_id="<a@x>", uid="1", sender=sender, subject=subject,
        internal_date=d, score=score, reasons=reasons or ["Có file XML đính kèm"],
        has_xml=has_xml, has_pdf=has_pdf, bucket=bucket,
    )


def _read(path):
    return list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))


def test_writes_header_and_one_row(tmp_path):
    p = write_candidates_csv([_cand()], tmp_path / "c.csv")
    assert p.exists()
    rows = _read(p)
    assert rows[0] == CANDIDATE_HEADERS
    assert rows[1][0] == "certain"
    assert rows[1][1] == "5"
    assert rows[1][2] == "x@sinvoice.com.vn"
    assert "XML" in rows[1][7]


def test_empty_writes_header_only(tmp_path):
    p = write_candidates_csv([], tmp_path / "c.csv")
    assert len(_read(p)) == 1


def test_reasons_joined_and_missing_date_blank(tmp_path):
    c = _cand(bucket="suspect", score=3, reasons=["lý do A", "lý do B"], d=None)
    rows = _read(write_candidates_csv([c], tmp_path / "c.csv"))
    assert rows[1][7] == "lý do A; lý do B"
    assert rows[1][4] == ""


def test_bool_flags_rendered(tmp_path):
    rows = _read(write_candidates_csv([_cand(has_xml=True, has_pdf=False)],
                                      tmp_path / "c.csv"))
    assert rows[1][5] == "x"   # XML column
    assert rows[1][6] == ""    # PDF column


def test_source_account_column(tmp_path):
    c = _cand()
    c.account = "info@miyano.com.vn"
    rows = _read(write_candidates_csv([c], tmp_path / "c.csv"))
    assert "Hộp thư" in rows[0]
    idx = rows[0].index("Hộp thư")
    assert rows[1][idx] == "info@miyano.com.vn"
