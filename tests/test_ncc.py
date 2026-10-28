"""Registry công thức tải theo nhà cung cấp: học 1 lần, dùng mãi.

Registry là BỘ NHỚ ĐỆM của quy trình dò, không phải điều kiện tiên quyết — cổng
chưa từng gặp vẫn tải được, có công thức chỉ để đi tắt.
"""
from hdtool.ncc import NccEntry, build_url, learn, load_registry, match, save_registry

MISA = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"


def test_learn_suy_cong_thuc_va_sinh_luon_dong_pdf():
    e = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn", ngay="2026-08-25")
    assert e.tai["xml"] == \
        "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code={ma}"
    assert e.tai["pdf"] == \
        "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=pdf&Code={ma}"
    assert e.nhan_dien == ["meinvoice.vn"]
    assert e.hoc_tu == MISA and not e.phai_do_lai


def test_learn_danh_dau_phai_do_lai_khi_url_khong_chua_ma():
    """Link ký theo phiên (VNPT/Fast) không template hóa được -> vẫn auto, chỉ không đi tắt."""
    e = learn("https://x.vn/getinvoice?token=EPHEMERAL999", "ABC123", ten="x.vn")
    assert e.phai_do_lai and e.tai == {}


def test_learn_khong_sinh_dong_pdf_khi_url_khong_co_type():
    e = learn("https://x.vn/tai/ABC123", "ABC123", ten="x.vn")
    assert e.tai == {"xml": "https://x.vn/tai/{ma}"}


def test_build_url_thay_ma():
    e = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    assert build_url(e, "QQWZK_9911") == \
        "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=QQWZK_9911"


def test_build_url_tra_none_khi_chua_co_cong_thuc():
    assert build_url(NccEntry(ten="x", nhan_dien=["x.vn"]), "ABC123") is None


def test_match_theo_nhan_dien():
    entries = [NccEntry(ten="MISA", nhan_dien=["meinvoice.vn"])]
    assert match(entries, "https://meinvoice.vn/tra-cuu?c=1").ten == "MISA"
    assert match(entries, "https://khac.vn/tra-cuu") is None


def test_roundtrip_yaml(tmp_path):
    p = tmp_path / "ncc.yaml"
    save_registry(p, [learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn", ngay="2026-08-25")])
    lai = load_registry(p)
    assert lai[0].tai["xml"].endswith("Code={ma}")
    assert lai[0].ten == "meinvoice.vn"


def test_load_registry_file_chua_co_tra_ve_rong(tmp_path):
    assert load_registry(tmp_path / "chua-co.yaml") == []


def test_load_registry_bo_qua_khoa_la(tmp_path):
    """File người dùng sửa tay có thể thừa khóa — không được làm sập."""
    p = tmp_path / "ncc.yaml"
    p.write_text("- ten: X\n  nhan_dien: [x.vn]\n  khoa_la: 1\n", encoding="utf-8")
    assert load_registry(p)[0].ten == "X"
