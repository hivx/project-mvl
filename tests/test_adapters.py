"""Tests for the portal-adapter registry & contract (T11a).

The registry is empty by default in production, so link-only invoices fall back
to "cần tải tay". A concrete issuer adapter is only added once we have real
emails to survey. These tests use a dummy adapter to prove the dispatch works.
"""
import pytest

from hdtool.collect import Attachment
from hdtool.adapters import (
    register, clear_adapters, get_adapter, fetch_via_portal, try_fetch_links,
)


class DummyAdapter:
    name = "dummy-sinvoice"
    match_hints = ["sinvoice"]

    def can_handle(self, url):
        return any(h in url.lower() for h in self.match_hints)

    def fetch(self, url, code=None):
        return [Attachment("hd.xml", "xml", b"<HDon></HDon>")]


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_adapters()
    yield
    clear_adapters()


def test_empty_registry_returns_none():
    assert get_adapter("https://tracuu.sinvoice.com.vn/x") is None
    assert fetch_via_portal("https://tracuu.sinvoice.com.vn/x") is None
    assert try_fetch_links(["https://tracuu.sinvoice.com.vn/x"]) == []


def test_register_and_get_adapter_by_url():
    register(DummyAdapter())
    assert get_adapter("https://tracuu.sinvoice.com.vn/x").name == "dummy-sinvoice"
    assert get_adapter("https://other.example.com/x") is None


def test_fetch_via_portal_uses_matching_adapter():
    register(DummyAdapter())
    files = fetch_via_portal("https://tracuu.sinvoice.com.vn/x")
    assert files and files[0].kind == "xml"


def test_try_fetch_links_returns_first_match():
    register(DummyAdapter())
    files = try_fetch_links([
        "https://no.example.com/a",
        "https://sinvoice.com.vn/b",
    ])
    assert files and files[0].kind == "xml"


def test_try_fetch_links_empty_when_no_match():
    register(DummyAdapter())
    assert try_fetch_links(["https://no.example.com/a"]) == []


def test_adapter_exception_is_isolated():
    class Boom:
        name = "boom"
        match_hints = ["boom"]
        def can_handle(self, url):
            raise RuntimeError("boom")
        def fetch(self, url, code=None):
            return []
    register(Boom())
    register(DummyAdapter())
    # Boom raising in can_handle must not break dispatch to the good adapter
    assert get_adapter("https://sinvoice.com.vn/x").name == "dummy-sinvoice"
