"""Load configuration from .env (secrets) and config/settings.yaml (behavior)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .classify import ClassifierConfig


@dataclass
class Settings:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    buyer_msts: set[str]
    classifier: ClassifierConfig
    pad_before_days: int
    pad_after_days: int
    data_dir: Path


def parse_msts(raw: Optional[str]) -> set[str]:
    """Parse a comma-separated list of tax codes into a clean set."""
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def build_settings(env: dict, cfg: dict, data_dir: Optional[Path] = None) -> Settings:
    classifier = ClassifierConfig(
        issuer_domains=list(cfg.get("issuer_domains", [])),
        keywords=list(cfg.get("keywords", [])),
        whitelist_senders=list(cfg.get("whitelist_senders", [])),
        certain_threshold=int(cfg.get("certain_threshold", 5)),
        suspect_threshold=int(cfg.get("suspect_threshold", 2)),
    )
    return Settings(
        imap_host=env.get("IMAP_HOST", "imap.gmail.com"),
        imap_port=int(env.get("IMAP_PORT", "993")),
        imap_user=env.get("IMAP_USER", ""),
        imap_password=env.get("IMAP_APP_PASSWORD", ""),
        buyer_msts=parse_msts(env.get("MIYANO_MST")),
        classifier=classifier,
        pad_before_days=int(cfg.get("pad_before_days", 15)),
        pad_after_days=int(cfg.get("pad_after_days", 45)),
        data_dir=data_dir or Path("data"),
    )


def load_settings(project_root: Path, env: Optional[dict] = None) -> Settings:
    """Load .env + config/settings.yaml under ``project_root``.

    ``env`` overrides os.environ (useful for tests). Real runs pass None and we
    read the process environment (populated from .env by the CLI).
    """
    cfg_path = project_root / "config" / "settings.yaml"
    cfg = {}
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    environ = env if env is not None else os.environ
    return build_settings(environ, cfg, data_dir=project_root / "data")
