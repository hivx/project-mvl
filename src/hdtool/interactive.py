"""Interactive menu: chạy lên → hỏi ngày, công ty, định dạng → tải + tổng hợp.

Tách phần *hỏi/parse* (``prompt_options`` + các helper thuần, tiêm ``input_fn``/
``out`` để test không cần stdin) khỏi phần *thực thi* (``run_interactive`` gọi
collect → build_report → write_report). Không giữ số liệu ở đây; mọi con số vẫn
đến từ XML qua pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Callable, Optional

from .config import Settings

@dataclass
class Choices:
    """Người dùng đã chọn gì ở menu."""
    from_date: date
    to_date: date
    company: str          # tên công ty đã validate (miyano/medcons)
    fmt: str              # "xlsx" | "csv"
    include_suspect: bool = True


def _ask_date(label: str, default: Optional[str], input_fn, out) -> date:
    hint = f" [{default}]" if default else ""
    while True:
        raw = input_fn(f"{label}{hint} (YYYY-MM-DD): ").strip()
        if not raw and default:
            raw = default
        try:
            return date.fromisoformat(raw)
        except ValueError:
            out(f"  ✗ Ngày không hợp lệ: '{raw}'. Nhập lại dạng YYYY-MM-DD.")


def _ask_company(companies: dict, input_fn, out) -> str:
    names = sorted(set(companies.values()))
    if not names:
        raise SystemExit(
            "Chưa cấu hình công ty nào trong config/settings.yaml (mục companies).")
    while True:
        out("Công ty nhận hóa đơn:")
        for i, n in enumerate(names, 1):
            out(f"  {i}) {n}")
        raw = input_fn(f"Chọn [1-{len(names)}] (mặc định 1): ").strip()
        if not raw:
            return names[0]
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            return names[int(raw) - 1]
        if raw in names:                      # cho gõ thẳng tên công ty
            return raw
        out(f"  ✗ Lựa chọn không hợp lệ: '{raw}'.")


def _ask_format(input_fn, out) -> str:
    while True:
        out("Định dạng xuất:  1) Excel (.xlsx)   2) CSV")
        raw = input_fn("Chọn [1-2] (mặc định 1): ").strip()
        if not raw or raw == "1":
            return "xlsx"
        if raw == "2":
            return "csv"
        out(f"  ✗ Lựa chọn không hợp lệ: '{raw}'.")


def prompt_options(settings: Settings, input_fn: Callable = input,
                   out: Callable = print) -> Choices:
    """Hỏi ngày / công ty / định dạng và trả về ``Choices`` đã validate."""
    out("=== hdtool — Tổng hợp hóa đơn điện tử ===")
    fd = _ask_date("Từ ngày", settings.default_from, input_fn, out)
    td = _ask_date("Đến ngày", settings.default_to, input_fn, out)
    if td < fd:
        out("  ⚠ 'Đến ngày' nhỏ hơn 'Từ ngày' — đảo lại cho đúng.")
        fd, td = td, fd
    company = _ask_company(settings.companies, input_fn, out)
    fmt = _ask_format(input_fn, out)
    return Choices(from_date=fd, to_date=td, company=company, fmt=fmt)


def _output_path(settings: Settings, ch: Choices):
    ext = "csv" if ch.fmt == "csv" else "xlsx"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / f"bang-ke-{ch.company}-{ch.from_date}_{ch.to_date}.{ext}"


def _default_execute(settings: Settings, ch: Choices, out_path, out) -> int:
    """Tải hóa đơn (IMAP readonly) rồi xuất bảng kê cho công ty đã chọn."""
    from . import cli  # lazy: tránh vòng import (cli -> interactive khi chạy menu)
    args = SimpleNamespace(
        from_date=ch.from_date, to_date=ch.to_date,
        include_suspect=ch.include_suspect,
        company=ch.company, format=ch.fmt,
        output=str(out_path), source=None,
    )
    out(f"\n→ Kết nối hộp thư (chỉ đọc), tải hóa đơn {ch.from_date} … {ch.to_date}")
    rc = cli.cmd_collect(settings, args)
    if rc != 0:
        return rc
    # Chạy auto hết: thử tải nốt hóa đơn chỉ-có-link (kể cả dòng bạn vừa điền mã
    # tay vào sổ) trước khi tổng hợp. Cổng lỗi không chặn việc ra bảng kê.
    out("→ Thử tải nốt hóa đơn chỉ có link tra cứu…")
    cli.cmd_ncc(settings, SimpleNamespace(tai=True))
    out(f"→ Tổng hợp cho công ty '{ch.company}', xuất {ch.fmt.upper()}…")
    return cli.cmd_report(settings, args)


def run_interactive(settings: Settings, input_fn: Callable = input,
                    out: Callable = print, execute: Optional[Callable] = None) -> int:
    """Chạy toàn bộ menu: hỏi → tải → tổng hợp. ``execute`` tiêm được để test."""
    ch = prompt_options(settings, input_fn=input_fn, out=out)
    out_path = _output_path(settings, ch)
    return (execute or _default_execute)(settings, ch, out_path, out)
