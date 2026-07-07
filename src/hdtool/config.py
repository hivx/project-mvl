"""Load configuration from .env (secrets) and config/settings.yaml (behavior)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .classify import ClassifierConfig


@dataclass
class Account:
    """One IMAP mailbox to scan."""
    host: str
    port: int
    user: str
    password: str


@dataclass
class Settings:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    accounts: list[Account]
    buyer_msts: set[str]
    companies: dict[str, str]          # MST bên mua -> tên công ty (folder)
    classifier: ClassifierConfig
    pad_before_days: int
    pad_after_days: int
    data_dir: Path
    default_from: Optional[str] = None   # kỳ mặc định (ngày lập HĐ) khi không có --from
    default_to: Optional[str] = None


def parse_msts(raw: Optional[str]) -> set[str]:
    """Parse a comma-separated list of tax codes into a clean set."""
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _parse_accounts(env: dict) -> list[Account]:
    """Account 1 from IMAP_USER/IMAP_APP_PASSWORD, then IMAP_USER_2, _3, ...

    host/port default to the base IMAP_HOST/IMAP_PORT unless overridden per account.
    """
    base_host = env.get("IMAP_HOST", "imap.gmail.com")
    base_port = int(env.get("IMAP_PORT", "993"))
    accounts: list[Account] = []
    if env.get("IMAP_USER"):
        accounts.append(Account(base_host, base_port,
                                env.get("IMAP_USER", ""), env.get("IMAP_APP_PASSWORD", "")))
    n = 2
    while env.get(f"IMAP_USER_{n}"):
        accounts.append(Account(
            env.get(f"IMAP_HOST_{n}", base_host),
            int(env.get(f"IMAP_PORT_{n}", base_port)),
            env.get(f"IMAP_USER_{n}", ""),
            env.get(f"IMAP_APP_PASSWORD_{n}", ""),
        ))
        n += 1
    return accounts


def _build_companies(env: dict, cfg: dict) -> dict[str, str]:
    """Map buyer MST -> company folder name. Falls back to MIYANO_MST env."""
    companies = {str(k).strip(): str(v).strip()
                 for k, v in (cfg.get("companies") or {}).items() if str(k).strip()}
    if not companies:
        for mst in parse_msts(env.get("MIYANO_MST")):
            companies[mst] = "cong-ty"
    return companies


def build_settings(env: dict, cfg: dict, data_dir: Optional[Path] = None) -> Settings:
    companies_map = _build_companies(env, cfg)
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
        accounts=_parse_accounts(env),
        buyer_msts=set(companies_map),
        companies=companies_map,
        classifier=classifier,
        pad_before_days=int(cfg.get("pad_before_days", 15)),
        pad_after_days=int(cfg.get("pad_after_days", 45)),
        data_dir=data_dir or Path("data"),
        # YAML may parse an unquoted ISO date to a date object; coerce to str.
        default_from=str(cfg["default_from"]) if cfg.get("default_from") else None,
        default_to=str(cfg["default_to"]) if cfg.get("default_to") else None,
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
