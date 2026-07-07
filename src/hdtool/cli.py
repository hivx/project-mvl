"""Command-line interface: scan / collect / report / run."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from .collect import extract_links, has_kind, invoice_files, save_invoice_files
from .config import Settings, load_settings
from .parse_xml import InvoiceParseError, parse_invoice_xml
from .pipeline import build_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _isodate(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Ngày không hợp lệ (cần YYYY-MM-DD): {s}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hdtool", description="Tổng hợp hóa đơn điện tử VN qua email ra Excel"
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_period(sp):
        sp.add_argument("--from", dest="from_date", type=_isodate, required=True,
                        help="Ngày lập hóa đơn từ (YYYY-MM-DD)")
        sp.add_argument("--to", dest="to_date", type=_isodate, required=True,
                        help="Ngày lập hóa đơn đến (YYYY-MM-DD)")

    sp_scan = sub.add_parser("scan", help="Dò email hóa đơn (chỉ đọc), không tải")
    add_period(sp_scan)

    sp_collect = sub.add_parser("collect", help="Tải file hóa đơn về local")
    add_period(sp_collect)
    sp_collect.add_argument("--include-suspect", action="store_true",
                            help="Tải cả email rổ 'nghi ngờ', không chỉ 'chắc chắn'")

    sp_report = sub.add_parser("report", help="Parse + tổng hợp ra Excel")
    add_period(sp_report)
    sp_report.add_argument("-o", "--output", default=None, help="File Excel xuất ra")
    sp_report.add_argument("--source", default=None, help="Thư mục chứa XML (mặc định data/)")

    sp_run = sub.add_parser("run", help="Chạy cả chuỗi scan → collect → report")
    add_period(sp_run)
    sp_run.add_argument("--include-suspect", action="store_true")
    sp_run.add_argument("-o", "--output", default=None)

    return p


def _load_settings() -> Settings:
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except Exception:
        pass
    return load_settings(PROJECT_ROOT)


def _default_output(from_date: date, to_date: date, settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / f"bang-ke-{from_date}_{to_date}.xlsx"


def cmd_scan(settings: Settings, args) -> int:
    from .mailscan import MailScanner
    scanner = MailScanner(settings)
    scanner.connect()
    print(f"Đã kết nối, quét thư mục: {scanner.folder}")
    try:
        cands = scanner.scan(args.from_date, args.to_date)
    finally:
        scanner.close()
    certain = [c for c in cands if c.bucket == "certain"]
    suspect = [c for c in cands if c.bucket == "suspect"]
    print(f"\n== CHẮC CHẮN là hóa đơn: {len(certain)} ==")
    for c in certain:
        print(f"  [{c.score}] {c.sender[:40]:40s} | {c.subject[:60]}")
    print(f"\n== NGHI NGỜ (cần duyệt): {len(suspect)} ==")
    for c in suspect:
        print(f"  [{c.score}] {c.sender[:40]:40s} | {c.subject[:60]}  -> {', '.join(c.reasons)}")
    if not certain and not suspect:
        print("Không tìm thấy email hóa đơn nào trong cửa sổ thời gian này.")
    return 0


def cmd_collect(settings: Settings, args) -> int:
    from .mailscan import MailScanner
    scanner = MailScanner(settings)
    scanner.connect()
    try:
        cands = scanner.scan(args.from_date, args.to_date)
        wanted = [c for c in cands if c.bucket == "certain"
                  or (args.include_suspect and c.bucket == "suspect")]
        print(f"Sẽ tải {len(wanted)} email hóa đơn...")
        need_manual = []
        saved_count = 0
        for c in wanted:
            msg = scanner.fetch_message(c.uid)
            files = invoice_files(msg)
            if not has_kind(files, "xml") and not has_kind(files, "pdf"):
                links = extract_links(msg, settings.classifier.issuer_domains + ["tracuu", "hoadon"])
                need_manual.append((c, links))
                continue
            supplier, ngay = _peek_supplier_date(files, c)
            saved = save_invoice_files(files, settings.data_dir, ngay, supplier)
            saved_count += 1
            print(f"  ✓ {c.subject[:50]} -> {saved.get('xml') or saved.get('pdf')}")
    finally:
        scanner.close()
    if need_manual:
        print(f"\n⚠ {len(need_manual)} hóa đơn chỉ có LINK (cần adapter / tải tay):")
        for c, links in need_manual:
            print(f"  - {c.sender} | {c.subject[:50]} | {links or 'không thấy link'}")
    print(f"\nĐã tải {saved_count} hóa đơn có file.")
    return 0


def _peek_supplier_date(files, candidate):
    """Best-effort supplier name + invoice date from the XML for foldering."""
    for f in files:
        if f.kind == "xml":
            try:
                inv = parse_invoice_xml(f.data)
                return (inv.ten_ban or "khong-ro", inv.ngay_lap)
            except InvoiceParseError:
                pass
    return (candidate.sender.split("@")[-1] if candidate.sender else "khong-ro", candidate.internal_date)


def cmd_report(settings: Settings, args) -> int:
    source = Path(args.source) if args.source else settings.data_dir
    out = Path(args.output) if args.output else _default_output(args.from_date, args.to_date, settings)
    if not source.exists():
        print(f"Không tìm thấy thư mục nguồn: {source}. Hãy chạy 'collect' trước.")
        return 1
    result, skipped = build_report(source, args.from_date, args.to_date,
                                   settings.buyer_msts, out)
    print(f"Đã xuất: {out}")
    print(f"  Hóa đơn trong kỳ: {len(result.invoices)}")
    print(f"  Tổng tiền chưa thuế: {result.total_chua_thue:,}")
    print(f"  Tổng tiền thuế    : {result.total_thue:,}")
    print(f"  Tổng thanh toán   : {result.total_thanh_toan:,}")
    if not settings.buyer_msts:
        print("  (Chưa cấu hình MIYANO_MST → không lọc mua-vào, chỉ gắn cờ.)")
    if skipped:
        print(f"  Bỏ qua/cần xem lại: {len(skipped)} (xem sheet 'Bỏ qua')")
    return 0


def cmd_run(settings: Settings, args) -> int:
    rc = cmd_collect(settings, args)
    if rc != 0:
        return rc
    report_args = argparse.Namespace(
        from_date=args.from_date, to_date=args.to_date,
        output=getattr(args, "output", None), source=None,
    )
    return cmd_report(settings, report_args)


_COMMANDS = {"scan": cmd_scan, "collect": cmd_collect, "report": cmd_report, "run": cmd_run}


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = _load_settings()
    return _COMMANDS[args.command](settings, args)


if __name__ == "__main__":
    sys.exit(main())
