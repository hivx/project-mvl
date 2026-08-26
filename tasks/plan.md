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
- [x] **T30 — Adapter VNPT (`*-tt78.vnpt-invoice.com.vn`)**: spike thật cho thấy link
  email `invoice/getinvoice?token=` trả **XML thẳng** (không captcha — captcha chỉ ở
  trang tra cứu). Adapter GET link đó → XML. TDD mock HTTP. ~13 HĐ.

## Đợt 6 — OCR HĐ chỉ-PDF (ảnh scan) + adapter HTTP cho HĐ chỉ-link

Spec: `docs/superpowers/specs/2026-07-09-ocr-pdf-and-http-link-adapter.md`.
2 nhánh độc lập (A: OCR / B: adapter HTTP), làm song song.

- [x] **T31 — OCR fallback (nhánh A)**: `pdf_to_ocr_text` (pdftoppm 300dpi trang 1
  → tesseract -l vie, degrade rỗng khi thiếu binary); `extract_pdf_invoice` bóc
  text layer trước, thiếu text (<50 ký tự) → OCR, gắn `nguon="PDF-OCR"`. TDD mock.
- [x] **T32 — Cột Nguồn nhận `PDF-OCR`**: `bk_tt80_rows` (dùng chung Excel+CSV) phát
  `inv.nguon` verbatim → PDF-OCR chảy qua sẵn. Test khóa hành vi trong CSV.
- [x] **T33 — Spike Fast e-Invoice + Vietcombank (nhánh B)** (2026-07-09):
  * **Fast**: trang `index.aspx?c=` CÓ captcha, NHƯNG email có link ký
    `index.aspx?type=2&c=&hash=` trả **XML thẳng** (type=1/3 = PDF; c+hash giống
    nhau, chỉ khác type) — KHÔNG captcha → **khả thi HTTP**.
  * **Vietcombank (72)**: email `VCBDigibank@info.vietcombank.com.vn` "Biên lai
    chuyển tiền/thanh toán" = **biên lai NH, KHÔNG phải HĐ GTGT**, không có link →
    false positive của classifier, KHÔNG dựng adapter (đề xuất lọc → T36, chờ duyệt).
- [x] **T34 — Adapter Fast e-Invoice**: `fast_einvoice.py` (claim link ký type=&hash=,
  fetch XML type=2 + PDF type=1, degrade `[]`) + đăng ký registry. TDD mock HTTP;
  chạy thật HĐ số 736 (PYS, 53.635.000đ) qua đúng luồng `collect`.
- [x] **T35 — Tài liệu + chạy thật**: cập nhật `adapters/README.md`, `CLAUDE.md`,
  `plan.md`. Chạy full `hdtool collect --include-suspect` (2026-07-09): Fast HĐ 736
  tự tải về `data/medcons/2026-02/` (XML+PDF); danh sách "cần tải tay" **113→40**
  (−72 VCB nhờ T36, −1 Fast). 40 còn lại = cổng SPA/captcha (ngoài phạm vi).
  Thêm `test_pdf_ocr_integration.py` verify OCR end-to-end (skip nếu thiếu tesseract/gs).
- [x] **T36 — Lọc biên lai Vietcombank khỏi ứng viên** (bạn duyệt 2026-07-09):
  thêm `exclude_senders` (config) vào classifier; sender khớp + KHÔNG có XML →
  `ignore` (XML vẫn override để không mất HĐ thật). `settings.yaml` thêm
  `vcbdigibank`. Verify thật: ứng viên medcons 389→316, VCBDigibank còn 0. TDD.

## Đối chiếu mẫu MVL 6.26 (miyano 06/2026) — 2026-07-09

Chạy `report --company miyano --from 2026-06-01 --to 2026-06-30` so với
`docs/MVL 6.26_...xlsx`: **cấu trúc + 27 HĐ chung khớp 100% tiền**; tool giữ số 0
đầu `SHDon` đúng theo XML (mẫu bị Excel cắt). Mẫu 40 HĐ / 37.981.600; tool 27 HĐ /
10.019.380 → thiếu **13 HĐ (74% giá trị)** vì chưa có XML trong `data/`:
- **Nhóm A** (chỉ-link cổng SPA/captcha, chờ browser): meinvoice (CG GLOBAL, CÂY
  SUNG, TUẤN KIỆT), GSM/Xanh SM (hilo), Viettel K26DAB. → cần Chrome automation.
- **Nhóm B** (điều tra hộp thư 2026-07-09): **KHÔNG lấy được từ email** —
  ĐÔI CÁNH & MEGA không có email; GRAB chỉ có "E-Receipt" (HĐ ở app Grab); P.A &
  BẢO VỆ chỉ lẫn trong gói tài liệu/forward kế toán (đính kèm .doc/hỗn hợp, không
  phải HĐĐT chuẩn). **Quyết định: chấp nhận NHẬP TAY** (không nới classifier —
  rủi ro false-positive cao). Không đổi code.

## Đợt 7 — Tự động tra cứu & tải hóa đơn chỉ-link (cổng tự học)

Spec: `docs/superpowers/specs/2026-08-25-tu-dong-tra-cuu-tai-hoa-don.md`
Kế hoạch chi tiết (từng bước, có code): `docs/superpowers/plans/2026-08-25-tu-dong-tra-cuu-tai-hoa-don.md`

Đảo hướng: thay vì viết một adapter Python cho mỗi cổng, **tool tự dò** cách tải
từ link tra cứu có sẵn trong mail, **tự xác minh** bằng cách parse ra `Invoice`
hợp lệ, rồi **tự nhớ** công thức. Registry là *bộ nhớ đệm*, không phải điều kiện
tiên quyết — cổng chưa từng gặp vẫn tải được ngay lần đầu.

- [x] **T37 — Khảo sát**: 76 dòng chỉ-link = **44 HĐ khác nhau**. meinvoice (22)
  và ehoadon (6) là **CAPTCHA** chứ không phải SPA như README cũ ghi → 64% nằm
  ngoài tầm HTTP thuần. Link tải MISA GET thuần trả **200 rỗng 0 byte**. Chỉ
  `ipos.vn` giải trọn vẹn. Kết quả: `docs/superpowers/specs/2026-08-25-khao-sat-cong-tra-cuu.md`.
- [x] **T44 — Vá `save_invoice_files`**: trùng tên mà khác nội dung → thêm `-2`;
  trùng cả nội dung → dùng lại file cũ (giữ idempotent).
- [x] **T38 — `worklist.py`**: sổ `data/so-hoa-don-cho-tai.csv` tích lũy, merge
  KHÔNG đè ô người dùng tự điền (mã tra cứu, ghi chú), ghi qua file tạm.
- [x] **T39 — `lookup.py`**: chấm điểm link giữa 5–15 URL trong mail + bóc mã từ
  query, **từ path** (ehoadon `tracuu.ehoadon.vn/<mã>`) và từ nhãn (kể cả `MTC`).
  Đo thật: bóc đúng mã 100% cho 34 dòng meinvoice.
- [x] **T40 — `portal_probe.py` phần thuần**: `classify_page` (captcha xét TRƯỚC
  form) / `find_form` (mang hidden field) / `candidate_download_links` /
  `accept_files`. Hồi quy trên HTML thật của 4 cổng.
- [x] **T41 — `probe()` + tích hợp `collect`**: trần 5 request/HĐ, 3 ứng viên,
  nghỉ 1s. Regex anchor tách 2 bước (bản cũ backtrack siêu tuyến tính trên trang
  80–150KB). Chạy thật: tải tự động được 3 hóa đơn ipos.
- [x] **T42 — `ncc.py` + `RegistryAdapter`**: học công thức từ URL đã xác minh,
  đi tắt lần sau, công thức hỏng thì tự dò lại và ghi đè. Kèm sửa nhãn Trạng thái
  cho phản ánh chỗ tắc thật (chạy thật lộ ra 21 dòng ghi nhầm "thiếu mã").
- [x] **T43 — `hdtool ncc`** (+ `--tai`) và menu tự gọi, không hỏi thêm câu nào.
- [x] **T45 — Chạy thật + tài liệu**: 70 dòng sổ, **0 dòng thiếu chẩn đoán**.
- [ ] **T46 — (spec riêng, sau)** nhánh trình duyệt cho cổng SPA/captcha —
  **đây mới là chỗ có 64% giá trị còn lại**.

Thứ tự: **T37 → T44 → T38 → T39 → T40 → T41 → T42 → T43 → T45**.

## Ghi chú

- T11 là phần fragile duy nhất, không làm mù được — chờ email thật.
- Cần người dùng cung cấp `MIYANO_MST` để bật lọc mua-vào (không phải task code).
