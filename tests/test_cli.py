"""Tests for CLI argument parsing and date resolution."""
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from hdtool import cli
from hdtool.cli import build_parser, resolve_period
from hdtool.config import build_settings

FIXTURES = Path(__file__).parent / "fixtures"


def _settings(default_from=None, default_to=None):
    cfg = {}
    if default_from:
        cfg["default_from"] = default_from
    if default_to:
        cfg["default_to"] = default_to
    return build_settings({"IMAP_USER": "a@x.vn"}, cfg)


def test_parser_report_with_output():
    args = build_parser().parse_args(
        ["report", "--from", "2026-06-01", "--to", "2026-06-30", "-o", "out.xlsx"]
    )
    assert args.command == "report"
    assert args.from_date == date(2026, 6, 1)
    assert args.to_date == date(2026, 6, 30)
    assert args.output == "out.xlsx"


def test_parser_report_company_flag():
    args = build_parser().parse_args(["report", "--company", "miyano"])
    assert args.company == "miyano"


def test_parser_report_company_defaults_none():
    args = build_parser().parse_args(["report"])
    assert args.company is None


def test_parser_report_format_flag():
    args = build_parser().parse_args(["report", "--format", "csv"])
    assert args.format == "csv"


def test_parser_report_format_default_xlsx():
    args = build_parser().parse_args(["report"])
    assert args.format == "xlsx"


def test_parser_scan():
    args = build_parser().parse_args(["scan", "--from", "2026-06-01", "--to", "2026-06-30"])
    assert args.command == "scan"
    assert args.from_date == date(2026, 6, 1)


def test_parser_run_and_collect_exist():
    for cmd in ("collect", "run", "reorganize"):
        args = build_parser().parse_args([cmd, "--from", "2026-06-01", "--to", "2026-06-30"])
        assert args.command == cmd


def test_is_old_period_dir():
    from hdtool.cli import _is_old_period_dir
    assert _is_old_period_dir("2026-06") is True
    assert _is_old_period_dir("unknown-period") is False
    assert _is_old_period_dir("miyano") is False
    assert _is_old_period_dir("_chua-ro-cong-ty") is False


def test_dir_keys_subset_guards_data_loss(tmp_path):
    import shutil
    from hdtool.cli import _dir_keys_subset
    from hdtool.parse_xml import parse_invoice_xml
    fixtures = __import__("pathlib").Path(__file__).parent / "fixtures"
    old = tmp_path / "2026-06"
    old.mkdir()
    shutil.copy(fixtures / "inv_10pct.xml", old / "a.xml")
    key = parse_invoice_xml((fixtures / "inv_10pct.xml").read_bytes()).dedup_key
    # every invoice in the old dir is present in the new structure -> safe to remove
    assert _dir_keys_subset(old, {key}) is True
    # its invoice is NOT in the new structure -> unsafe, must keep
    assert _dir_keys_subset(old, set()) is False


def test_reorganize_keeps_old_dir_when_not_recollected(tmp_path, monkeypatch):
    # Reproduces the CRITICAL scenario: collect re-downloads nothing, so the old
    # invoice must SURVIVE (never delete an old dir whose invoice isn't in the
    # new tree), and the manifest must not be lost.
    data = tmp_path / "data"
    old = data / "2026-06" / "abc"
    old.mkdir(parents=True)
    shutil.copy(FIXTURES / "inv_10pct.xml", old / "a.xml")
    (data / ".collected.json").write_text('{"m":{"xml":"x"}}')
    settings = build_settings({"IMAP_USER": "x@y"}, {}, data_dir=data)
    monkeypatch.setattr(cli, "cmd_collect", lambda s, a: 0)   # simulate 0 re-downloads
    args = SimpleNamespace(from_date=date(2026, 6, 1), to_date=date(2026, 6, 30),
                           include_suspect=False)
    cli.cmd_reorganize(settings, args)
    assert (old / "a.xml").exists()               # invoice NOT lost
    assert (data / ".collected.json").exists()     # manifest preserved


def test_parser_dates_optional_for_report():
    # dates are optional at parse time now; resolve_period enforces them later
    args = build_parser().parse_args(["report"])
    assert args.from_date is None and args.to_date is None


def test_parser_include_suspect_flag():
    args = build_parser().parse_args(
        ["collect", "--from", "2026-06-01", "--to", "2026-06-30", "--include-suspect"]
    )
    assert args.include_suspect is True


def test_parser_dates_optional_now():
    # dates are optional; they can come from config instead
    args = build_parser().parse_args(["scan"])
    assert args.from_date is None
    assert args.to_date is None


def test_resolve_period_prefers_cli_args():
    fd, td = resolve_period(date(2026, 1, 1), date(2026, 1, 31),
                            _settings("2026-06-01", "2026-06-30"))
    assert (fd, td) == (date(2026, 1, 1), date(2026, 1, 31))


def test_resolve_period_falls_back_to_config():
    fd, td = resolve_period(None, None, _settings("2026-06-01", "2026-06-30"))
    assert (fd, td) == (date(2026, 6, 1), date(2026, 6, 30))


def test_resolve_period_errors_when_missing():
    with pytest.raises(SystemExit):
        resolve_period(None, None, _settings())


def test_main_no_args_launches_interactive(monkeypatch):
    import hdtool.interactive as interactive
    calls = {}
    monkeypatch.setattr(interactive, "run_interactive",
                        lambda settings, **kw: calls.update(ran=True) or 0)
    monkeypatch.setattr(cli, "_load_settings", lambda: _settings("2026-06-01", "2026-06-30"))
    rc = cli.main([])
    assert rc == 0 and calls.get("ran") is True


# ------------------------------------------------------- lệnh `hdtool ncc` (T43)

def test_parser_ncc_va_co_tai():
    p = build_parser()
    assert p.parse_args(["ncc"]).tai is False
    assert p.parse_args(["ncc", "--tai"]).tai is True


def _settings_data(tmp_path):
    s = _settings()
    s.data_dir = tmp_path
    return s


def test_cmd_ncc_liet_ke_cong_thuc_va_dong_dang_cho(tmp_path, capsys, monkeypatch):
    from hdtool import ncc, worklist
    from hdtool.worklist import WorkRow

    reg = tmp_path / "ncc.yaml"
    ncc.save_registry(reg, [ncc.learn(
        "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP",
        "GJF211_PDLEP", ten="meinvoice.vn")])
    monkeypatch.setattr(cli, "NCC_REGISTRY", reg)
    worklist.save(tmp_path / "so-hoa-don-cho-tai.csv", [
        WorkRow(message_id="m1", ncc="ehoadon.vn", trang_thai="cần trình duyệt",
                chan_doan="có captcha — cần trình duyệt"),
        WorkRow(message_id="m2", ncc="ipos.vn", trang_thai="đã tải"),
    ])
    cli.cmd_ncc(_settings_data(tmp_path), SimpleNamespace(tai=False))
    out = capsys.readouterr().out
    assert "meinvoice.vn" in out                      # NCC đã có công thức
    assert "ehoadon.vn" in out and "captcha" in out   # dòng đang chờ + lý do
    assert "m2" not in out                            # dòng đã tải không nằm ở mục chờ


def test_cmd_ncc_tai_dung_ma_nguoi_dung_dien_tay(tmp_path, monkeypatch):
    """Người dùng gõ mã vào sổ -> `hdtool ncc --tai` phải dùng ĐÚNG mã đó."""
    from hdtool import worklist
    from hdtool.portal_probe import ProbeResult
    from hdtool.worklist import WorkRow

    monkeypatch.setattr(cli, "NCC_REGISTRY", tmp_path / "ncc.yaml")
    worklist.save(tmp_path / "so-hoa-don-cho-tai.csv", [
        WorkRow(message_id="m1", link_tra_cuu="https://x.vn/p",
                ma_tra_cuu="ABC123", trang_thai="thiếu mã")])
    goi = {}

    def gia(links, ma=None, **kw):
        goi["links"], goi["ma"] = links, ma
        return ProbeResult()

    monkeypatch.setattr(cli.portal_probe, "fetch_link_only", gia)
    cli.cmd_ncc(_settings_data(tmp_path), SimpleNamespace(tai=True))
    assert goi["ma"] == "ABC123"
    assert goi["links"] == ["https://x.vn/p"]


def test_main_lenh_ncc_khong_doi_khoang_ngay(monkeypatch):
    """`hdtool ncc` làm việc trên sổ đã có, không cần --from/--to.

    Phải vá vào _COMMANDS (dict giữ tham chiếu hàm trực tiếp) chứ vá thuộc tính
    module thì main() vẫn gọi hàm thật.
    """
    goi = {}
    monkeypatch.setattr(cli, "_load_settings", _settings)

    def gia(settings, args):
        goi["chay"] = True
        return 0

    monkeypatch.setitem(cli._COMMANDS, "ncc", gia)
    assert cli.main(["ncc"]) == 0
    assert goi["chay"] is True
