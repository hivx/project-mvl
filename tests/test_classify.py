"""Tests for invoice-email scoring / bucketing."""
from hdtool.classify import score_email, ClassifierConfig

CFG = ClassifierConfig(
    issuer_domains=["sinvoice", "vnpt", "misa", "easyinvoice", "meinvoice"],
    keywords=["hóa đơn", "invoice", "hđđt"],
    whitelist_senders=["ketoan@nhacungcap.vn"],
)


def test_xml_attachment_is_certain():
    c = score_email("billing@sinvoice.com.vn", "Thông báo", has_xml=True,
                    has_pdf=True, has_link=False, cfg=CFG)
    assert c.bucket == "certain"
    assert "xml" in " ".join(c.reasons).lower()


def test_issuer_domain_plus_keyword_is_certain():
    c = score_email("hoadon@vnpt.vn", "Hóa đơn GTGT tháng 6", has_xml=False,
                    has_pdf=True, has_link=True, cfg=CFG)
    assert c.bucket == "certain"


def test_keyword_only_is_suspect():
    c = score_email("someone@random.com", "Gửi bạn hóa đơn tháng này",
                    has_xml=False, has_pdf=False, has_link=False, cfg=CFG)
    assert c.bucket == "suspect"


def test_plain_pdf_from_unknown_sender_is_ignored():
    c = score_email("sales@foreignvendor.com", "Quotation Q3 medical devices",
                    has_xml=False, has_pdf=True, has_link=False, cfg=CFG)
    assert c.bucket == "ignore"


def test_link_only_is_ignored():
    c = score_email("noreply@newsletter.com", "Check this out",
                    has_xml=False, has_pdf=False, has_link=True, cfg=CFG)
    assert c.bucket == "ignore"


# --- exclude_senders (T36): bank payment receipts are not VAT invoices --------

EXCL = ClassifierConfig(keywords=["biên lai", "hóa đơn"],
                        exclude_senders=["vcbdigibank"])


def test_excluded_sender_without_xml_is_ignored():
    """VCBDigibank 'Biên lai chuyển tiền' matches keyword but is a bank receipt."""
    c = score_email("VCBDigibank@info.vietcombank.com.vn",
                    "Biên lai chuyển tiền qua tài khoản",
                    has_xml=False, has_pdf=False, has_link=False, cfg=EXCL)
    assert c.bucket == "ignore"
    assert "loại trừ" in " ".join(c.reasons).lower()


def test_excluded_sender_with_xml_is_still_kept():
    """Safety: an excluded sender that DOES attach XML is a real invoice — keep it."""
    c = score_email("VCBDigibank@info.vietcombank.com.vn", "Hóa đơn phí dịch vụ",
                    has_xml=True, has_pdf=False, has_link=False, cfg=EXCL)
    assert c.bucket != "ignore"


def test_exclude_does_not_affect_other_senders():
    c = score_email("hoadon@vnpt.vn", "Hóa đơn tháng 6",
                    has_xml=True, has_pdf=False, has_link=False, cfg=EXCL)
    assert c.bucket == "certain"


def test_whitelisted_sender_forced_certain():
    c = score_email("ketoan@nhacungcap.vn", "random subject", has_xml=False,
                    has_pdf=False, has_link=False, cfg=CFG)
    assert c.bucket == "certain"
    assert any("whitelist" in r.lower() for r in c.reasons)


def test_reasons_recorded():
    c = score_email("hoadon@misa.com.vn", "Hóa đơn điện tử", has_xml=True,
                    has_pdf=False, has_link=False, cfg=CFG)
    assert c.has_xml is True
    assert len(c.reasons) >= 2  # xml + issuer + keyword


def test_records_source_account():
    c = score_email("hoadon@misa.com.vn", "Hóa đơn", has_xml=True, has_pdf=False,
                    has_link=False, cfg=CFG, account="info@miyano.com.vn")
    assert c.account == "info@miyano.com.vn"


# ---------------------------------------- T48: lọc theo TIÊU ĐỀ (không phải người gửi)

def _cfg_loai_tru():
    return ClassifierConfig(
        issuer_domains=["vnpt", "viettel"],
        keywords=["hóa đơn", "invoice"],
        exclude_senders=["viettelpost.com.vn", "accounts.google.com"],
        exclude_subjects=["cảnh báo đăng nhập", "thông báo tài khoản trả trước"],
    )


def test_loai_theo_tieu_de_du_nguoi_gui_la_nha_phat_hanh_that():
    """VNPT là nhà phát hành THẬT — chặn cả người gửi sẽ đánh rơi HĐ VNPT chỉ-link.
    Nên 'Thông báo tài khoản trả trước' phải lọc theo tiêu đề."""
    c = score_email("EInvoice <hoadondientu@vnpt-invoice.vn>",
                    "Hóa đơn điện tử VNPT-INVOICE: Thông báo tài khoản trả trước",
                    has_xml=False, has_pdf=False, has_link=False, cfg=_cfg_loai_tru())
    assert c.bucket == "ignore"


def test_hoa_don_vnpt_that_van_qua_duoc():
    c = score_email("EInvoice <hoadondientu@vnpt-invoice.vn>",
                    "VNPT-INVOICE: Thông báo phát hành hóa đơn điện tử",
                    has_xml=False, has_pdf=False, has_link=True, cfg=_cfg_loai_tru())
    assert c.bucket != "ignore"


def test_co_xml_thi_luon_giu_du_khop_tieu_de_loai_tru():
    """Luật an toàn sẵn có: email mang XML thì không bao giờ bị loại."""
    c = score_email("noreply@viettelpost.com.vn",
                    "(Viettel Post) Cảnh báo đăng nhập tài khoản",
                    has_xml=True, has_pdf=False, has_link=False, cfg=_cfg_loai_tru())
    assert c.bucket != "ignore"


def test_loai_theo_nguoi_gui_van_hoat_dong():
    c = score_email("Google <no-reply@accounts.google.com>",
                    "Security alert for mvl.invoices2024@gmail.com",
                    has_xml=False, has_pdf=False, has_link=False, cfg=_cfg_loai_tru())
    assert c.bucket == "ignore"
