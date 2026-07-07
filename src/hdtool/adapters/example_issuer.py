"""TEMPLATE portal adapter — copy this to write a real one.

This file is a safe no-op scaffold, NOT a working adapter:
  * ``match_hints`` is empty and ``can_handle`` returns False, so it never
    claims a URL even if accidentally registered.
  * ``fetch`` raises NotImplementedError.
  * It is deliberately NOT registered (no ``register(...)`` call), so importing
    it changes nothing.

## To implement a real adapter (once you have a real issuer email sample)

1. Copy this file to e.g. ``sinvoice.py`` and rename the class.
2. Set ``name`` and ``match_hints`` to the issuer's portal host(s), e.g.
   ``["tracuu.sinvoice.com.vn", "sinvoice"]``.
3. In ``fetch``: open the tra-cứu URL (use ``requests``), submit the lookup code
   if required, find the XML/PDF download links on the page, download them, and
   return them as ``collect.Attachment`` objects (prefer XML).
4. Register it: at the bottom, ``from .base import register`` and
   ``register(SinvoiceAdapter())`` — OR register from a central place.
5. Write tests with a mocked HTTP layer (never hit the live portal in tests).
"""
from __future__ import annotations

from typing import Optional

from ..collect import Attachment


class ExampleIssuerAdapter:
    name = "example-template"
    match_hints: list[str] = []   # empty -> never matches a real URL

    def can_handle(self, url: str) -> bool:
        return any(h in url.lower() for h in self.match_hints)

    def fetch(self, url: str, code: Optional[str] = None) -> list[Attachment]:
        raise NotImplementedError(
            "Template adapter: copy this file and implement fetch() against a "
            "real issuer portal sample. See module docstring."
        )
