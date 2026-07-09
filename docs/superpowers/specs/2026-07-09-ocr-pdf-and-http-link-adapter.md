# Spec: OCR hóa đơn chỉ-PDF (ảnh scan) + adapter HTTP cho HĐ chỉ-link

Ngày: 2026-07-09. Nguồn yêu cầu: người dùng (Miyano/MVL).
Nối tiếp: Đợt 5 (`2026-07-08-*`), `tasks/plan.md`.

## 1. Objective (làm gì & vì sao)

Hai lỗ hổng còn lại trong thu thập số liệu HĐĐT, gộp **1 spec, 2 nhánh độc lập**:

- **Nhánh A — OCR HĐ chỉ-PDF ảnh scan.** Hiện `pdf_extract.py` chỉ bóc **lớp
  text** bằng `pdftotext`. PDF là **ảnh scan** (không lớp text) → trả `None` →
  rơi vào "cần nhập tay", **mất số liệu**. Cần OCR (tesseract tiếng Việt) làm
  fallback để những HĐ này cũng vào được bảng kê (gắn cờ Nguồn để đối soát).
- **Nhánh B — Tải HĐ chỉ-link qua adapter HTTP dễ.** 113 HĐ đang nằm trong
  `data/can-tai-tay-*.csv` vì chưa có adapter. Với các cổng mà **một GET HTTP
  thuần trả thẳng file** (ứng viên: **Fast e-Invoice**, **Vietcombank** — 72 dòng),
  viết adapter để tự tải về XML/PDF **đối soát**. Cổng SPA/captcha
  (meinvoice/easyinvoice/ehoadon) **giữ nguyên** danh sách tải tay.

**Ai dùng:** kế toán MVL kê khai GTGT. **Thành công =** ít HĐ "cần tải tay/nhập
tay" hơn, và mọi HĐ tải/bóc được đều có cột **Nguồn** đúng để biết độ tin cậy.

**Ngoài phạm vi (KHÔNG làm trong spec này):** browser automation (Chrome), giải
captcha, adapter SPA (meinvoice/easyinvoice). Nếu spike cho thấy Fast/Vietcombank
cũng cần JS/captcha → **không dựng adapter giả**, để nguyên tải tay (degrade an toàn).

## 2. Tech Stack

Không thêm thư viện Python. OCR đi theo đúng style hiện có (subprocess thuần):
- `pdftoppm` (poppler — **đã có** `/usr/bin/pdftoppm`) render PDF→PNG 300dpi.
- `tesseract-ocr` + `tesseract-ocr-vie` (**chưa cài** — xem Boundaries).
- Nhánh B: `requests` (đã dùng trong adapter sẵn có).

## 3. Commands

```bash
make test                                   # ./.venv/bin/python -m pytest -q
sudo apt-get install -y tesseract-ocr tesseract-ocr-vie   # ASK FIRST (nhánh A, để chạy thật)
./.venv/bin/hdtool report --from 2026-01-01 --to 2026-06-30 --company miyano --format csv
./.venv/bin/hdtool collect --from 2026-01-01 --to 2026-07-08   # readonly IMAP + adapter
```

## 4. Project Structure (file đụng tới)

```
src/hdtool/pdf_extract.py        # +pdf_to_ocr_text(); extract_pdf_invoice fallback OCR
src/hdtool/adapters/fast_einvoice.py   # (mới, NẾU spike khả thi) adapter Fast e-Invoice
src/hdtool/adapters/vietcombank.py     # (mới, NẾU spike khả thi) adapter Vietcombank
src/hdtool/adapters/__init__.py  # đăng ký adapter mới
src/hdtool/adapters/README.md    # cập nhật bảng tình trạng cổng
tests/test_pdf_extract.py        # test OCR path (mock tesseract) + nguon flag
tests/test_adapters.py           # test adapter mới (mock HTTP)
docs/.../scratch-ocr-fixture.*   # fixture text OCR mẫu (không cần tesseract để test)
tasks/plan.md                    # thêm "Đợt 6"
```

## 5. Code Style (bám mẫu `pdf_to_text` — subprocess, degrade rỗng)

```python
def pdf_to_ocr_text(pdf_path, lang: str = "vie") -> str:
    """OCR một PDF ảnh scan (pdftoppm 300dpi -> tesseract). '' nếu thiếu binary/lỗi.

    Chỉ gọi khi pdf_to_text trả text quá ngắn (PDF không có lớp text).
    """
    try:
        ppm = subprocess.run(["pdftoppm", "-r", "300", "-png", str(pdf_path), "-"],
                             capture_output=True, timeout=120)
        if ppm.returncode != 0 or not ppm.stdout:
            return ""
        ocr = subprocess.run(["tesseract", "stdin", "stdout", "-l", lang],
                            input=ppm.stdout, capture_output=True, timeout=120)
        return ocr.stdout.decode("utf-8", "replace")
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
```

- OCR chỉ chạy khi `len(pdf_to_text(...).strip()) < NGƯỠNG` (ví dụ 50) → không
  tốn CPU cho PDF đã có lớp text.
- HĐ bóc từ OCR gắn `nguon="PDF-OCR"` (phân biệt với `"PDF"` bóc lớp text) để
  cột Nguồn báo cho kế toán biết **cần đối soát kỹ hơn** (OCR có thể sai số).
- Adapter mới theo đúng contract `PortalAdapter` (`can_handle`/`fetch`), trả `[]`
  khi lỗi/timeout → HĐ về "cần tải tay", **không làm sập batch**.

## 6. Testing Strategy (TDD bắt buộc — RED→GREEN→refactor)

- **Không phụ thuộc mạng / không phụ thuộc tesseract khi test**:
  - Nhánh A: monkeypatch `pdf_to_ocr_text` trả một chuỗi OCR mẫu (đã lưu fixture)
    → assert `parse_pdf_text` ra `Invoice` đúng + `nguon="PDF-OCR"`. Test thứ 2:
    cả `pdf_to_text` lẫn `pdf_to_ocr_text` rỗng → `extract_pdf_invoice` trả `None`
    (→ vẫn "cần nhập tay", không crash khi thiếu binary).
  - Nhánh B: mock HTTP (như `test` adapter einvoice/vnpt sẵn có) — GET token →
    file giả → assert `fetch` trả `Attachment` xml/pdf; `can_handle` khớp domain.
- Fixtures XML/text trong `tests/fixtures/` là cách kiểm chứng chính.

## 7. Boundaries

- **Always:** IMAP readonly + BODY.PEEK; số liệu chỉ từ XML (OCR/PDF luôn gắn cờ
  Nguồn, không coi ngang XML); `make test` xanh trước khi commit; không commit `.env`.
- **Ask first:** ⚠️ **Cài `tesseract-ocr`/`tesseract-ocr-vie`** (system pkg, cần
  sudo) — sẽ hỏi bạn trước khi cài. Test dùng mock nên GREEN được **không cần**
  cài; nhưng chạy OCR thật thì cần. Mọi adapter gọi HTTP ra ngoài (nhánh B).
- **Never:** dựng adapter giả cho cổng chưa xác minh; suy diễn số từ PDF/OCR khi
  parser không chắc (thà để "cần nhập tay" còn hơn bịa số).

## 8. Success Criteria (kiểm chứng được)

**Nhánh A (OCR):**
- [ ] `pdf_to_ocr_text` tồn tại, degrade `''` khi thiếu tesseract (không throw).
- [ ] Một PDF ảnh-scan (không lớp text) → OCR → `parse_pdf_text` ra Invoice
      `nguon="PDF-OCR"` nếu đọc được; nếu không → vào "cần nhập tay" (không mất, không crash).
- [ ] Cột **Nguồn** trong Excel/CSV hiển thị `PDF-OCR`.
- [ ] `make test` xanh (test mock, không cần tesseract).

**Nhánh B (adapter HTTP):**
- [ ] Spike Fast e-Invoice + Vietcombank: **ghi lại** GET token trả gì (file? JS? captcha?).
- [ ] Nếu khả thi HTTP → adapter mới + đăng ký + test mock HTTP; 1 HĐ mẫu chuyển
      từ `can-tai-tay` vào `data/`. Nếu không → README ghi "cần trình duyệt", KHÔNG adapter.
- [ ] `can-tai-tay-*.csv` tách rõ "chưa có adapter (tải tay)" vs đã tải được.

## 9. Open Questions

1. **Vietcombank 72 dòng** là HĐ GTGT thật hay thông báo sao kê/marketing? Spike
   B1 phân loại trước — nếu đa số không phải HĐ mua-vào thì hạ ưu tiên.
2. OCR: chấp nhận `nguon="PDF-OCR"` là tên cột, hay bạn muốn nhãn khác
   (vd "PDF (OCR – cần đối soát)")? Mặc định dùng `PDF-OCR`, đổi được ở 1 chỗ.

## 10. Task breakdown (đưa vào `tasks/plan.md` — Đợt 6)

Nhánh A và B **độc lập**, làm song song được.

- [ ] **T31 — OCR fallback (nhánh A).** RED: test parse text OCR mẫu → `nguon="PDF-OCR"`;
      test thiếu binary → `None`. GREEN: `pdf_to_ocr_text` + nhánh fallback trong
      `extract_pdf_invoice`. Files: `pdf_extract.py`, `tests/test_pdf_extract.py`.
- [ ] **T32 — Cột Nguồn nhận `PDF-OCR`.** Kiểm Excel/CSV hiển thị đúng nhãn mới
      (đa phần chạy sẵn vì đọc `inv.nguon`). Files: `excel.py`/`csv_report.py` (nếu cần), test.
- [ ] **T33 — Spike Fast e-Invoice + Vietcombank (nhánh B).** GET token bằng
      `requests`, ghi lại phản hồi. Quyết định khả thi/không. **Không code adapter ở bước này.**
- [ ] **T34 — Adapter HTTP (nếu T33 khả thi).** `fast_einvoice.py`/`vietcombank.py`
      + đăng ký + test mock HTTP + chạy thật 1 HĐ. Files: `adapters/*`, `tests/test_adapters.py`.
- [ ] **T35 — Tài liệu + chạy thật.** Cập nhật `README.md` adapter, `CLAUDE.md`,
      `plan.md`; chạy lại `collect` + `report`, đối chiếu số HĐ "cần tải tay" giảm.
```
Thứ tự trong nhánh: A = T31→T32; B = T33→(T34)→T35. T35 chốt cả hai.
```
