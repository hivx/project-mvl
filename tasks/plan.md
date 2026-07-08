# Kế hoạch triển khai hdtool

Nguồn: `docs/superpowers/specs/2026-07-07-invoice-email-aggregator-design.md`.
Mỗi task: RED → GREEN → chạy full test → commit.

## Đã xong

- [x] **T1 — Parse XML chuẩn TCT** (`parse_xml`, `xmlutil`, `models`): số HĐ, ký
  hiệu, NLap, MST/tên bán+mua, tổng, danh sách thuế suất, trạng thái thay thế.
- [x] **T2 — Aggregate**: khử trùng, thay thế→nghi hủy, lọc mua-vào, gom thuế suất.
- [x] **T3 — Classify**: chấm điểm email → certain/suspect/ignore + whitelist.
- [x] **T4 — Excel**: sheet Bảng kê + Tổng hợp theo thuế suất + Bỏ qua, dòng tổng.
- [x] **T5 — Config**: nạp `.env` + `settings.yaml`, parse MST.
- [x] **T6 — Collect**: trích attachment, giải nén zip, dò link, cây thư mục.
- [x] **T7 — Mailscan**: IMAP read-only, cửa sổ ngày, fetch (helper thuần test được).
- [x] **T8 — Pipeline + CLI**: report XML→Excel; lệnh scan/collect/report/run.
- [x] **T9 — Xuất danh sách ứng viên/nghi ngờ ra CSV** (`reports`), gắn vào `scan`.

## Còn lại

- [x] **T10 — Idempotent collect**: manifest message-id đã tải để không tải lại;
  bỏ qua file đã có. (Test được không cần mạng.)
- [x] **T11a — Khung adapter portal**: contract `PortalAdapter` + registry +
  fallback "cần tải tay"; `collect` thử adapter cho hóa đơn chỉ-link. Registry
  rỗng mặc định (`hdtool/adapters/`).
- [~] **T11b — Adapter cho nhà phát hành cụ thể**: đã có **template scaffold**
  (`adapters/example_issuer.py` — no-op, không đăng ký, `fetch` raise). Logic
  THẬT vẫn CHẶN cho tới khi có email mẫu link-only. Khảo sát hộp thư 2 lần
  (2026-07-07): 78/478 email giống hóa đơn nhưng **0 có link tra cứu** → chưa
  có mẫu để dựng. Có mẫu → copy template, điền `fetch`, viết test mock HTTP.
- [x] **T12 — Đánh dấu hóa đơn PDF-only "cần nhập tay"** rõ ràng trong report
  (hiện chỉ vào "Bỏ qua" khi thiếu XML). Cân nhắc sheet riêng.
- [ ] **T13 — (Tùy chọn) Tra cứu trạng thái hủy trên cổng TCT** để khẳng định
  "hủy" thay vì "nghi hủy". Rủi ro/độ phức tạp cao, để sau.

## Đợt 2 — Chọn công ty + menu tương tác + CSV

Spec: `docs/superpowers/specs/2026-07-08-company-report-selection-and-interactive.md`.

- [x] **T14 — Khôi phục `excel.py`** (đang bị xóa → import gãy). Full test xanh lại.
- [x] **T15 — Lọc tổng hợp theo 1 công ty**: `aggregate(only_company=...)`; hóa
  đơn công ty khác → `excluded` nhóm `cong_ty_khac` (không phải `sai_ben_mua`).
- [x] **T16 — Thread `only_company` qua pipeline + cờ `--company`**: tách
  `build_report` (không ghi, trả result/skipped/manual) và cập nhật `cmd_report`.
- [x] **T17 — Xuất CSV**: `csv_report.py` (bảng kê + tong-hop + bo-qua, UTF-8 BOM)
  + `write_report(fmt)` dispatch + cờ `--format {xlsx,csv}`; nhãn `cong_ty_khac`.
- [x] **T18 — Menu tương tác**: `interactive.py` (`run_interactive`, input tiêm
  được); `run.py` thành launcher; `hdtool` không kèm lệnh → mở menu.
- [x] **T19 — Tài liệu**: cập nhật `CLAUDE.md`, `settings.yaml`, `plan.md`; full test.

## Đợt 3 — Tinh chỉnh sau lần chạy thật (2026-07-08)

Phát hiện khi chạy thật cả 2 hộp thư (263 file tải về, 109 HĐ miyano):

- [x] **T20 — Lọc "Cần nhập tay" theo công ty được chọn**: khi `only_company`
  đặt, `build_report` chỉ quét PDF-only trong `data/<công ty>/` (không gộp PDF của
  medcons/_chua-ro vào báo cáo miyano). Thuần offline, test bằng fixtures.
- [x] **T21 — Ghi danh sách "cần tải tay" (HĐ chỉ-link) ra CSV**: `collect` xuất
  `data/can-tai-tay-<from>_<to>.csv` (hộp thư, người gửi, tiêu đề, nhà phát hành,
  link tra cứu) để tải tay. Helper thuần `write_manual_links_csv` test được.
- [ ] **T22 — (HOÃN, cần bạn duyệt riêng) Adapter cổng thật** (meinvoice/
  easyinvoice) tải HĐ chỉ-link — có gọi HTTP ra ngoài, rủi ro cao hơn.

## Đợt 4 — Xuất Excel 4 sheet giống file mẫu

Spec: `docs/superpowers/specs/2026-07-08-excel-4-sheets-like-sample.md`.
Mẫu: `docs/MVL 6.26_tai-hoa-don_muaVao_...xlsx` (4 sheet, cấp dòng SP).

- [x] **T23 — Model + parser dòng SP & trường mở rộng**: `ProductLine`, thêm
  địa chỉ/CKTM/phí/tỷ giá/ngày ký/mã tra cứu vào `Invoice`; parse `DSHHDVu`.
  Fixture XML tổng hợp có dòng SP + chiết khấu. Test `test_parse_xml`.
- [x] **T24 — Writer 4 sheet**: viết lại `write_workbook` xuất Chi tiết SP / BK
  TT80 / DS hóa đơn / DS sản phẩm (khớp cột mẫu) + giữ Bỏ qua/Cần nhập tay;
  helper `_display_lines`, nhãn TChat, loại HĐ, dòng chiết khấu âm. Test `test_excel`.
- [x] **T25 — CSV theo BK TT80 + truyền kỳ**: CSV bảng kê đổi sang cột TT80;
  `write_report`/pipeline truyền from/to cho tiêu đề sheet. Test.
- [x] **T26 — Tài liệu + chạy thật**: cập nhật CLAUDE.md; xuất lại bảng kê miyano
  kỳ 06/2026, đối chiếu với file mẫu.

## Đợt 5 — HĐ chỉ-PDF (bóc text) + HĐ chỉ-link (tải cổng), cột Nguồn

Spike cổng (2026-07-08): token-portal (easyinvoice/saigoncoop/meinvoice/fast)
**không captcha** nhưng nút tải XML chạy JS; ehoadon/VNPT **có ReCaptcha**.
pdftotext có sẵn; HĐĐT PDF có lớp text (bóc trực tiếp). Quyết định: gộp chung,
thêm cột **Nguồn** (XML/PDF/Cổng).

- [x] **T27 — Cột "Nguồn"**: `Invoice.nguon` (mặc định "XML"); thêm cột Nguồn ở
  CUỐI các sheet + CSV (giữ nguyên cột giống mẫu). Aggregate giữ nguon. TDD.
- [x] **T28 — Bóc PDF**: `pdf_extract.py` — `pdftotext` + `parse_pdf_text` (thuần,
  test trên text mẫu Golden Gate) → `Invoice(nguon="PDF")` cho HĐ chỉ-PDF; gộp vào
  pipeline (gắn cờ). Xử lý HĐ Golden Gate + PDF medcons.
- [x] **T29 — Adapter cổng qua HTTP (hướng 2, automation)**. Spike thật (2026-07-08):
  saigoncoop `*.einvoice.com.vn` tải được bằng HTTP — GET trang → `__RequestVerification
  Token` + `idHoaDon` → POST `/tai-ve-hoa-don` → ZIP chứa XML/PDF. Nền tảng
  einvoice.com.vn dùng chung nhiều nhà phát hành.
  - [x] **T29a — Adapter `einvoice.com.vn`**: `parse_download_form` + `fetch`
    (GET→POST→giải nén zip→Attachment), đăng ký registry. TDD mock HTTP.
  - [x] **T29b — Tích hợp collect**: HĐ chỉ-link qua adapter → lưu `data/`; chạy
    thật 1 HĐ saigoncoop để kiểm chứng.
  - [x] **T29c — Mở rộng + tài liệu**: đánh giá meinvoice/easyinvoice (SPA) &
    ehoadon/VNPT (captcha — để trình duyệt/tay); ghi rõ cổng nào tự động được.
- [x] **T29d — Chạy collect thật**: adapter einvoice.com.vn tự tải HĐ saigoncoop
  (244213) về `data/medcons/2025-12/` — XML 242→244. Automation chạy end-to-end.
- [ ] **T30 — Adapter VNPT (`*-tt78.vnpt-invoice.com.vn`)**: spike thật cho thấy link
  email `invoice/getinvoice?token=` trả **XML thẳng** (không captcha — captcha chỉ ở
  trang tra cứu). Adapter GET link đó → XML. TDD mock HTTP. ~13 HĐ.

## Ghi chú

- T11 là phần fragile duy nhất, không làm mù được — chờ email thật.
- Cần người dùng cung cấp `MIYANO_MST` để bật lọc mua-vào (không phải task code).
