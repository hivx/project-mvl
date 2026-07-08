# Spec — Chọn công ty khi tổng hợp + menu tương tác + xuất CSV

Ngày: 2026-07-08. Nguồn: brainstorming với người dùng (Miyano/MVL).
Bổ sung cho: `2026-07-07-invoice-email-aggregator-design.md`.

## Bối cảnh

Hộp thư `anh.doan@medcons.vn` chứa hóa đơn mua-vào của **cả hai** pháp nhân:
`miyano` (MST 0109529507) và `medcons` (MST 0108186705). Công cụ hiện gộp cả hai
vào một bảng kê. Người dùng muốn:

1. Phân loại rõ theo **đúng 2 công ty nhận** (không lẫn).
2. Mỗi lần tổng hợp **chọn 1 công ty**; bảng kê chỉ chứa hóa đơn của công ty đó.
3. Một **file main tương tác**: chạy lên → nhập khoảng ngày, chọn công ty, chọn
   Excel/CSV → tự tải hóa đơn từ email rồi xuất bảng kê.
4. Xuất được **Excel hoặc CSV**.

## Quyết định đã chốt (brainstorming)

- **Cấu trúc thư mục GIỮ NGUYÊN**: `data/<công ty>/<YYYY-MM>/<người gửi>/`.
  Không đổi layout. `_khac` (gửi tới MST khác) và `_chua-ro-cong-ty` (XML
  hỏng/PDF-only) giữ nguyên.
- **Menu chính**: sau khi nhập → **tải mới từ email (readonly) rồi tổng hợp**.
- **Phạm vi báo cáo**: bảng kê chỉ gồm công ty đã chọn.
- **CSV**: 1 file bảng kê chính + 2 file phụ cùng thư mục (`-tong-hop.csv`,
  `-bo-qua.csv`). UTF-8 BOM.
- **Menu chọn 1 công ty mỗi lần** (không có tùy chọn "cả 2" — thêm sau nếu cần).

## Yêu cầu chức năng

### R1 — Sửa lỗi gãy import (`excel.py`)
`excel.py` bị xóa trong working tree nhưng `pipeline.py` vẫn import → khôi phục
từ git. Toàn bộ test phải xanh trở lại.

### R2 — Lọc tổng hợp theo 1 công ty
`aggregate()` nhận thêm `only_company: Optional[str]`:
- Vẫn phân loại theo **cả hai** MST bên mua (để phân biệt mua-vào vs CC nhầm).
- Nếu `only_company` được đặt: chỉ giữ trong `invoices`/tổng/`by_rate` các hóa
  đơn có `cong_ty == only_company`. Hóa đơn mua-vào của công ty **khác** (hợp lệ
  nhưng không phải công ty đang chọn) đưa vào `excluded` với lý do nhóm
  `cong_ty_khac` (KHÔNG phải `sai_ben_mua`).
- Nếu `only_company` là None: hành vi như cũ (gộp mọi công ty).

### R3 — Tách tổng hợp khỏi ghi file; xuất Excel hoặc CSV
- `pipeline.build_report(...)` trả `(result, skipped, manual)` và **không tự ghi**;
  nhận thêm `only_company`.
- `pipeline.write_report(result, path, fmt, skipped, manual)` điều phối:
  - `fmt="xlsx"` → `excel.write_workbook` (giữ nguyên).
  - `fmt="csv"` → `csv_report.write_bang_ke_csv`:
    - file chính `<path>.csv` = bảng kê (cùng cột với Excel).
    - `<base>-tong-hop.csv` = tổng hợp theo thuế suất.
    - `<base>-bo-qua.csv` = danh sách bỏ qua (có cột Nhóm).
    - Tất cả UTF-8 BOM (`utf-8-sig`).
- `cmd_report` gọi build + write; thêm cờ `--company <tên>` và
  `--format {xlsx,csv}` (mặc định `xlsx`).
- Nhóm skipped mới `cong_ty_khac` có nhãn hiển thị "Công ty khác (không thuộc kỳ
  báo cáo này)" ở cả Excel và CSV.

### R4 — File main tương tác
Module `interactive.py`, hàm `run_interactive(settings, input_fn=input, out=print)`
(input_fn/out tiêm được để unit-test không cần stdin thật):
- Nhập **từ ngày / đến ngày** (Enter để dùng `default_from/default_to`); validate
  ISO, nhập sai thì hỏi lại.
- Chọn **công ty** từ `settings.companies` (menu số); bắt buộc hợp lệ.
- Chọn **định dạng**: 1) Excel  2) CSV.
- Luồng: `collect` (IMAP readonly) → `build_report(only_company=...)` →
  `write_report(fmt=...)`. Tên file mặc định `bang-ke-<công ty>-<from>_<to>.<ext>`.
- Tách phần thuần (parse/validate input, dựng tên file, dựng kế hoạch) khỏi phần
  I/O để test được.
- `run.py` viết lại thành launcher gọi `run_interactive`.
- `hdtool` **không kèm subcommand** → mở menu tương tác. Các subcommand cũ
  (scan/collect/report/run/reorganize) giữ nguyên.

### R5 — Tài liệu
Cập nhật `CLAUDE.md` (mục cấu trúc/lệnh), `config/settings.yaml` (ghi chú), và
`tasks/plan.md`. Không đổi nguyên tắc bất di bất dịch (IMAP readonly, số từ XML).

## Ngoài phạm vi (YAGNI)
- Không đổi layout thư mục.
- Không viết adapter portal (chờ email thật).
- Không có tùy chọn "cả 2 công ty một lần".
- Không refactor phần không liên quan.

## Ràng buộc
- IMAP luôn `readonly`, `BODY.PEEK`. Số liệu chỉ từ XML.
- TDD: mỗi task RED → GREEN → full test → commit.
- Cấu hình ở `settings.yaml`, không hardcode danh sách công ty.
