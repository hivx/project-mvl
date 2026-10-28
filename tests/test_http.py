"""Phiên HTTP dùng chung — phải trông giống trình duyệt.

Bài học đắt giá 2026-08-27: cổng meinvoice CHỈ trả file khi ``Accept`` có chứa
``text/html``. Xin ``*/*`` (mặc định của ``requests``) thì nó trả HTTP 200 kèm
**0 byte**. Mọi adapter trước đây chỉ đặt User-Agent nên nhận file rỗng, và cả
một đợt chẩn đoán đã kết luận nhầm là "cổng chặn captcha / cần trình duyệt".
"""
import pytest

from hdtool.http import new_session

# Mọi nơi tự tạo phiên HTTP — thêm adapter mới thì thêm vào đây.
from hdtool import portal_probe
from hdtool.adapters import (einvoice_com_vn, fast_einvoice, registry_adapter,
                             vnpt_invoice)

MO_DUN = [portal_probe, registry_adapter, vnpt_invoice, fast_einvoice, einvoice_com_vn]


def test_accept_chua_text_html():
    """Chốt chặn của cả tool: thiếu cái này là tải về file rỗng."""
    assert "text/html" in new_session().headers.get("Accept", "")


def test_van_gui_user_agent():
    assert "Mozilla" in new_session().headers.get("User-Agent", "")


@pytest.mark.parametrize("mod", MO_DUN, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_moi_noi_deu_dung_phien_chung(mod):
    """Không module nào được tự dựng phiên trần — sẽ lặp lại lỗi file rỗng."""
    assert "text/html" in mod._new_session().headers.get("Accept", "")
