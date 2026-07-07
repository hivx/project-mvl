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


def test_load_settings_reads_repo_defaults():
    root = Path(__file__).resolve().parent.parent
    s = load_settings(root, env={"IMAP_USER": "x@y.vn", "IMAP_APP_PASSWORD": "p"})
    # values come from config/settings.yaml checked into the repo
    assert "sinvoice" in s.classifier.issuer_domains
    assert s.pad_after_days == 45
