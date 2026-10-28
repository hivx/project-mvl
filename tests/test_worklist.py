"""Sổ hóa đơn chỉ-link: tích lũy qua mọi lần chạy, người dùng sửa tay được."""
from hdtool.worklist import WorkRow, load, merge, save, upsert


def test_save_ghi_utf8_bom_va_doc_lai_duoc(tmp_path):
    p = tmp_path / "so.csv"
    save(p, [WorkRow(message_id="m1", nguoi_gui="kt@ncc.vn", trang_thai="đã tải")])
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")   # Excel đọc tiếng Việt đúng
    assert load(p)["m1"].nguoi_gui == "kt@ncc.vn"


def test_load_file_chua_co_tra_ve_rong(tmp_path):
    assert load(tmp_path / "chua-co.csv") == {}


def test_merge_giu_o_nguoi_dung_dien_tay():
    """Người dùng gõ mã vào dòng 'thiếu mã' -> chạy lại KHÔNG được xóa mất."""
    cu = {"m1": WorkRow(message_id="m1", ma_tra_cuu="ABC123", ghi_chu="tự điền")}
    moi = [WorkRow(message_id="m1", ma_tra_cuu="", trang_thai="thiếu mã",
                   chan_doan="không bóc được mã")]
    out = merge(cu, moi)
    assert out[0].ma_tra_cuu == "ABC123"          # ô người dùng: giữ
    assert out[0].ghi_chu == "tự điền"            # ô người dùng: giữ
    assert out[0].trang_thai == "thiếu mã"        # ô tool: cập nhật


def test_merge_giu_dong_cu_khong_con_trong_lan_chay_moi():
    cu = {"m1": WorkRow(message_id="m1", trang_thai="đã tải")}
    out = merge(cu, [WorkRow(message_id="m2", trang_thai="chưa có công thức")])
    assert sorted(r.message_id for r in out) == ["m1", "m2"]


def test_upsert_hai_lan_khong_nhan_doi_dong(tmp_path):
    p = tmp_path / "so.csv"
    upsert(p, [WorkRow(message_id="m1", trang_thai="chưa có công thức")])
    upsert(p, [WorkRow(message_id="m1", trang_thai="đã tải", file="data/x.xml")])
    rows = load(p)
    assert len(rows) == 1
    assert rows["m1"].trang_thai == "đã tải"
    assert rows["m1"].file == "data/x.xml"


def test_save_khong_de_lai_file_tam(tmp_path):
    p = tmp_path / "so.csv"
    save(p, [WorkRow(message_id="m1")])
    assert [f.name for f in tmp_path.iterdir()] == ["so.csv"]


# ------------------------ T49: bản Re:/Fwd: không đính kèm là BẢN SAO, không thiếu

def test_index_da_tai_theo_tieu_de_chuan_hoa():
    from hdtool.worklist import index_da_tai
    rows = {
        "m1": WorkRow(message_id="m1", tieu_de="CÔNG TY ABC gửi hóa đơn số 123",
                      trang_thai="đã tải", file="data/miyano/2026-06/x/hd.xml"),
        "m2": WorkRow(message_id="m2", tieu_de="Chưa tải được", trang_thai="cần trình duyệt"),
    }
    idx = index_da_tai(rows)
    assert idx["công ty abc gửi hóa đơn số 123"] == "data/miyano/2026-06/x/hd.xml"
    assert "chưa tải được" not in idx


def test_index_da_tai_khop_ca_ban_forward():
    from hdtool.worklist import index_da_tai, khop_ban_goc
    rows = {"m1": WorkRow(message_id="m1", tieu_de="ABC gửi hóa đơn 123",
                          trang_thai="đã tải", file="data/x/hd.xml")}
    idx = index_da_tai(rows)
    assert khop_ban_goc(idx, "Fwd: ABC gửi hóa đơn 123") == "data/x/hd.xml"
    assert khop_ban_goc(idx, "Re: Fwd: ABC gửi hóa đơn 123") == "data/x/hd.xml"
    assert khop_ban_goc(idx, "Hóa đơn khác hẳn") is None
