"""Công thức tải trong config/ncc-registry.yaml — kiểm chứng bằng công thức thật."""
from pathlib import Path

from hdtool.ncc import build_url, load_registry, match

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "ncc-registry.yaml"


def test_meinvoice_dung_url_truc_tiep_cho_ca_xml_va_pdf():
    """MISA tải được bằng URL trực tiếp — không cần phiên, không cần trình duyệt."""
    e = match(load_registry(REGISTRY), "https://www.meinvoice.vn/tra-cuu/")
    assert e is not None and not e.phai_do_lai and not e.can_phien
    assert build_url(e, "VLF4IVJJVJXM", "xml") == (
        "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx"
        "?Type=xml&Code=VLF4IVJJVJXM")
    assert build_url(e, "VLF4IVJJVJXM", "pdf") == (
        "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx"
        "?Type=pdf&Code=VLF4IVJJVJXM")


def test_meinvoice_nhan_ca_ten_mien_khong_www():
    """Email có cả hai dạng link: www.meinvoice.vn và meinvoice.vn."""
    entries = load_registry(REGISTRY)
    assert match(entries, "https://meinvoice.vn/tra-cuu") is not None
