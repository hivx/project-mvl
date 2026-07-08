"""Portal adapters. Concrete adapters registered here once a real issuer works."""
from .base import (
    PortalAdapter,
    register,
    clear_adapters,
    get_adapter,
    fetch_via_portal,
    try_fetch_links,
)
from .einvoice_com_vn import EinvoiceComVnAdapter

# Live adapters (proven against real portals). einvoice.com.vn: HTTP download,
# no captcha — covers saigoncoop and other <company>.einvoice.com.vn issuers.
register(EinvoiceComVnAdapter())

__all__ = [
    "PortalAdapter",
    "register",
    "clear_adapters",
    "get_adapter",
    "fetch_via_portal",
    "try_fetch_links",
    "EinvoiceComVnAdapter",
]
