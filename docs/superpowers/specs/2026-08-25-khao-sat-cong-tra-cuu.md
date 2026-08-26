# Khảo sát cổng tra cứu hóa đơn chỉ-link (T37)

Ngày: 2026-08-25. Kỳ khảo sát: NLap 2026-06-01 → 2026-06-30 (cửa sổ mail
2026-05-17 → 2026-08-14). Hộp thư quét: `anh.doan@medcons.vn` +
`mvl.invoices2024@gmail.com`.

**Không quét được `info@miyano.com.vn`** — app password hết hiệu lực
(`[AUTHENTICATIONFAILED] Invalid credentials`). Theo `CLAUDE.md` hộp này gần như
không có hóa đơn XML nên ảnh hưởng dự kiến nhỏ, nhưng con số dưới đây là **chưa
đủ 3 hộp thư**.

## Kết quả tổng

- **228 hóa đơn có file** đã tải về (đính kèm XML/PDF hoặc adapter sẵn có).
- **76 dòng chỉ-có-link** → sau khi khử trùng theo mã tra cứu còn **44 hóa đơn
  khác nhau** (một hóa đơn thường xuất hiện ở cả hai hộp thư do forward).

## Phân loại theo cổng — **đo thật, không suy đoán**

Mỗi trang được `portal_probe.classify_page` chấm trên HTML tải về thật
(lưu tại `data/_chan-doan/`).

| Cổng | HĐ khác nhau | Loại trang | HTTP thuần tải được? |
|------|-------------:|-----------|----------------------|
| `meinvoice.vn` (MISA) | **22** | **captcha** (`captcha$captchaTextbox` trong form) | ❌ |
| `tracuu.ehoadon.vn` (BKAV) | **6** | **captcha** (ASP.NET `__VIEWSTATE` + captcha) | ❌ |
| (không có link trong mail) | 7 | — (SMBC eInvoice…) | ❌ không có gì để đi theo |
| `*.easyinvoice.com.vn` / `.vn` | 4 | **spa**; `DownloadInvPdf`/`DownloadInvXml` đều trả HTML | ❌ |
| `viettelpost.com.vn` | 2 | — | ❌ **không phải hóa đơn** (bảng kê cước + cảnh báo đăng nhập) |
| `tracuuhoadon.ipos.vn` | 1 | link tải nằm sẵn trong mail | ✅ **được** |
| `gsm-einvoice.hilo.com.vn` | 1 | **form**, KHÔNG captcha (`Filter.SearchKey` + CSRF) | ⚠️ có thể, nhưng mail không kèm mã |
| `clienttool-cadmin.vnpt-invoice.com.vn` | 1 | link công cụ, không phải link HĐ | ❌ |

## Trả lời Open Questions của spec

**1. Link tải MISA `DownloadHandler.ashx?Type=xml&Code=…` có tải được bằng GET
thuần không? → KHÔNG.** Trả `200` nhưng **body rỗng 0 byte, không content-type**
— kể cả với chính link mẫu người dùng đưa, và với hai mã lấy tươi từ mail. Cần
phiên/cookie/referer từ trang tra cứu đã qua captcha.

**2. Trang tra cứu meinvoice có phải SPA không? → KHÔNG, là CAPTCHA.** Trang trả
HTML thật 82KB, có `<form>` với ô `txtCode` + `captcha$captchaTextbox`. README
cũ ghi "SPA" là **sai** — phải sửa. Kết luận thực tế không đổi: HTTP thuần không
qua được.

**3. Quy trình dò (nấc 1) ăn được bao nhiêu? → Rất ít: 1–2 trên 44 (~4%).**
Chỉ `ipos.vn` chắc chắn được; `hilo` may ra. **28/44 = 64% nằm sau captcha**
(meinvoice + ehoadon).

**4. Cổng nào cần cookie phiên? →** MISA cần (câu 1). Các cổng còn lại chưa xác
định vì đã chặn ở captcha trước đó.

## Phát hiện phụ có giá trị

- **`tracuuhoadon.ipos.vn` giải được trọn vẹn, đã kiểm chứng end-to-end.** Mail
  kèm sẵn `Invoice/Download78?id=<id>` trả `application/xml` 19KB; đưa qua
  `accept_files` ra hóa đơn thật: **số 00004279, ký hiệu C26MPP, 2026-07-16,
  VITA HOLIDAY → MIYANO, 1.561.521đ**. Lưu ý `Invoice/getinvoice?token=` (giống
  hệt pattern VNPT) ở cổng này lại trả **PDF**, không phải XML.
- **`ehoadon` lộ URL tra cứu thật** `TCHD?MTC=<mã>` — mã nằm trong **path** của
  link trong mail (`tracuu.ehoadon.vn/UTAWCE3X5A5`), không phải trong query.
  `lookup.code_from_url` hiện chỉ đọc query → **cần bổ sung bóc mã từ path**.
  Tiêu đề mail cũng ghi `MTC: <mã>` → nên thêm nhãn `MTC` vào `_CODE_LABELS`.
- **Nhiễu classifier**: ViettelPost "Cảnh báo đăng nhập tài khoản" và "Bảng kê
  cước chuyển phát" lọt vào ứng viên. Giống ca Vietcombank ở T36 → nên thêm vào
  `exclude_senders`.
- **SMBC eInvoice** (7 HĐ): mail không có đính kèm **và** không có link tra cứu →
  không lấy được từ email bằng bất kỳ cách nào.

## Kết luận cho lộ trình

Quy trình dò HTTP thuần (T41–T43) **không phải chỗ có giá trị lớn nhất** với dữ
liệu thật: nó gỡ được ~2/44 hóa đơn. Giá trị nằm ở **nhánh trình duyệt (T46)**,
vốn bị spec đẩy ra ngoài phạm vi — 28/44 hóa đơn đang bị chặn bởi captcha ở đúng
hai cổng (`meinvoice`, `ehoadon`), và cả hai đều là **cổng dùng đi dùng lại
tháng này qua tháng khác**, nên vượt được một lần là dùng mãi.

Hạ tầng T38–T43 **không phí**: nhánh trình duyệt vẫn dùng lại nguyên `worklist`
(sổ), `ncc` (registry), `accept_files` (chốt xác minh) và
`candidate_download_links`. Nhưng thứ tự ưu tiên nên được xem lại.
