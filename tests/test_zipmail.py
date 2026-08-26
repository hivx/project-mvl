"""SMBC eInvoice: zip mã hóa ở một email, mật khẩu ở email KHÁC cùng tiêu đề.

Mẫu thật (kiểm chứng 2026-08-26, 4/4 hóa đơn):
    Email 1: "[ SMBC HN - eInvoice] [8754440] [0005301][30062026] …"
             đính kèm invoice.zip (mã hóa) -> 01GTKT.xml + invoice.pdf
    Email 2: tiêu đề Y HỆT, không đính kèm, body "Password unzip file: ya0N1ZzrPPxp"

Hai email có thể đến theo thứ tự bất kỳ nên phải gom hết rồi mới ghép.
"""
import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from hdtool.zipmail import (chuan_hoa_tieu_de, ghep_cap, giai_nen_co_mat_khau,
                            tim_mat_khau)

FIXTURES = Path(__file__).parent / "fixtures"
XML_OK = (FIXTURES / "inv_10pct.xml").read_bytes()
MAT_KHAU = "BmDkKAxPhZF7"


@pytest.fixture(scope="module")
def zip_ma_hoa(tmp_path_factory):
    """Zip có mật khẩu. zipfile không TẠO được zip mã hóa -> dùng `zip -P`."""
    d = tmp_path_factory.mktemp("smbc")
    (d / "01GTKT.xml").write_bytes(XML_OK)
    (d / "invoice.pdf").write_bytes(b"%PDF-1.4 gia")
    out = d / "invoice.zip"
    r = subprocess.run(["zip", "-P", MAT_KHAU, "-j", str(out),
                        str(d / "01GTKT.xml"), str(d / "invoice.pdf")],
                       capture_output=True)
    if r.returncode != 0:
        pytest.skip("cần lệnh `zip` để tạo fixture zip mã hóa")
    return out.read_bytes()


def test_chuan_hoa_bo_moi_tien_to_fwd_re():
    goc = "[ SMBC HN - eInvoice] [8754440] [0005301][30062026] [VND]"
    assert chuan_hoa_tieu_de("Fwd: " + goc) == chuan_hoa_tieu_de(goc)
    assert chuan_hoa_tieu_de("Fwd: Fw: RE: " + goc) == chuan_hoa_tieu_de(goc)
    assert chuan_hoa_tieu_de("  " + goc.upper() + " ") == chuan_hoa_tieu_de(goc)


def test_chuan_hoa_khong_gop_nham_hai_hoa_don_khac_nhau():
    a = "[ SMBC HN - eInvoice] [8754440] [0005301][30062026]"
    b = "[ SMBC HN - eInvoice] [8754440] [0003894][29052026]"
    assert chuan_hoa_tieu_de(a) != chuan_hoa_tieu_de(b)


def test_tim_mat_khau_trong_body():
    assert tim_mat_khau("Password unzip file: BmDkKAxPhZF7\n\n") == MAT_KHAU
    assert tim_mat_khau("password unzip file:ya0N1ZzrPPxp") == "ya0N1ZzrPPxp"


def test_tim_mat_khau_bo_qua_rac_html():
    """Body HTML từng làm regex ngây thơ bắt nhầm '<span'."""
    assert tim_mat_khau('<p>Password unzip file: <span class="x">ABC12345</span></p>') \
        == "ABC12345"
    assert tim_mat_khau("<p>Không có mật khẩu ở đây</p>") is None


def test_giai_nen_ra_xml_va_pdf(zip_ma_hoa):
    files = giai_nen_co_mat_khau(zip_ma_hoa, MAT_KHAU)
    assert sorted(f.kind for f in files) == ["pdf", "xml"]
    assert next(f for f in files if f.kind == "xml").data == XML_OK


def test_giai_nen_sai_mat_khau_tra_rong(zip_ma_hoa):
    assert giai_nen_co_mat_khau(zip_ma_hoa, "sai-mat-khau") == []


def test_giai_nen_zip_hong_tra_rong():
    assert giai_nen_co_mat_khau(b"khong phai zip", MAT_KHAU) == []


def test_ghep_cap_khi_email_zip_den_TRUOC():
    goc = "[ SMBC HN - eInvoice] [0005301]"
    cap = ghep_cap([("m1", goc, b"ZIPBYTES", None),
                    ("m2", "Fwd: " + goc, None, MAT_KHAU)])
    assert cap == {"m1": (b"ZIPBYTES", MAT_KHAU)}


def test_ghep_cap_khi_email_mat_khau_den_TRUOC():
    goc = "[ SMBC HN - eInvoice] [0005301]"
    cap = ghep_cap([("m1", goc, None, MAT_KHAU),
                    ("m2", "Fwd: " + goc, b"ZIPBYTES", None)])
    assert cap == {"m2": (b"ZIPBYTES", MAT_KHAU)}


def test_ghep_cap_zip_khong_co_mat_khau_thi_khong_ghep():
    cap = ghep_cap([("m1", "[SMBC] [0005301]", b"ZIPBYTES", None)])
    assert cap == {}


def test_ghep_cap_khong_lan_giua_hai_hoa_don():
    cap = ghep_cap([
        ("m1", "[SMBC] [0005301]", b"ZIP-A", None),
        ("m2", "Fwd: [SMBC] [0005301]", None, "PASS-A00000"),
        ("m3", "[SMBC] [0003894]", b"ZIP-B", None),
        ("m4", "Fwd: [SMBC] [0003894]", None, "PASS-B00000"),
    ])
    assert cap == {"m1": (b"ZIP-A", "PASS-A00000"), "m3": (b"ZIP-B", "PASS-B00000")}


def test_nhan_dien_zip_ma_hoa(zip_ma_hoa):
    from hdtool.zipmail import la_zip_ma_hoa
    assert la_zip_ma_hoa(zip_ma_hoa) is True


def test_zip_thuong_khong_bi_coi_la_ma_hoa():
    from hdtool.zipmail import la_zip_ma_hoa
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("01GTKT.xml", XML_OK)
    assert la_zip_ma_hoa(buf.getvalue()) is False
    assert la_zip_ma_hoa(b"khong phai zip") is False
