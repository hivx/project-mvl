# hdtool — Tổng hợp hóa đơn điện tử VN qua email ra Excel

Quét hộp thư (IMAP, **chỉ đọc**), nhận diện email hóa đơn điện tử, tải file
XML/PDF về local, rồi tổng hợp ra file Excel bảng kê phục vụ kê khai GTGT.

Số liệu **chỉ lấy từ XML** (bản gốc theo chuẩn Tổng cục Thuế). PDF chỉ lưu làm
bản thể hiện.

## Cài đặt

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .
```

## Cấu hình

1. Sao chép `.env.example` thành `.env` rồi điền:
   - `IMAP_USER`, `IMAP_APP_PASSWORD` (app password của Gmail/Workspace).
   - `MIYANO_MST`: mã số thuế **bên mua** của Miyano/MVL (nhiều pháp nhân thì
     phân tách bằng dấu phẩy). Để trống ⇒ không lọc mua-vào, chỉ gắn cờ.
   - `.env` đã được `.gitignore` — không bao giờ commit.
2. Tinh chỉnh nhận diện trong `config/settings.yaml` (danh sách domain nhà phát
   hành, từ khóa tiêu đề, whitelist người gửi, độ nới ngày). Không cần sửa code.

## Sử dụng

Tham số `--from`/`--to` là khoảng **ngày lập hóa đơn** (NLap), không phải ngày
email đến. Tool tự quét rộng ngày email `[from-15, to+45]` rồi lọc lại theo NLap.

```bash
# 1) Dò email hóa đơn (chỉ đọc, không tải) — xem rổ chắc chắn / nghi ngờ
hdtool scan   --from 2026-06-01 --to 2026-06-30

# 2) Tải file hóa đơn về data/<kỳ>/<nhà cung cấp>/
hdtool collect --from 2026-06-01 --to 2026-06-30 [--include-suspect]

# 3) Parse + tổng hợp ra Excel
hdtool report  --from 2026-06-01 --to 2026-06-30 -o bang-ke-062026.xlsx

# Hoặc chạy cả chuỗi
hdtool run     --from 2026-06-01 --to 2026-06-30 -o bang-ke-062026.xlsx
```

## File Excel xuất ra

- **Bảng kê**: mỗi dòng 1 hóa đơn (ngày, ký hiệu, số HĐ, MST + tên người bán,
  tiền chưa thuế, thuế suất, tiền thuế, tổng, loại mua/bán, trạng thái, đường
  dẫn XML/PDF, nguồn) + dòng tổng cộng.
- **Tổng hợp theo thuế suất**: gom 10/8/5/0/KCT/KKKNT → số kê khai GTGT.
- **Bỏ qua**: hóa đơn ngoài kỳ, sai bên mua, XML lỗi (cần xem lại/nhập tay).

## Giới hạn hiện tại (theo thiết kế)

- **Hóa đơn chỉ có link tra cứu** (không đính kèm file): tool liệt kê vào danh
  sách "cần tải tay" cho tới khi có **adapter portal** cho đúng nhà phát hành đó
  (`src/hdtool/adapters/`). Adapter chỉ viết được khi khảo sát email thật.
- **Hóa đơn hủy**: trạng thái hủy ghi ở cơ quan thuế, không nằm chắc trong XML
  gốc → tool chỉ đánh dấu "nghi hủy" khi có hóa đơn thay thế trỏ tới.
- **PDF không kèm XML**: không lấy số tự động (đánh dấu cần nhập tay/OCR).

## Kiểm thử

```bash
./.venv/bin/python -m pytest -q
```

Thiết kế chi tiết: `docs/superpowers/specs/2026-07-07-invoice-email-aggregator-design.md`.
