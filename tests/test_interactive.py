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
