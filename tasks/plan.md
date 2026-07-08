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

- [ ] **T14 — Khôi phục `excel.py`** (đang bị xóa → import gãy). Full test xanh lại.
- [ ] **T15 — Lọc tổng hợp theo 1 công ty**: `aggregate(only_company=...)`; hóa
  đơn công ty khác → `excluded` nhóm `cong_ty_khac` (không phải `sai_ben_mua`).
- [ ] **T16 — Thread `only_company` qua pipeline + cờ `--company`**: tách
  `build_report` (không ghi, trả result/skipped/manual) và cập nhật `cmd_report`.
- [ ] **T17 — Xuất CSV**: `csv_report.py` (bảng kê + tong-hop + bo-qua, UTF-8 BOM)
  + `write_report(fmt)` dispatch + cờ `--format {xlsx,csv}`; nhãn `cong_ty_khac`.
- [ ] **T18 — Menu tương tác**: `interactive.py` (`run_interactive`, input tiêm
  được); `run.py` thành launcher; `hdtool` không kèm lệnh → mở menu.
- [ ] **T19 — Tài liệu**: cập nhật `CLAUDE.md`, `settings.yaml`, `plan.md`; full test.

## Ghi chú

- T11 là phần fragile duy nhất, không làm mù được — chờ email thật.
- Cần người dùng cung cấp `MIYANO_MST` để bật lọc mua-vào (không phải task code).
