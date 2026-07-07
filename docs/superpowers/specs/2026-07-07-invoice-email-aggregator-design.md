# Thiết kế: Công cụ tổng hợp hóa đơn điện tử qua email (hdtool)

Ngày: 2026-07-07
Trạng thái: Đã duyệt thiết kế, đang triển khai (Phương án A)

## Bối cảnh & phát hiện khảo sát

Mục tiêu: tổng hợp hóa đơn điện tử (HĐĐT) đầu vào của Miyano/MVL từ hộp thư
`info@miyano.com.vn` (Google Workspace, truy cập IMAP `imap.gmail.com:993` bằng
app password) ra file Excel bảng kê phục vụ kê khai GTGT.

Khảo sát read-only toàn bộ hộp thư (478 email, mọi thời điểm) cho thấy **0 file
XML HĐĐT**, PDF chủ yếu là chứng từ nhà cung cấp nước ngoài. Kết luận: hiện hộp
thư **chưa có/rất ít** HĐĐT VN. Người dùng xác nhận đây ĐÚNG là hộp thư sẽ nhận,
nên tool được build để chạy đúng khi hóa đơn bắt đầu về. Hệ quả:
- Parse bám **chuẩn XML Tổng cục Thuế (NĐ123/2020, TT78, QĐ1450/QĐ-TCT)**.
- Nhận diện email + adapter portal làm theo kiểu **cấu hình mở rộng được**;
  adapter portal để trống, chỉ viết khi `scan` phát hiện nhà phát hành thật.
- Kiểm thử bằng **fixture XML mẫu** thay cho email thật.

## Nguyên tắc
- **XML là nguồn số liệu duy nhất.** PDF chỉ là bản thể hiện. Hóa đơn chỉ có
  PDF → đánh dấu "cần nhập tay/OCR", không suy diễn số.
- **Read-only tuyệt đối với hộp thư**: SELECT readonly, không đánh dấu đã đọc,
  không xóa/di chuyển. Idempotent, chạy lại nhiều lần an toàn.
- YAGNI: không viết adapter portal khi chưa thấy nhà phát hành thật.

## Kiến trúc

CLI Python 3.12. Thư viện: `imaplib`/`email` (stdlib), `lxml`, `openpyxl`,
`python-dotenv`, `requests` (dành cho adapter portal về sau).

```
project-mvl/
  .env                 # IMAP creds + MST (gitignored)
  .env.example
  .gitignore
  config/settings.yaml # whitelist người gửi, từ khóa, padding ngày
  src/hdtool/
    __init__.py
    config.py          # nạp .env + settings.yaml
    models.py          # dataclass Invoice, TaxLine, EmailCandidate
    xmlutil.py         # tìm phần tử theo local-name, bỏ qua namespace
    parse_xml.py       # XML chuẩn TCT -> Invoice
    mailscan.py        # IMAP readonly, quét cửa sổ ngày rộng
    classify.py        # chấm điểm invoice/nghi ngờ/bỏ; whitelist
    collect.py         # tải attachment; dispatch portal adapter
    adapters/          # registry theo domain/URL — ban đầu rỗng
      __init__.py
    aggregate.py       # khử trùng, trạng thái, lọc mua-vào, gom theo thuế suất
    excel.py           # xuất bảng kê + sheet tổng hợp
    cli.py             # scan / collect / report / run
  data/                # file tải về + Excel (gitignored)
  tests/
    fixtures/          # XML mẫu: 10/8/5/0/KCT, hủy, thay thế, trùng
    test_parse_xml.py
    test_aggregate.py
    test_classify.py
    test_excel.py
```

## Luồng dữ liệu
`scan` (IMAP quét cửa sổ rộng → chấm điểm) → `collect` (tải XML/PDF về cây
`data/<kỳ YYYY-MM>/<slug_nhà_cung_cấp>/`) → `parse` (XML→Invoice) →
`aggregate` (khử trùng/lọc/gom) → `excel`.

## Ba chỗ khó

### 4.1 Lệch kỳ (ngày email ≠ ngày hóa đơn)
Cửa sổ tìm email = `[from − PAD_BEFORE, to + PAD_AFTER]` (mặc định 15/45 ngày,
cấu hình trong settings). Sau khi có XML, **lọc lại theo `NLap` ∈ [from, to]**.
Bắt đúng hóa đơn tháng 6 gửi đầu tháng 7.

### 4.2 Nhận diện email hóa đơn (chấm điểm)
Tín hiệu + trọng số: có `.xml` đính kèm (mạnh nhất) > domain nhà phát hành >
từ khóa tiêu đề ("hóa đơn", "invoice", "HĐĐT"...) > có link tra cứu. Ngưỡng chia
3 rổ: **chắc chắn / nghi ngờ / bỏ**. Rổ "nghi ngờ" xuất danh sách để người dùng
duyệt. **Whitelist** người gửi đã biết → tự động nhận. Danh sách nhà phát hành &
từ khóa nằm trong `settings.yaml` để mở rộng.

### 4.3 Nhánh portal (fragile)
`collect` chia 2 nhánh:
- **Có attachment**: tải thẳng XML + PDF. Ưu tiên XML.
- **Chỉ link + mã**: tra registry adapter theo domain/URL. Ban đầu registry
  rỗng → hóa đơn chỉ-link đưa vào danh sách "cần tải tay". Khi `scan` cho biết
  nhà phát hành thật, viết adapter riêng cho từng cái (Viettel/VNPT/MISA/...).

## Parse XML (chuẩn TCT)
Trích (tìm theo local-name, bỏ qua namespace để chịu được khác biệt nhà phát hành):
- `TTChung`: KHMSHDon (ký hiệu mẫu số), KHHDon (ký hiệu), SHDon (số HĐ), NLap
  (ngày lập), DVTTe (đơn vị tiền), TGia (tỷ giá).
- `NBan`: Ten, MST (bên bán). `NMua`: Ten, MST (bên mua).
- `TToan`: TgTCThue (tổng chưa thuế), TgTThue (tổng thuế), TgTTTBSo (tổng thanh
  toán); danh sách `THTTLTSuat/LTSuat`: TSuat, ThTien (chưa thuế), TThue (thuế).
- **Trạng thái**: mặc định "gốc". Nếu có block hóa đơn liên quan (thay thế/điều
  chỉnh) → gán "thay thế"/"điều chỉnh" kèm số HĐ bị thay. **"Hủy"** không nằm
  chắc trong XML gốc (ghi ở TCT) → chỉ đánh dấu "nghi hủy" khi có HĐ thay thế
  trỏ tới; không khẳng định mù.

## Aggregate
- **Khử trùng** theo khóa `(MST người bán, ký hiệu, số HĐ)`. Giữ bản mới nhất.
- Nhận diện **thay thế/điều chỉnh** qua trạng thái; hóa đơn bị thay thế → đánh
  dấu để loại khỏi tổng.
- **Lọc mua-vào**: nếu `MIYANO_MST` được cấu hình → chỉ giữ hóa đơn có MST người
  mua ∈ tập MST của Miyano (loại email CC nhầm). Nếu chưa cấu hình → **không lọc,
  chỉ gắn cờ** (degrade an toàn).
- Gom theo mức thuế suất: 10 / 8 / 5 / 0 / KCT (không chịu thuế) / KKKNT (không
  kê khai).

## Excel
- Sheet **Bảng kê**: Ngày HĐ | Ký hiệu | Số HĐ | MST bán | Tên bán | Tiền chưa
  thuế | Thuế suất | Tiền thuế | Tổng tiền | Loại (mua/bán) | Trạng thái
  (gốc/thay thế/điều chỉnh/nghi hủy) | Link XML | Link PDF | Nguồn (Message-ID).
  Dòng **tổng cộng** ở cuối.
- Sheet **Tổng hợp theo thuế suất**: nhóm 10/8/5/0/KCT → số phục vụ kê khai GTGT.

## Cấu hình & bảo mật
- `.env` (gitignored): `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_APP_PASSWORD`,
  `MIYANO_MST` (danh sách MST bên mua, phân tách bằng dấu phẩy).
- `.env.example`: bản mẫu không chứa bí mật.
- `settings.yaml`: whitelist người gửi, danh sách domain nhà phát hành, từ khóa,
  padding ngày, ngưỡng chấm điểm.

## Lỗi & kiểm thử
- Xử lý lỗi theo từng hóa đơn: 1 file XML hỏng không làm sập cả kỳ; gom vào
  "báo cáo bỏ qua" (sheet/log riêng).
- TDD trên fixture XML mẫu bao phủ: các mức thuế 10/8/5/0/KCT, hóa đơn thay thế,
  hóa đơn trùng, hóa đơn của bên mua khác (để test lọc mua-vào), XML hỏng.

## CLI
- `hdtool scan --from YYYY-MM-DD --to YYYY-MM-DD` — dò + xuất danh sách chắc
  chắn/nghi ngờ (không tải).
- `hdtool collect --from --to` — tải file về cây thư mục kỳ/nhà cung cấp.
- `hdtool report --from --to [-o out.xlsx]` — parse + tổng hợp → Excel.
- `hdtool run --from --to` — chạy cả chuỗi scan→collect→report.

## Ngoài phạm vi (hiện tại)
- Adapter portal cụ thể (viết khi có nhà phát hành thật).
- OCR PDF (chỉ đánh dấu "cần nhập tay").
- Tra cứu trạng thái hủy trực tiếp trên cổng TCT.
