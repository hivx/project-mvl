"""Bóc link tra cứu + mã tra cứu ra khỏi email. Thuần, không mạng."""
from hdtool.lookup import code_from_url, find_code, rank_links

MISA = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"


def test_code_from_url_lay_tham_so_code():
    assert code_from_url(MISA) == "GJF211_PDLEP"


def test_code_from_url_bo_qua_url_khong_co_ma():
    assert code_from_url("https://ncc.vn/trang-chu") is None


def test_find_code_tu_nhan_trong_text():
    body = "Kính gửi Quý khách,\nMã tra cứu: GJF211_PDLEP\nTrân trọng."
    assert find_code(body) == "GJF211_PDLEP"


def test_find_code_tu_bang_html():
    """Nhiều nhà phát hành đặt mã trong <td> — bản text phẳng dính hai ô vào nhau."""
    html = "<table><tr><td>Mã tra cứu</td><td> ABC123XYZ </td></tr></table>"
    assert find_code("", html) == "ABC123XYZ"


def test_find_code_khong_bat_nham_tu_tieng_viet():
    assert find_code("Mã tra cứu: xem trong file đính kèm") is None


def test_rank_links_uu_tien_link_co_ma_va_domain_nha_phat_hanh():
    urls = ["https://cdn.ncc.vn/logo.png",
            "https://facebook.com/ncc",
            "https://ncc.vn",
            "https://meinvoice.vn/tra-cuu?code=ABC123"]
    got = rank_links(urls, "kt@ncc.vn", ["meinvoice"])
    assert got[0] == "https://meinvoice.vn/tra-cuu?code=ABC123"


def test_rank_links_loai_anh_va_unsubscribe():
    urls = ["https://x.vn/a.jpg", "https://x.vn/unsubscribe?u=1", "mailto:a@x.vn"]
    assert rank_links(urls, "a@x.vn", []) == []


def test_code_from_url_lay_ma_nam_trong_path():
    """ehoadon: tracuu.ehoadon.vn/UTAWCE3X5A5 — mã ở PATH, không phải query."""
    assert code_from_url("http://tracuu.ehoadon.vn/UTAWCE3X5A5") == "UTAWCE3X5A5"


def test_code_from_url_khong_nham_path_thuong():
    assert code_from_url("https://www.meinvoice.vn/tra-cuu") is None
    assert code_from_url("https://meinvoice.vn/tra-cuu/DownloadHandler.ashx") is None


def test_find_code_nhan_nhan_MTC():
    """Tiêu đề ehoadon: 'Hóa đơn số 00005596 - MTC: UTAWCE3X5A5 của …'."""
    assert find_code("Hóa đơn số 00005596 - MTC: UTAWCE3X5A5 của CÔNG TY") == "UTAWCE3X5A5"
