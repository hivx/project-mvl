"""Portal adapters. Registry ships empty; concrete adapters added per real issuer."""
from .base import (
    PortalAdapter,
    register,
    clear_adapters,
    get_adapter,
    fetch_via_portal,
    try_fetch_links,
)

__all__ = [
    "PortalAdapter",
    "register",
    "clear_adapters",
    "get_adapter",
    "fetch_via_portal",
    "try_fetch_links",
]
