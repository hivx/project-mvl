"""Tests for CLI argument parsing."""
from datetime import date

import pytest

from hdtool.cli import build_parser


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


def test_parser_requires_dates():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["report"])


def test_parser_include_suspect_flag():
    args = build_parser().parse_args(
        ["collect", "--from", "2026-06-01", "--to", "2026-06-30", "--include-suspect"]
    )
    assert args.include_suspect is True
