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
from .fast_einvoice import FastEinvoiceAdapter
from .vnpt_invoice import VnptInvoiceAdapter

# Live adapters (proven against real portals):
#  * einvoice.com.vn — GET page + POST /tai-ve-hoa-don -> zip (saigoncoop, …).
#  * vnpt-invoice.com.vn — email link invoice/getinvoice?token= -> XML directly.
#  * einvoice.fast.com.vn — email link index.aspx?type=2&…&hash= -> XML directly.
register(EinvoiceComVnAdapter())
register(VnptInvoiceAdapter())
register(FastEinvoiceAdapter())

__all__ = [
    "PortalAdapter",
    "register",
    "clear_adapters",
    "get_adapter",
    "fetch_via_portal",
    "try_fetch_links",
    "EinvoiceComVnAdapter",
    "VnptInvoiceAdapter",
    "FastEinvoiceAdapter",
]
