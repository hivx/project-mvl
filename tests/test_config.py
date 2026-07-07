"""Tests for configuration loading and MST parsing."""
from pathlib import Path

from hdtool.config import parse_msts, build_settings, load_settings


def test_parse_msts_splits_and_trims():
    assert parse_msts("0301234567, 0312345678") == {"0301234567", "0312345678"}


def test_parse_msts_empty_is_empty_set():
    assert parse_msts("") == set()
    assert parse_msts(None) == set()


def test_parse_msts_dedupes_and_ignores_blanks():
    assert parse_msts("0301234567,,0301234567 , ") == {"0301234567"}


def test_build_settings_from_env_and_cfg():
    env = {
        "IMAP_HOST": "imap.gmail.com",
        "IMAP_PORT": "993",
        "IMAP_USER": "info@miyano.com.vn",
        "IMAP_APP_PASSWORD": "secret pass word here",
        "MIYANO_MST": "0301234567",
    }
    cfg = {
        "pad_before_days": 10,
        "pad_after_days": 40,
        "issuer_domains": ["sinvoice", "vnpt"],
        "keywords": ["hóa đơn"],
        "whitelist_senders": ["ketoan@x.vn"],
        "certain_threshold": 5,
        "suspect_threshold": 2,
    }
    s = build_settings(env, cfg)
    assert s.imap_host == "imap.gmail.com"
    assert s.imap_port == 993
    assert s.imap_user == "info@miyano.com.vn"
    assert s.imap_password == "secret pass word here"
    assert s.buyer_msts == {"0301234567"}
    assert s.pad_before_days == 10
    assert s.classifier.issuer_domains == ["sinvoice", "vnpt"]
    assert s.classifier.whitelist_senders == ["ketoan@x.vn"]


def test_build_settings_single_account_backward_compat():
    env = {"IMAP_USER": "a@x.vn", "IMAP_APP_PASSWORD": "pw a"}
    s = build_settings(env, {})
    assert len(s.accounts) == 1
    assert s.accounts[0].user == "a@x.vn"
    assert s.accounts[0].password == "pw a"
    # legacy fields still populated (first account)
    assert s.imap_user == "a@x.vn"


def test_build_settings_multiple_accounts():
    env = {
        "IMAP_HOST": "imap.gmail.com", "IMAP_PORT": "993",
        "IMAP_USER": "a@x.vn", "IMAP_APP_PASSWORD": "pw a a a",
        "IMAP_USER_2": "b@y.vn", "IMAP_APP_PASSWORD_2": "pw b b b",
        "IMAP_USER_3": "c@z.vn", "IMAP_APP_PASSWORD_3": "pw c",
    }
    s = build_settings(env, {})
    assert [a.user for a in s.accounts] == ["a@x.vn", "b@y.vn", "c@z.vn"]
    assert s.accounts[1].password == "pw b b b"   # app passwords keep spaces
    assert all(a.host == "imap.gmail.com" and a.port == 993 for a in s.accounts)


def test_build_settings_parses_companies_map():
    s = build_settings({"IMAP_USER": "a@x"},
                       {"companies": {"0109529507": "miyano", "0108186705": "medcons"}})
    assert s.companies == {"0109529507": "miyano", "0108186705": "medcons"}
    # buyer filter keeps ALL our companies
    assert s.buyer_msts == {"0109529507", "0108186705"}


def test_companies_falls_back_to_miyano_mst_env():
    s = build_settings({"IMAP_USER": "a@x", "MIYANO_MST": "0109529507"}, {})
    assert "0109529507" in s.buyer_msts
    # legacy single MST gets a default company name
    assert s.companies.get("0109529507")


def test_build_settings_reads_default_period():
    s = build_settings({"IMAP_USER": "a@x.vn", "IMAP_APP_PASSWORD": "p"},
                       {"default_from": "2026-06-01", "default_to": "2026-06-30"})
    assert s.default_from == "2026-06-01"
    assert s.default_to == "2026-06-30"


def test_default_period_absent_is_none():
    s = build_settings({"IMAP_USER": "a@x.vn"}, {})
    assert s.default_from is None
    assert s.default_to is None


def test_load_settings_reads_repo_defaults():
    root = Path(__file__).resolve().parent.parent
    s = load_settings(root, env={"IMAP_USER": "x@y.vn", "IMAP_APP_PASSWORD": "p"})
    # values come from config/settings.yaml checked into the repo
    assert "sinvoice" in s.classifier.issuer_domains
    assert s.pad_after_days == 45
