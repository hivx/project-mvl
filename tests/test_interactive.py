"""Tests for the interactive menu (input injected — no real stdin / network)."""
from datetime import date

from hdtool.config import build_settings
from hdtool.interactive import prompt_options, run_interactive


def scripted(*answers):
    """A fake input() that returns the given answers in order, ignoring prompt."""
    it = iter(answers)
    return lambda prompt="": next(it)


def _settings(tmp_path, **cfg_extra):
    cfg = {"companies": {"0109529507": "miyano", "0108186705": "medcons"},
           "default_from": "2026-06-01", "default_to": "2026-06-30"}
    cfg.update(cfg_extra)
    return build_settings({"IMAP_USER": "a@x.vn"}, cfg, data_dir=tmp_path)


def test_prompt_options_reads_all_fields(tmp_path):
    inp = scripted("2026-06-01", "2026-06-30", "2", "2")  # from, to, company#2, CSV
    ch = prompt_options(_settings(tmp_path), input_fn=inp, out=lambda *_: None)
    assert ch.from_date == date(2026, 6, 1)
    assert ch.to_date == date(2026, 6, 30)
    assert ch.company == "miyano"      # companies sorted -> [medcons, miyano], #2
    assert ch.fmt == "csv"


def test_prompt_options_uses_defaults_on_enter(tmp_path):
    inp = scripted("", "", "", "")     # all Enter -> config dates, first company, xlsx
    ch = prompt_options(_settings(tmp_path), input_fn=inp, out=lambda *_: None)
    assert (ch.from_date, ch.to_date) == (date(2026, 6, 1), date(2026, 6, 30))
    assert ch.company == "medcons"     # first of sorted list
    assert ch.fmt == "xlsx"


def test_prompt_options_reprompts_on_bad_date(tmp_path):
    inp = scripted("khong-phai-ngay", "2026-06-05", "2026-06-30", "1", "1")
    ch = prompt_options(_settings(tmp_path), input_fn=inp, out=lambda *_: None)
    assert ch.from_date == date(2026, 6, 5)


def test_prompt_options_accepts_company_by_name(tmp_path):
    inp = scripted("2026-06-01", "2026-06-30", "medcons", "1")
    ch = prompt_options(_settings(tmp_path), input_fn=inp, out=lambda *_: None)
    assert ch.company == "medcons"


def test_run_interactive_builds_output_path_and_executes(tmp_path):
    inp = scripted("2026-06-01", "2026-06-30", "2", "1")  # miyano, xlsx
    captured = {}

    def execute(settings, choices, out_path, out):
        captured["choices"] = choices
        captured["path"] = out_path
        return 0

    rc = run_interactive(_settings(tmp_path), input_fn=inp,
                         out=lambda *_: None, execute=execute)
    assert rc == 0
    assert captured["choices"].company == "miyano"
    assert str(captured["path"]).endswith(
        "bang-ke-miyano-2026-06-01_2026-06-30.xlsx")


def test_run_interactive_csv_extension(tmp_path):
    inp = scripted("2026-06-01", "2026-06-30", "1", "2")  # medcons, csv
    captured = {}
    run_interactive(_settings(tmp_path), input_fn=inp, out=lambda *_: None,
                    execute=lambda s, c, p, o: captured.setdefault("path", p) and 0)
    assert str(captured["path"]).endswith(
        "bang-ke-medcons-2026-06-01_2026-06-30.csv")


def test_menu_thu_tai_hd_chi_link_truoc_khi_tong_hop(monkeypatch):
    """Menu phải gọi cmd_ncc(tai=True) GIỮA collect và report — không hỏi thêm câu nào."""
    from datetime import date

    from hdtool import cli
    from hdtool.interactive import Choices, _default_execute

    thu_tu = []
    monkeypatch.setattr(cli, "cmd_collect", lambda s, a: thu_tu.append("collect") or 0)
    monkeypatch.setattr(cli, "cmd_ncc", lambda s, a: thu_tu.append(f"ncc:{a.tai}") or 0)
    monkeypatch.setattr(cli, "cmd_report", lambda s, a: thu_tu.append("report") or 0)

    ch = Choices(from_date=date(2026, 6, 1), to_date=date(2026, 6, 30),
                 company="miyano", fmt="csv")
    _default_execute(None, ch, "/tmp/x.csv", lambda *_: None)
    assert thu_tu == ["collect", "ncc:True", "report"]


def test_menu_truyen_cong_ty_da_chon_xuong_collect(monkeypatch):
    """Chọn miyano ở menu -> collect phải nhận company='miyano' để giới hạn hộp thư."""
    from datetime import date

    from hdtool import cli
    from hdtool.interactive import Choices, _default_execute

    nhan = {}
    monkeypatch.setattr(cli, "cmd_collect", lambda s, a: nhan.update(c=a.company) or 0)
    monkeypatch.setattr(cli, "cmd_ncc", lambda s, a: 0)
    monkeypatch.setattr(cli, "cmd_report", lambda s, a: 0)
    ch = Choices(from_date=date(2026, 6, 1), to_date=date(2026, 6, 30),
                 company="miyano", fmt="csv")
    _default_execute(None, ch, "/tmp/x.csv", lambda *_: None)
    assert nhan["c"] == "miyano"
