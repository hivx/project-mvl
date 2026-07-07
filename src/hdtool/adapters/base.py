"""Portal-adapter contract and registry (T11a).

Concrete issuer adapters (Viettel/sinvoice, VNPT, MISA...) are added only once
we have real emails to survey — the registry ships EMPTY. With no adapter for a
link, callers fall back to the "cần tải tay" list; the pipeline never breaks.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..collect import Attachment


@runtime_checkable
class PortalAdapter(Protocol):
    """Fetch invoice files from an issuer's tra-cứu portal."""
    name: str
    match_hints: list[str]

    def can_handle(self, url: str) -> bool: ...

    def fetch(self, url: str, code: Optional[str] = None) -> list[Attachment]: ...


_REGISTRY: list = []


def register(adapter) -> None:
    _REGISTRY.append(adapter)


def clear_adapters() -> None:
    _REGISTRY.clear()


def get_adapter(url: str):
    """First registered adapter that claims the URL, else None."""
    for adapter in _REGISTRY:
        try:
            if adapter.can_handle(url):
                return adapter
        except Exception:
            continue
    return None


def fetch_via_portal(url: str, code: Optional[str] = None):
    """Fetch files for a single URL, or None if no adapter handles it."""
    adapter = get_adapter(url)
    if adapter is None:
        return None
    return adapter.fetch(url, code)


def try_fetch_links(links, code: Optional[str] = None) -> list:
    """Try each link; return files from the first adapter that succeeds, else []."""
    for url in links:
        files = fetch_via_portal(url, code)
        if files:
            return files
    return []
