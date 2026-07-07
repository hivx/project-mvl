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
