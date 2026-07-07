"""Tests for the example/template adapter (T11b scaffold).

The template must be a safe no-op: it conforms to the PortalAdapter interface,
never matches a real URL, is NOT auto-registered, and refuses to fetch (so it
can't be mistaken for a working adapter). A real adapter is written by copying
it once we have a real issuer sample.
"""
import pytest

from hdtool.adapters import PortalAdapter, get_adapter, clear_adapters
from hdtool.adapters.example_issuer import ExampleIssuerAdapter


@pytest.fixture(autouse=True)
def _clean():
    clear_adapters()
    yield
    clear_adapters()


def test_template_conforms_to_interface():
    a = ExampleIssuerAdapter()
    assert isinstance(a.name, str)
    assert isinstance(a.match_hints, list)
    assert callable(a.can_handle)
    assert callable(a.fetch)
    assert isinstance(a, PortalAdapter)


def test_template_never_matches_a_real_url():
    a = ExampleIssuerAdapter()
    assert a.can_handle("https://tracuu.sinvoice.com.vn/x") is False


def test_template_fetch_refuses():
    a = ExampleIssuerAdapter()
    with pytest.raises(NotImplementedError):
        a.fetch("https://tracuu.example.vn/x", code="ABC")


def test_importing_template_does_not_register_it():
    # Importing the module must not populate the registry (safe default).
    assert get_adapter("https://tracuu.sinvoice.com.vn/x") is None
