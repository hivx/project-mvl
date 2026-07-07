# Portal adapters

Adapter tải hóa đơn từ cổng tra cứu của từng nhà phát hành, cho các email
**chỉ có link + mã** (không đính kèm file).

Thư mục này **cố ý để trống**: mỗi nhà phát hành (Viettel/sinvoice, VNPT,
MISA/meinvoice, EasyInvoice...) có URL và cách lấy file khác nhau, **chỉ viết
chính xác được sau khi khảo sát email thật**. Đây là phần duy nhất của tool
không làm mù được.

## Hợp đồng dự kiến (khi thêm adapter đầu tiên)

```python
class PortalAdapter:
    #: chuỗi con để nhận diện adapter theo domain/URL của link tra cứu
    match_hints: list[str]

    def can_handle(self, url: str) -> bool: ...

    #: trả về các file (xml/pdf) tải được từ trang tra cứu
    def fetch(self, url: str, code: str | None) -> list["Attachment"]: ...
```

Registry sẽ chọn adapter theo `can_handle(url)`. Hóa đơn chỉ-link mà **chưa có
adapter** phải rơi vào danh sách "cần tải tay" — không được làm sập pipeline.

## Quy trình thêm adapter

1. Chạy `hdtool scan` trên kỳ có hóa đơn thật để biết nhà phát hành nào xuất hiện.
2. Lấy 1-2 email mẫu của nhà phát hành đó, khảo sát link + luồng tải file.
3. Viết adapter + test (mock HTTP), đăng ký vào registry.
