# Portal adapters

Adapter tải hóa đơn từ cổng tra cứu của từng nhà phát hành, cho các email
**chỉ có link + mã** (không đính kèm file).

Mỗi nhà phát hành có URL và cách lấy file khác nhau, **chỉ viết chính xác được
sau khi khảo sát email thật**. Đây là phần fragile nhất của tool.

## Tình trạng cổng (khảo sát thật 2026-07-08)

| Cổng | Cơ chế | Tự động (HTTP)? |
|------|--------|-----------------|
| **`*.einvoice.com.vn`** (saigoncoop…) | GET trang → CSRF token + `idHoaDon` → POST `/tai-ve-hoa-don` → ZIP (XML+PDF) | ✅ **`einvoice_com_vn.py`** (đã đăng ký) |
| **`einvoice.fast.com.vn`** (Fast) | Trang `index.aspx?c=` CÓ captcha, NHƯNG email có link ký `index.aspx?type=2&c=&hash=` trả **XML thẳng** (type=1/3 = PDF; c+hash chung, chỉ khác type) — không captcha | ✅ **`fast_einvoice.py`** (đã đăng ký) |
| meinvoice.vn (MISA) | SPA; JS đóng gói CDN mã hóa (`meinvoice.misacdn.net/…WebResource.axd`), `ApiUrl=app.meinvoice.vn`, hàm `downloadInvoice` dựng endpoint lúc chạy | ⏳ **cần xem XHR bằng trình duyệt** (DevTools) — HTTP thuần không dò ra |
| easyinvoice.com.vn (Thái Sơn) | SPA, endpoint `/Invoice/ConvertInv` dựng bằng JS | ⏳ **cần xem XHR bằng trình duyệt** |
| **`*-tt78.vnpt-invoice.com.vn`** (VNPT) | Link email `invoice/getinvoice?token=` trả **XML thẳng** (trang tra cứu mới có captcha, link email thì không) | ✅ **`vnpt_invoice.py`** (đã đăng ký) |
| ehoadon.vn | **ReCaptcha** ở trang tra cứu | ❌ cần trình duyệt + nhập captcha tay |
| `info.vietcombank.com.vn` (VCBDigibank) | Email "Biên lai chuyển tiền/thanh toán" — **biên lai ngân hàng, KHÔNG phải HĐ GTGT**, không có link tra cứu | — không dựng adapter; nên lọc khỏi ứng viên (classifier) |

**Pattern chung (VNPT + Fast)**: trang tra-cứu có captcha, nhưng email thông báo
phát hành kèm **link tải trực tiếp đã ký** (token/hash) bỏ qua captcha. Khi thêm
nhà phát hành mới, tìm link tải-thẳng trong **body email** trước khi kết luận
"cần trình duyệt".

**Lưu ý**: file tải từ cổng là **XML thật** → chạy pipeline như HĐ có XML (cột
`Nguồn` = `XML`, tin cậy như email đính kèm). Cổng có thể chậm/timeout/token hết
hạn → adapter trả `[]` và HĐ rơi vào "cần tải tay" (không làm sập batch).

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
