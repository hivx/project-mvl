"""Phiên HTTP dùng chung cho mọi adapter và bước dò cổng.

Vì sao phải có file này thay vì mỗi nơi tự ``requests.Session()``:

Cổng tra cứu của MISA (meinvoice.vn) chỉ trả file khi ``Accept`` có chứa
``text/html`` — tức khi phía gọi trông như trình duyệt đang mở trang. Xin
``*/*`` (mặc định của ``requests``), ``application/xml`` hay
``application/octet-stream`` thì nó trả **HTTP 200 kèm 0 byte**, không hề báo
lỗi. Đo được ngày 2026-08-27, tái lập nhiều lần, không phụ thuộc cookie/phiên.

Hậu quả của việc thiếu header này: mọi adapter đều nhận file rỗng, bước dò kết
luận nhầm là "cổng chặn captcha / cần trình duyệt", và ~64% hóa đơn chỉ-link bị
xếp nhầm sang nhóm không tự động được.

Nhà cung cấp khác có thể dùng mẹo chặn bot tương tự, nên MỌI request đi ra đều
phải qua đây.
"""
from __future__ import annotations

import requests

#: Bộ header tối thiểu để cổng coi ta là trình duyệt.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s
