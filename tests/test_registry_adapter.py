"""Adapter dựng từ MỘT DÒNG registry — không phải code riêng cho từng cổng.

Thêm nhà cung cấp mới = thêm dữ liệu vào config/ncc-registry.yaml (tool tự ghi
sau khi dò thành công), không phải viết file Python mới.
"""
from pathlib import Path

from hdtool.adapters.registry_adapter import RegistryAdapter
from hdtool.ncc import NccEntry, learn

XML_OK = (Path(__file__).parent / "fixtures" / "inv_10pct.xml").read_bytes()
MISA = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"
CT_XML = {"content-type": "application/xml",
          "content-disposition": 'attachment;filename="hd.xml"'}


class FakeResp:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}


class FakeSession:
    def __init__(self, by_url):
        self.by_url = by_url
        self.headers = {}
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        return self.by_url.get(url, FakeResp(b"", status=404))


def test_fetch_dung_cong_thuc_voi_ma_moi():
    entry = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    url_moi = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=NEW_CODE1"
    sess = FakeSession({url_moi: FakeResp(XML_OK, headers=CT_XML)})
    files = RegistryAdapter(entry, session_factory=lambda: sess).fetch("", "NEW_CODE1")
    assert [f.kind for f in files] == ["xml"]
    assert files[0].filename == "hd.xml"


def test_fetch_tra_rong_khi_cong_tra_html():
    """Cổng đổi URL / token hết hạn -> [] để rơi về nhánh dò, không làm sập batch."""
    entry = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    sess = FakeSession({})                       # mọi URL -> 404
    assert RegistryAdapter(entry, session_factory=lambda: sess).fetch("", "NEW_CODE1") == []


def test_fetch_tra_rong_khi_khong_co_ma():
    entry = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    assert RegistryAdapter(entry).fetch("https://meinvoice.vn/x", None) == []


def test_can_handle_chi_nhan_khi_da_co_cong_thuc():
    co_cong_thuc = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    assert RegistryAdapter(co_cong_thuc).can_handle("https://meinvoice.vn/tra-cuu?sc=X")

    chua_hoc = NccEntry(ten="x", nhan_dien=["x.vn"])      # chưa có công thức
    assert not RegistryAdapter(chua_hoc).can_handle("https://x.vn/tra-cuu")

    assert not RegistryAdapter(co_cong_thuc).can_handle("https://cong-khac.vn/tra-cuu")
