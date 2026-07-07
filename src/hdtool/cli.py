"""Command-line interface: scan / collect / report / run."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from .adapters import try_fetch_links
from .collect import extract_links, invoice_dir, invoice_files, save_invoice_files
from .config import Settings, load_settings
from .manifest import filter_uncollected, load_manifest, mark_collected, save_manifest
from .parse_xml import InvoiceParseError, parse_invoice_xml
from .pipeline import build_report
from .reports import write_candidates_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _isodate(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Ngày không hợp lệ (cần YYYY-MM-DD): {s}")


def _cfg_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise SystemExit(f"Ngày trong settings.yaml không hợp lệ (cần YYYY-MM-DD): {s}")


def resolve_period(from_arg, to_arg, settings: "Settings"):
    """CLI --from/--to win; otherwise fall back to default_from/default_to config."""
    fd = from_arg or _cfg_date(settings.default_from)
    td = to_arg or _cfg_date(settings.default_to)
    if fd is None or td is None:
        raise SystemExit(
            "Thiếu khoảng ngày: truyền --from/--to, hoặc đặt default_from/default_to "
            "trong config/settings.yaml"
        )
    return fd, td


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hdtool", description="Tổng hợp hóa đơn điện tử VN qua email ra Excel"
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_period(sp):
        sp.add_argument("--from", dest="from_date", type=_isodate, default=None,
                        help="Ngày lập hóa đơn từ (YYYY-MM-DD). Bỏ trống -> dùng default_from")
        sp.add_argument("--to", dest="to_date", type=_isodate, default=None,
                        help="Ngày lập hóa đơn đến (YYYY-MM-DD). Bỏ trống -> dùng default_to")

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

    sp_reorg = sub.add_parser(
        "reorganize", help="Tải lại & sắp xếp hóa đơn theo cấu trúc công ty/tháng/người gửi")
    add_period(sp_reorg)
    sp_reorg.add_argument("--include-suspect", action="store_true")

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
    cands = []
    for account in settings.accounts:
        scanner = MailScanner(settings, account)
        scanner.connect()
        print(f"[{account.user}] đã kết nối, quét thư mục: {scanner.folder}")
        try:
            acc_cands = scanner.scan(args.from_date, args.to_date)
        finally:
            scanner.close()
        cands.extend(acc_cands)
        cer = sum(1 for c in acc_cands if c.bucket == "certain")
        sus = sum(1 for c in acc_cands if c.bucket == "suspect")
        print(f"  -> chắc chắn: {cer}, nghi ngờ: {sus}")

    certain = [c for c in cands if c.bucket == "certain"]
    suspect = [c for c in cands if c.bucket == "suspect"]
    print(f"\n== CHẮC CHẮN là hóa đơn: {len(certain)} ==")
    for c in certain:
        print(f"  [{c.score}] {c.account:22s} | {c.sender[:34]:34s} | {c.subject[:48]}")
    print(f"\n== NGHI NGỜ (cần duyệt): {len(suspect)} ==")
    for c in suspect:
        print(f"  [{c.score}] {c.account:22s} | {c.sender[:34]:34s} | {c.subject[:48]}  -> {', '.join(c.reasons)}")
    if not certain and not suspect:
        print("Không tìm thấy email hóa đơn nào trong cửa sổ thời gian này.")

    out_csv = settings.data_dir / f"ung-vien-{args.from_date}_{args.to_date}.csv"
    write_candidates_csv(cands, out_csv)
    print(f"\nĐã ghi danh sách ứng viên/nghi ngờ để rà soát: {out_csv}")
    return 0


def cmd_collect(settings: Settings, args) -> int:
    from .mailscan import MailScanner
    manifest_path = settings.data_dir / ".collected.json"
    manifest = load_manifest(manifest_path)
    need_manual = []
    errors = []
    saved_count = 0
    for account in settings.accounts:
        scanner = MailScanner(settings, account)
        scanner.connect()
        try:
            cands = scanner.scan(args.from_date, args.to_date)
            wanted = [c for c in cands if c.bucket == "certain"
                      or (args.include_suspect and c.bucket == "suspect")]
            wanted, already = filter_uncollected(wanted, manifest)
            print(f"[{account.user}] tải {len(wanted)} email"
                  + (f" (bỏ qua {len(already)} đã tải)" if already else ""))
            for c in wanted:
                # One bad email must never sink the whole batch.
                try:
                    msg = scanner.fetch_message(c.uid)
                    files = invoice_files(msg)
                    if not files:
                        links = extract_links(msg, settings.classifier.issuer_domains + ["tracuu", "hoadon"])
                        portal_files = try_fetch_links(links)  # empty registry -> [] -> manual
                        if not portal_files:
                            need_manual.append((c, links))
                            continue
                        files = portal_files
                    company, ngay = _peek_company_date(files, c, settings)
                    dest = invoice_dir(settings.data_dir, company, ngay, _extract_email(c.sender))
                    saved = save_invoice_files(files, dest)
                    mark_collected(manifest, c.message_id, saved)
                    saved_count += 1
                    where = saved.get("xml") or saved.get("pdf") or saved.get("zip")
                    print(f"  ✓ {c.subject[:50]} -> {where}")
                except Exception as exc:  # noqa: BLE001 - keep going on any single email
                    errors.append((c, str(exc)))
                    print(f"  ✗ lỗi: {c.subject[:45]} — {exc}")
        finally:
            save_manifest(manifest_path, manifest)   # persist progress per account
            scanner.close()
    if need_manual:
        print(f"\n⚠ {len(need_manual)} hóa đơn chỉ có LINK (cần adapter / tải tay):")
        for c, links in need_manual:
            print(f"  - [{c.account}] {c.sender} | {c.subject[:45]} | {links or 'không thấy link'}")
    if errors:
        print(f"\n✗ {len(errors)} email lỗi khi tải (bỏ qua, không làm sập batch):")
        for c, msg in errors[:20]:
            print(f"  - [{c.account}] {c.subject[:45]} — {msg}")
    print(f"\nĐã tải {saved_count} hóa đơn có file.")
    return 0


def _extract_email(s: str) -> str:
    m = re.search(r"[\w.\-+]+@[\w.\-]+", s or "")
    return m.group(0).lower() if m else ""


def _peek_company_date(files, candidate, settings):
    """From the invoice XML: (company folder name, invoice date).

    company = settings.companies[buyer MST] for our companies, "_khac" for a
    known-but-not-ours buyer, "_chua-ro-cong-ty" when there is no readable XML.
    """
    for f in files:
        if f.kind == "xml":
            try:
                inv = parse_invoice_xml(f.data)
            except InvoiceParseError:
                continue
            company = settings.companies.get(inv.mst_mua)
            if company is None:
                company = "_khac" if inv.mst_mua else "_chua-ro-cong-ty"
            return company, (inv.ngay_lap or candidate.internal_date)
    return "_chua-ro-cong-ty", candidate.internal_date


def cmd_report(settings: Settings, args) -> int:
    source = Path(args.source) if args.source else settings.data_dir
    out = Path(args.output) if args.output else _default_output(args.from_date, args.to_date, settings)
    if not source.exists():
        print(f"Không tìm thấy thư mục nguồn: {source}. Hãy chạy 'collect' trước.")
        return 1
    result, skipped, manual = build_report(source, args.from_date, args.to_date,
                                            settings.buyer_msts, out,
                                            companies=settings.companies)
    def _money(x):
        return int(x) if x == x.to_integral_value() else x

    print(f"Đã xuất: {out}")
    print(f"  Hóa đơn trong kỳ: {len(result.invoices)}")
    print(f"  Tổng tiền chưa thuế: {_money(result.total_chua_thue):,}")
    print(f"  Tổng tiền thuế    : {_money(result.total_thue):,}")
    print(f"  Tổng thanh toán   : {_money(result.total_thanh_toan):,}")
    if not settings.buyer_msts:
        print("  (Chưa cấu hình MIYANO_MST → không lọc mua-vào, chỉ gắn cờ.)")
    if skipped:
        print(f"  Bỏ qua/cần xem lại: {len(skipped)} (xem sheet 'Bỏ qua')")
    if manual:
        print(f"  Chỉ có PDF, cần nhập tay: {len(manual)} (xem sheet 'Cần nhập tay')")
    return 0


def _is_old_period_dir(name: str) -> bool:
    """True for old-layout top-level folders named YYYY-MM (to be cleaned up)."""
    return bool(re.fullmatch(r"\d{4}-\d{2}", name))


def cmd_reorganize(settings: Settings, args) -> int:
    """Re-download invoices into data/<company>/<month>/<sender>/ and remove the
    old period-based layout. Files are re-derivable from the mailbox, so this
    rebuilds cleanly (grouping by sender email needs the mailbox)."""
    import shutil
    data = settings.data_dir
    manifest = data / ".collected.json"
    if manifest.exists():
        manifest.unlink()   # force re-download into the new tree
    print("Sắp xếp lại: tải lại vào cấu trúc công ty/tháng/người gửi...")
    rc = cmd_collect(settings, args)
    removed = 0
    if data.exists():
        for child in data.iterdir():
            if child.is_dir() and _is_old_period_dir(child.name):
                shutil.rmtree(child)
                removed += 1
    if removed:
        print(f"Đã dọn {removed} thư mục theo cấu trúc cũ.")
    return rc


def cmd_run(settings: Settings, args) -> int:
    rc = cmd_collect(settings, args)
    if rc != 0:
        return rc
    report_args = argparse.Namespace(
        from_date=args.from_date, to_date=args.to_date,
        output=getattr(args, "output", None), source=None,
    )
    return cmd_report(settings, report_args)


_COMMANDS = {"scan": cmd_scan, "collect": cmd_collect, "report": cmd_report,
             "run": cmd_run, "reorganize": cmd_reorganize}


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = _load_settings()
    args.from_date, args.to_date = resolve_period(args.from_date, args.to_date, settings)
    return _COMMANDS[args.command](settings, args)


if __name__ == "__main__":
    sys.exit(main())
