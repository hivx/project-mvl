"""Tests for CLI argument parsing and date resolution."""
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from hdtool import cli
from hdtool.cli import build_parser, resolve_period
from hdtool.config import build_settings

FIXTURES = Path(__file__).parent / "fixtures"


def _settings(default_from=None, default_to=None):
    cfg = {}
    if default_from:
        cfg["default_from"] = default_from
    if default_to:
        cfg["default_to"] = default_to
    return build_settings({"IMAP_USER": "a@x.vn"}, cfg)


def test_parser_report_with_output():
    args = build_parser().parse_args(
        ["report", "--from", "2026-06-01", "--to", "2026-06-30", "-o", "out.xlsx"]
    )
    assert args.command == "report"
    assert args.from_date == date(2026, 6, 1)
    assert args.to_date == date(2026, 6, 30)
    assert args.output == "out.xlsx"


def test_parser_report_company_flag():
    args = build_parser().parse_args(["report", "--company", "miyano"])
    assert args.company == "miyano"


def test_parser_report_company_defaults_none():
    args = build_parser().parse_args(["report"])
    assert args.company is None


def test_parser_report_format_flag():
    args = build_parser().parse_args(["report", "--format", "csv"])
    assert args.format == "csv"


def test_parser_report_format_default_xlsx():
    args = build_parser().parse_args(["report"])
    assert args.format == "xlsx"


def test_parser_scan():
    args = build_parser().parse_args(["scan", "--from", "2026-06-01", "--to", "2026-06-30"])
    assert args.command == "scan"
    assert args.from_date == date(2026, 6, 1)


def test_parser_run_and_collect_exist():
    for cmd in ("collect", "run", "reorganize"):
        args = build_parser().parse_args([cmd, "--from", "2026-06-01", "--to", "2026-06-30"])
        assert args.command == cmd


def test_is_old_period_dir():
    from hdtool.cli import _is_old_period_dir
    assert _is_old_period_dir("2026-06") is True
    assert _is_old_period_dir("unknown-period") is False
    assert _is_old_period_dir("miyano") is False
    assert _is_old_period_dir("_chua-ro-cong-ty") is False


def test_dir_keys_subset_guards_data_loss(tmp_path):
    import shutil
    from hdtool.cli import _dir_keys_subset
    from hdtool.parse_xml import parse_invoice_xml
    fixtures = __import__("pathlib").Path(__file__).parent / "fixtures"
    old = tmp_path / "2026-06"
    old.mkdir()
    shutil.copy(fixtures / "inv_10pct.xml", old / "a.xml")
    key = parse_invoice_xml((fixtures / "inv_10pct.xml").read_bytes()).dedup_key
    # every invoice in the old dir is present in the new structure -> safe to remove
    assert _dir_keys_subset(old, {key}) is True
    # its invoice is NOT in the new structure -> unsafe, must keep
    assert _dir_keys_subset(old, set()) is False


def test_reorganize_keeps_old_dir_when_not_recollected(tmp_path, monkeypatch):
    # Reproduces the CRITICAL scenario: collect re-downloads nothing, so the old
    # invoice must SURVIVE (never delete an old dir whose invoice isn't in the
    # new tree), and the manifest must not be lost.
    data = tmp_path / "data"
    old = data / "2026-06" / "abc"
    old.mkdir(parents=True)
    shutil.copy(FIXTURES / "inv_10pct.xml", old / "a.xml")
    (data / ".collected.json").write_text('{"m":{"xml":"x"}}')
    settings = build_settings({"IMAP_USER": "x@y"}, {}, data_dir=data)
    monkeypatch.setattr(cli, "cmd_collect", lambda s, a: 0)   # simulate 0 re-downloads
    args = SimpleNamespace(from_date=date(2026, 6, 1), to_date=date(2026, 6, 30),
                           include_suspect=False)
    cli.cmd_reorganize(settings, args)
    assert (old / "a.xml").exists()               # invoice NOT lost
    assert (data / ".collected.json").exists()     # manifest preserved


def test_parser_dates_optional_for_report():
    # dates are optional at parse time now; resolve_period enforces them later
    args = build_parser().parse_args(["report"])
    assert args.from_date is None and args.to_date is None


def test_parser_include_suspect_flag():
    args = build_parser().parse_args(
        ["collect", "--from", "2026-06-01", "--to", "2026-06-30", "--include-suspect"]
    )
    assert args.include_suspect is True


def test_parser_dates_optional_now():
    # dates are optional; they can come from config instead
    args = build_parser().parse_args(["scan"])
    assert args.from_date is None
    assert args.to_date is None


def test_resolve_period_prefers_cli_args():
    fd, td = resolve_period(date(2026, 1, 1), date(2026, 1, 31),
                            _settings("2026-06-01", "2026-06-30"))
    assert (fd, td) == (date(2026, 1, 1), date(2026, 1, 31))


def test_resolve_period_falls_back_to_config():
    fd, td = resolve_period(None, None, _settings("2026-06-01", "2026-06-30"))
    assert (fd, td) == (date(2026, 6, 1), date(2026, 6, 30))


def test_resolve_period_errors_when_missing():
    with pytest.raises(SystemExit):
        resolve_period(None, None, _settings())
