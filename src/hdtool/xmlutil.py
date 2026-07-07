"""Namespace-agnostic XML helpers.

Vietnamese e-invoice issuers emit XML with varying namespaces (or none).
We match elements by their *local* tag name and ignore namespaces entirely,
so one parser handles many issuer formats.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional


def local(tag: str) -> str:
    """Strip a `{namespace}` prefix from an element tag."""
    return tag.rsplit("}", 1)[-1]


def find_first(elem: ET.Element, *local_names: str) -> Optional[ET.Element]:
    """First descendant (or self) whose local name matches any given name."""
    names = set(local_names)
    for e in elem.iter():
        if local(e.tag) in names:
            return e
    return None


def find_all(elem: ET.Element, *local_names: str) -> list[ET.Element]:
    """All descendants (or self) whose local name matches any given name."""
    names = set(local_names)
    return [e for e in elem.iter() if local(e.tag) in names]


def text(elem: Optional[ET.Element], *local_names: str, default=None) -> Optional[str]:
    """Trimmed text of the first matching descendant, else `default`."""
    if elem is None:
        return default
    e = find_first(elem, *local_names)
    if e is None or e.text is None:
        return default
    return e.text.strip()
