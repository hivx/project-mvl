"""Tests for CLI argument parsing and date resolution."""
from datetime import date

import pytest

from hdtool.cli import build_parser, resolve_period
from hdtool.config import build_settings


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


def test_parser_scan():
    args = build_parser().parse_args(["scan", "--from", "2026-06-01", "--to", "2026-06-30"])
    assert args.command == "scan"
    assert args.from_date == date(2026, 6, 1)


def test_parser_run_and_collect_exist():
    for cmd in ("collect", "run"):
        args = build_parser().parse_args([cmd, "--from", "2026-06-01", "--to", "2026-06-30"])
        assert args.command == cmd


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
