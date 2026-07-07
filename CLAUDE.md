# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này.

## Dự án

**hdtool** — công cụ CLI tổng hợp hóa đơn điện tử VN qua email ra Excel cho
Miyano/MVL. Quy trình 3 bước: quét IMAP (chỉ đọc) → nhận diện & tải hóa đơn →
parse XML + tổng hợp ra bảng kê Excel phục vụ kê khai GTGT.

Thiết kế chi tiết: `docs/superpowers/specs/2026-07-07-invoice-email-aggregator-design.md`.

## Nguyên tắc bất di bất dịch

1. **IMAP chỉ đọc.** Mọi truy cập hộp thư phải `readonly=True` + `BODY.PEEK`.
   KHÔNG bao giờ đánh dấu đã đọc, xóa, hay di chuyển email.
2. **Số liệu chỉ lấy từ XML** (chuẩn TCT). PDF chỉ là bản thể hiện. Hóa đơn chỉ
   có PDF → đánh dấu "cần nhập tay/OCR", không suy diễn số.
3. **Không commit bí mật.** `.env` chứa app password, đã nằm trong `.gitignore`.
   Trước khi commit luôn kiểm tra `git status` không có `.env`.
4. **Cấu hình, không hardcode.** Danh sách nhà phát hành, từ khóa, whitelist,
   độ nới ngày nằm trong `config/settings.yaml`. Sửa ở đó, không sửa code.

## Cấu trúc

```
src/hdtool/
  config.py      # nạp .env + settings.yaml -> Settings
  models.py      # dataclass Invoice, TaxLine, EmailCandidate
  xmlutil.py     # tìm phần tử theo local-name, bỏ qua namespace
  parse_xml.py   # XML chuẩn TCT -> Invoice
  mailscan.py    # IMAP readonly: quét + fetch (helper thuần tách riêng để test)
  classify.py    # chấm điểm email -> certain/suspect/ignore
  collect.py     # trích attachment (giải nén zip), dò link, lưu cây thư mục
  adapters/      # registry adapter portal theo nhà phát hành — hiện để trống
  aggregate.py   # khử trùng, xử lý thay thế, lọc mua-vào, gom theo thuế suất
  reports.py     # xuất danh sách ứng viên/nghi ngờ (CSV)
  excel.py       # xuất bảng kê + sheet tổng hợp
  pipeline.py    # orchestration report: XML trên đĩa -> Excel (không cần mạng)
  cli.py         # scan / collect / report / run
tests/           # pytest, có fixtures/ là XML mẫu chuẩn TCT
config/settings.yaml
docs/superpowers/specs/
tasks/plan.md    # task breakdown còn lại
```

## Lệnh hay dùng

```bash
make install      # tạo venv + cài editable + dev deps
make test         # ./.venv/bin/python -m pytest -q
./.venv/bin/hdtool scan   --from 2026-06-01 --to 2026-06-30
./.venv/bin/hdtool report --from 2026-06-01 --to 2026-06-30 -o out.xlsx
```

## Quy ước phát triển

- **TDD bắt buộc**: viết test (RED) → code tối thiểu (GREEN) → refactor. Fixtures
  XML trong `tests/fixtures/` là cách kiểm chứng chính (chưa có email thật).
- **Namespace-agnostic**: parse XML luôn qua `xmlutil` (khớp local-name) để chịu
  được khác biệt giữa các nhà phát hành.
- **Degrade an toàn**: thiếu `MIYANO_MST` → không lọc mua-vào, chỉ gắn cờ. Thiếu
  adapter portal → hóa đơn chỉ-link vào danh sách "cần tải tay", không làm sập.

## Bối cảnh quan trọng

- Hộp thư `info@miyano.com.vn` hiện **chưa có/rất ít** hóa đơn XML thật (khảo sát
  2026-07-07: 0 XML trên 478 email). Tool chạy đúng khi hóa đơn bắt đầu về.
- **Adapter portal chỉ viết được sau khi khảo sát email thật** của từng nhà phát
  hành — đây là phần duy nhất không làm mù được.
- `MIYANO_MST` (MST bên mua) chưa được cung cấp — cần điền vào `.env` để bật lọc.
