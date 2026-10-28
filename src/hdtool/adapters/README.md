# Portal adapters

Tải hóa đơn từ cổng tra cứu cho các email **chỉ có link + mã** (không đính kèm).

## Từ Đợt 7: dò tự động trước, adapter code chỉ cho cổng phức tạp

Không còn phải viết một adapter Python cho mỗi cổng. Luồng mặc định
(`portal_probe.fetch_link_only`):

1. **Công thức trong `config/ncc-registry.yaml`** — nếu cổng này đã học rồi.
2. **Adapter code** trong thư mục này — cho cổng phức tạp (CSRF + POST + zip).
3. **Dò tự động** — lấy trang tra cứu, phân loại, POST form nếu cần, thử tối đa
   3 link tải, **chỉ nhận khi bytes parse ra `Invoice` hợp lệ**, rồi **ghi công
   thức vào registry** để lần sau đi tắt.

Registry là **bộ nhớ đệm**, không phải điều kiện tiên quyết: cổng chưa từng gặp
vẫn tải được ngay lần đầu. Công thức hỏng (cổng đổi URL) thì tự rơi xuống nhánh
dò để học lại — tự chữa lành.

Viết adapter code **chỉ khi** cổng cần nhiều bước mà một URL không diễn đạt nổi.

## Tình trạng cổng (khảo sát thật 2026-08-25 — xem `docs/superpowers/specs/2026-08-25-khao-sat-cong-tra-cuu.md`)

| Cổng | Cơ chế | Tự động (HTTP)? |
|------|--------|-----------------|
| **`*.einvoice.com.vn`** (saigoncoop…) | GET trang → CSRF token + `idHoaDon` → POST `/tai-ve-hoa-don` → ZIP (XML+PDF) | ✅ **`einvoice_com_vn.py`** (đã đăng ký) |
| **`einvoice.fast.com.vn`** (Fast) | Trang `index.aspx?c=` CÓ captcha, NHƯNG email có link ký `index.aspx?type=2&c=&hash=` trả **XML thẳng** (type=1/3 = PDF; c+hash chung, chỉ khác type) — không captcha | ✅ **`fast_einvoice.py`** (đã đăng ký) |
| meinvoice.vn (MISA) | **CAPTCHA** (không phải SPA như ghi nhận cũ): trang trả HTML thật, form có `txtCode` + `captcha$captchaTextbox`. Link tải `DownloadHandler.ashx?Type=xml&Code=` GET thuần trả **200 rỗng 0 byte** → cần phiên đã qua captcha | ❌ cần trình duyệt |
| easyinvoice.com.vn (Thái Sơn) | SPA; `Invoice/DownloadInvPdf` và `DownloadInvXml` trong mail đều trả HTML | ❌ cần trình duyệt |
| **`tracuuhoadon.ipos.vn`** | Mail kèm sẵn `Invoice/Download78?id=<id>` trả **XML thẳng** (còn `Invoice/getinvoice?token=` lại trả PDF) | ✅ **dò tự động lấy được** |
| `gsm-einvoice.hilo.com.vn` | Form `Filter.SearchKey` + CSRF, **không captcha** — nhưng mail không kèm mã | ⚠️ thiếu mã |
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
