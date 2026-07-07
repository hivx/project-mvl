"""Track which invoice emails were already collected, so re-runs are idempotent.

Keyed by email Message-ID. Emails without a Message-ID cannot be deduped, so
they are always (re)collected rather than risk silently dropping them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_manifest(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_manifest(path, manifest: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def is_collected(manifest: dict, message_id: str) -> bool:
    return bool(message_id) and message_id in manifest


def mark_collected(manifest: dict, message_id: str, paths: dict) -> None:
    if not message_id:
        return
    manifest[message_id] = {k: str(v) for k, v in paths.items()}


def filter_uncollected(candidates: Iterable, manifest: dict):
    """Split candidates into (to_collect, skipped-already-collected)."""
    to_collect, skipped = [], []
    for c in candidates:
        if is_collected(manifest, c.message_id):
            skipped.append(c)
        else:
            to_collect.append(c)
    return to_collect, skipped
