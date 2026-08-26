# hdtool — Tổng quan & lộ trình hoàn thiện

> Cập nhật: **2026-08-25**. Tài liệu "một cửa": đọc file này là nắm được tool
> làm gì, đã xong tới đâu, số liệu thực tế hiện tại, còn thiếu gì và nên làm
> tiếp theo thứ tự nào. Chi tiết từng đợt xem `tasks/plan.md`; thiết kế gốc xem
> `docs/superpowers/specs/`.

---

## 1. Tool giải quyết việc gì

Mỗi kỳ kê khai GTGT, hóa đơn điện tử đầu vào của **Miyano** và **MEDCONS** nằm
rải rác trong hộp thư dưới 3 dạng: (a) đính kèm XML+PDF, (b) chỉ có PDF, (c) chỉ
có **link tra cứu** trên cổng nhà phát hành. Trước đây phải mở từng mail, tải
từng file, gõ tay vào bảng kê.

`hdtool` tự động hóa việc đó theo 3 bước:

```
  IMAP (chỉ đọc)          nhận diện + tải             parse + tổng hợp
┌──────────────┐      ┌────────────────────┐      ┌──────────────────────┐
│  scan        │ ───▶ │  collect           │ ───▶ │  report              │
│ chấm điểm    │      │ đính kèm / giải nén│      │ XML → Invoice        │
│ email → rổ   │      │ zip / adapter cổng │      │ khử trùng, lọc kỳ    │
│ chắc/nghi/bỏ │      │ → cây data/        │      │ → Excel 4 sheet / CSV│
└──────────────┘      └────────────────────┘      └──────────────────────┘
```

Đầu ra là file bảng kê đúng cấu trúc mẫu kế toán đang dùng
(`docs/MVL 6.26_tai-hoa-don_muaVao_01-06-2026_30-06-2026.xlsx`).

---

## 2. Bốn nguyên tắc không được phá

| # | Nguyên tắc | Vì sao |
|---|-----------|--------|
| 1 | **IMAP chỉ đọc** — `readonly=True` + `BODY.PEEK`, không đánh dấu đã đọc / xóa / di chuyển | Hộp thư là hộp thư làm việc thật, tool không được để lại dấu vết |
| 2 | **Số liệu chỉ lấy từ XML** (chuẩn TCT). PDF là bản thể hiện | Sai số tiền = sai tờ khai. Chỉ có PDF ⇒ gắn cờ "cần nhập tay/OCR", **không suy diễn** |
| 3 | **Không commit bí mật** — `.env` nằm trong `.gitignore` | App password Gmail không hết hạn |
| 4 | **Cấu hình, không hardcode** — nhà phát hành, từ khóa, whitelist, độ nới ngày ở `config/settings.yaml` | Mở rộng không cần sửa code |

---

## 3. Kiến trúc — file nào làm gì

| Module | Trách nhiệm |
|--------|-------------|
| `config.py` | Nạp `.env` + `settings.yaml` → `Settings`; hỗ trợ **nhiều hộp thư** (`IMAP_USER`, `_2`, `_3`, …) |
| `models.py` | `Invoice`, `TaxLine`, `ProductLine`, `EmailCandidate` |
| `xmlutil.py` | Tìm phần tử theo **local-name** → miễn nhiễm khác biệt namespace giữa nhà phát hành |
| `parse_xml.py` | XML chuẩn TCT → `Invoice` (kể cả dòng sản phẩm, CKTM, tỷ giá, ngày ký) |
| `pdf_extract.py` | HĐ chỉ-PDF: `pdftotext` → `nguon="PDF"`; PDF ảnh scan → OCR tesseract-vie → `nguon="PDF-OCR"` |
| `mailscan.py` | IMAP readonly: chọn thư mục `\All`, `UID SEARCH` theo cửa sổ ngày, fetch (helper thuần để test) |
| `classify.py` | Chấm điểm email → `certain` / `suspect` / `ignore`; whitelist + **exclude_senders** |
| `collect.py` | Trích attachment, giải nén zip (chịu được zip hỏng/khóa), dò link, lưu cây thư mục |
| `adapters/` | Adapter tải HĐ **chỉ-link** từ cổng — xem §7 |
| `manifest.py` | `data/.collected.json` — message-id đã tải ⇒ collect **idempotent** |
| `aggregate.py` | Khử trùng (`MST bán + ký hiệu + số HĐ`), xử lý thay thế→nghi hủy, lọc mua-vào, gom thuế suất, `only_company` |
| `pipeline.py` | `build_report` (không ghi file) + `write_report` (xlsx/csv) |
| `excel.py` | Xuất `.xlsx` 4 sheet giống mẫu + sheet Bỏ qua / Cần nhập tay |
| `csv_report.py` | Xuất CSV theo cột BK TT80 + `-tong-hop.csv` + `-bo-qua.csv` (UTF-8 BOM) |
| `reports.py` | CSV danh sách ứng viên/nghi ngờ; CSV "cần tải tay" |
| `interactive.py` | Menu: hỏi ngày → chọn công ty → chọn Excel/CSV |
| `cli.py` | `scan` / `collect` / `report` / `run` / `reorganize`; không kèm lệnh → mở menu |

---

## 4. Luồng dữ liệu thật — cái gì rơi xuống đĩa

```
data/
├── .collected.json                       # manifest message-id đã tải (idempotent)
├── ung-vien-<from>_<to>.csv              # scan: rổ chắc chắn + nghi ngờ để rà tay
├── can-tai-tay-<from>_<to>.csv           # collect: HĐ chỉ-link chưa có adapter
├── bang-ke-<công ty>-<from>_<to>.xlsx    # report
├── miyano/    <YYYY-MM>/ <email người gửi>/  invoice.xml + invoice.pdf
├── medcons/   <YYYY-MM>/ <email người gửi>/
└── _chua-ro-cong-ty/    # XML hỏng / PDF-only → chưa đọc được bên mua
    (và `_khac/` khi bên mua đọc được nhưng không phải 2 công ty của mình)
```

Vài điểm cần nhớ khi vận hành:

- `--from/--to` là **ngày lập hóa đơn (NLap)**, không phải ngày email đến. Tool
  quét email rộng ra `[from-15, to+45]` rồi mới lọc theo NLap.
- `scan` và `collect` **tự chạy qua tất cả hộp thư** khai trong `.env`.
- Manifest khóa theo `Message-ID` ⇒ chạy lại `collect` không tải trùng; email
  giống nhau ở 2 hộp thư khác Message-ID nên vẫn tải 2 lần (khử trùng ở tầng
  `aggregate` bằng `MST bán + ký hiệu + số HĐ`).
- `reorganize` = tải lại vào cấu trúc thư mục mới, **an toàn**: backup manifest,
  chỉ xóa cây cũ khi mọi hóa đơn đã có bản mới.

---

## 5. Đã làm được gì — 6 đợt

| Đợt | Nội dung | Kết quả then chốt |
|-----|----------|-------------------|
| **1** (T1–T13) | Bộ khung: parse XML, aggregate, classify, Excel, config, collect, mailscan, CLI, manifest idempotent, khung adapter, cờ "cần nhập tay" | Pipeline chạy end-to-end trên fixtures; đa hộp thư; fix dùng **UID** thay số thứ tự |
| **2** (T14–T19) | Chọn **1 công ty** để xuất bảng kê, xuất **CSV**, **menu tương tác** | `aggregate(only_company=)`, tách `build_report`/`write_report`, `run.py` thành launcher |
| **3** (T20–T22) | Tinh chỉnh sau lần chạy thật đầu tiên (263 file, 109 HĐ miyano) | "Cần nhập tay" chỉ tính trong thư mục công ty đang chọn; xuất CSV "cần tải tay" |
| **4** (T23–T26) | Xuất **Excel 4 sheet giống mẫu** (Chi tiết SP / BK TT80 / DS hóa đơn / DS sản phẩm) | Parse dòng sản phẩm + CKTM/tỷ giá/ngày ký; CSV đổi sang cột TT80 |
| **5** (T27–T30) | Cột **Nguồn** (XML/PDF/Cổng), bóc **PDF-only** bằng `pdftotext`, **adapter HTTP** đầu tiên | `einvoice.com.vn` (saigoncoop) và `vnpt-invoice` tự tải được — automation chạy thật |
| **6** (T31–T36) | **OCR** PDF ảnh scan, adapter **Fast e-Invoice**, lọc **biên lai Vietcombank** | Danh sách "cần tải tay" **113 → 40**; ứng viên medcons 389 → 316 (bỏ 72 mail VCB) |

**Phát hiện có giá trị nhất (đợt 5–6):** trang tra cứu của VNPT/Fast có captcha,
**nhưng email thông báo phát hành kèm link tải-thẳng đã ký** (`token=` / `hash=`)
trả XML trực tiếp, bỏ qua captcha. ⇒ Khi thêm nhà phát hành mới, **luôn tìm link
tải-thẳng trong body email trước** khi kết luận "phải dùng trình duyệt".

---

## 6. Trạng thái đo được hôm nay (2026-08-25)

**Test:** `164 passed, 1 skipped` (~0.6s). Test duy nhất bị skip là OCR
end-to-end — thiếu binary `tesseract` trên máy này.

**Dữ liệu đã tải về `data/`:**

| Thư mục | File | XML | PDF |
|---------|-----:|----:|----:|
| `miyano/` | 275 | 145 | 130 |
| `medcons/` | 39 | 21 | 18 |
| `_chua-ro-cong-ty/` | 197 | 92 | 95 |
| **Tổng** | **511** | **258** | **243** |

Manifest: **279** message-id đã tải.

**Bảng kê kỳ 06/2026 (chạy lại hôm nay):**

| Công ty | HĐ trong kỳ | Chưa thuế | Thuế | Tổng thanh toán | Bỏ qua |
|---------|------------:|----------:|-----:|----------------:|-------:|
| miyano | 27 | 8.865.782 | 791.598 | **10.019.380** | 218 |
| medcons | 1 | 15.740.743 | 1.259.257 | **17.000.000** | 244 (+1 PDF cần nhập tay) |

**Đối chiếu file mẫu MVL 6.26 (miyano 06/2026):** cấu trúc + **27 hóa đơn chung
khớp 100% tiền**. Mẫu có 40 HĐ / 37.981.600 → tool còn **thiếu 13 HĐ ≈ 74% giá
trị kỳ**, tất cả vì **chưa có XML trong `data/`** (không phải lỗi tính toán).
Tool giữ số 0 đầu của `SHDon` đúng theo XML (file mẫu bị Excel cắt mất).

**Hộp thư đang cấu hình (`.env`):**

| # | Hộp thư | Tình trạng |
|---|---------|-----------|
| 1 | `info@miyano.com.vn` | đã quét — gần như không có HĐ XML |
| 2 | `anh.doan@medcons.vn` | đã quét — hộp thư hóa đơn thật của **cả hai** công ty |
| 3 | `mvl.invoices2024@gmail.com` | **vừa thêm 2026-08-25, đã test login OK — CHƯA quét lần nào** |

**Binary phụ trợ trên máy:** `pdftotext` ✅, `pdftoppm` ✅, `ghostscript` ✅,
**`tesseract` ❌ (chưa cài)**.

**Chưa commit:** `src/hdtool/interactive.py` (bỏ 1 dòng trống) và
`src/hdtool/mailscan.py` (bỏ tham số charset `None` trong `uid("SEARCH", …)`) —
thay đổi nhỏ, test vẫn xanh, nhưng đang lơ lửng ngoài git.

---

## 7. Bao phủ cổng hóa đơn (HĐ chỉ-link)

| Cổng | Cơ chế | Tự động? |
|------|--------|----------|
| `*.einvoice.com.vn` (saigoncoop…) | GET trang → CSRF + `idHoaDon` → POST `/tai-ve-hoa-don` → ZIP | ✅ `einvoice_com_vn.py` |
| `*-tt78.vnpt-invoice.com.vn` | Link email `getinvoice?token=` trả XML thẳng | ✅ `vnpt_invoice.py` |
| `einvoice.fast.com.vn` | Link email `index.aspx?type=2&c=&hash=` trả XML thẳng | ✅ `fast_einvoice.py` |
| meinvoice.vn (MISA) | SPA, endpoint dựng bằng JS mã hóa | ⏳ cần bắt XHR bằng trình duyệt |
| easyinvoice.com.vn (Thái Sơn) | SPA, `/Invoice/ConvertInv` dựng bằng JS | ⏳ cần bắt XHR bằng trình duyệt |
| ehoadon.vn | **ReCaptcha** ở trang tra cứu | ❌ cần trình duyệt + nhập tay |
| `info.vietcombank.com.vn` | Biên lai ngân hàng, **không phải HĐ GTGT** | — đã lọc khỏi ứng viên (T36) |

File tải từ cổng là **XML thật** ⇒ chạy pipeline như HĐ có đính kèm. Cổng lỗi /
token hết hạn ⇒ adapter trả `[]`, hóa đơn rơi vào "cần tải tay", **không làm sập
batch**.

---

## 8. Còn thiếu gì — phân tích khoảng trống

| ID | Khoảng trống | Ảnh hưởng | Bản chất |
|----|--------------|-----------|----------|
| **G1** | **13 HĐ kỳ 06/2026 chưa vào bảng kê** (74% giá trị) | Cao — bảng kê chưa dùng thay mẫu được | Chia 2 nhóm, xem dưới |
| **G2** | Hộp thư `mvl.invoices2024@gmail.com` **chưa quét lần nào** | Cao — có thể chính là nơi chứa nhóm B | Chỉ cần chạy, không cần code |
| **G3** | Chưa cài `tesseract` ⇒ nhánh **OCR không chạy được thật** | Trung bình — PDF scan vẫn phải nhập tay | Hạ tầng |
| **G4** | Chưa có **luồng nhập tay có dấu vết** cho HĐ không lấy được từ mail | Trung bình — phải sửa Excel bằng tay, mất vết, lần sau làm lại từ đầu | Thiếu tính năng |
| **G5** | Cổng chỉ-link chưa tự tải được (meinvoice / easyinvoice / ehoadon…) | Trung bình — nhóm A của G1 | Đợt 7 xử lý bằng **dò tự động**; riêng SPA/captcha mới cần Chrome (T46) |
| **G6** | `_chua-ro-cong-ty/` còn **197 file (92 XML)** chưa soát | Thấp–TB — đa số là bản forward XML hỏng 37 byte đã kiểm chứng không mất HĐ, nhưng chưa soát lại sau các đợt sau | Vệ sinh dữ liệu |
| **G7** | Không có lệnh **đối soát** bảng kê với danh sách kỳ vọng | Thấp — mỗi kỳ phải so tay | Thiếu tính năng |
| **G8** | Trạng thái **hủy** chỉ suy ra từ HĐ thay thế ("nghi hủy") | Thấp — đúng theo thiết kế | Cần tra cứu cổng TCT (T13, hoãn) |

**Chi tiết G1 — 13 hóa đơn thiếu:**

- **Nhóm A — chỉ-link, cổng SPA/captcha** (meinvoice: CG GLOBAL, CÂY SUNG, TUẤN
  KIỆT; GSM/Xanh SM qua hilo; Viettel K26DAB). Có email, có link, **chưa tải tự
  động được** → Đợt 7 thử **dò tự động** trước; trượt thì mới cần trình duyệt (G5).
- **Nhóm B — không lấy được từ email** (điều tra 2026-07-09): ĐÔI CÁNH & MEGA
  không có email; GRAB chỉ gửi "E-Receipt" (HĐ nằm trong app Grab); P.A và BẢO VỆ
  chỉ lẫn trong gói tài liệu/forward kế toán, không phải HĐĐT chuẩn. **Đã quyết
  định: chấp nhận nhập tay** — không nới lỏng classifier vì rủi ro false-positive
  cao. ⚠️ Nhưng kết luận này dựa trên **2 hộp thư cũ**; hộp thư thứ 3 vừa thêm
  (G2) có thể lật lại một phần nhóm này.

---

## 9. Lộ trình — Đợt 7: tự động tra cứu & tải hóa đơn chỉ-link

**Đã có spec chi tiết chờ duyệt:**
`docs/superpowers/specs/2026-08-25-tu-dong-tra-cuu-tai-hoa-don.md`

### Ý tưởng cốt lõi (khác hẳn cách cũ)

Cách cũ: mỗi cổng một adapter Python — khảo sát, viết code, viết test, commit.
Không mở rộng nổi khi mỗi nhà cung cấp lại một kiểu link.

Cách mới: **tool tự dò**. Từ link tra cứu có sẵn trong mail, tool lấy trang, phân
loại nó, điền form nếu cần, tìm link tải, **tải thử và xác minh bằng cách parse ra
`Invoice` hợp lệ**, rồi **nhớ công thức** để lần sau đi tắt.

Điểm quan trọng nhất: **registry công thức là bộ nhớ đệm, không phải điều kiện
tiên quyết.** Cổng chưa từng gặp vẫn tải được ngay lần đầu; có công thức chỉ để
đỡ request và đỡ phụ thuộc giao diện cổng. Cổng đổi URL → tool tự dò lại và cập
nhật công thức, không cần ai can thiệp.

Chốt chặn an toàn: **bằng chứng duy nhất được chấp nhận là bytes tải về parse ra
hóa đơn hợp lệ.** Nhờ vậy việc tool tự đoán "link nào là link tải" không bao giờ
ghi rác vào `data/`.

### Ba quyết định đã chốt

1. **Giữ nguyên cây thư mục** `data/<công ty>/<YYYY-MM>/<email người gửi>/` —
   không migrate 511 file đang có.
2. **Sổ tổng hợp là CSV tích lũy, sửa tay được** (`data/so-hoa-don-cho-tai.csv`),
   thay `can-tai-tay-*.csv` vốn bị ghi đè mỗi lần chạy nên mất dấu.
3. **Nhánh trình duyệt (SPA/captcha) ngoài phạm vi đợt này** — sẽ dừng ở bước
   phân loại trang với chẩn đoán cụ thể, thành mục riêng sau.

### Task (chi tiết trong spec)

| Task | Nội dung | Cần mạng |
|------|----------|----------|
| **T37** | Khảo sát: dựng lại danh sách chỉ-link, thống kê theo domain + loại trang. Không viết code. **Tự động bao luôn hộp thư thứ 3 (G2)** vì `collect` chạy qua cả 3 account. | có |
| **T38** | `worklist.py` + sổ CSV tích lũy, merge không đè ô sửa tay | không |
| **T39** | `lookup.py`: chấm điểm link tra cứu + bóc mã (cả text lẫn HTML) | không |
| **T40** | `portal_probe.py` phần thuần: phân loại trang, đọc form, liệt kê ứng viên, xác minh | không |
| **T41** | `probe()` + tích hợp vào `collect` | mock |
| **T42** | `ncc.py` registry + `learn()` + `RegistryAdapter` (nhánh đi tắt) | mock |
| **T43** | Lệnh `hdtool ncc` + mục trong menu | không |
| **T44** | Vá `save_invoice_files` ghi đè khi trùng tên (`collect.py:157`) — lỗi mất dữ liệu tiềm ẩn | không |
| **T45** | Chạy thật, đo kết quả, biến HTML thu được thành fixtures, cập nhật tài liệu | có |
| **T46** | *(sau, spec riêng)* Nhánh trình duyệt cho cổng SPA/captcha | có |

Thứ tự: **T37 → T44 → T38 → T39 → T40 → T41 → T42 → T43 → T45**.
T37 phải chạy trước vì kết quả của nó định hình cả đợt: nếu 40 dòng chỉ-link chủ
yếu là SPA thì quy trình dò ăn ít, còn nếu là HTML thuần thì ăn gần hết.

### Việc còn treo, chưa lên spec

- **Nhập tay có dấu vết** (đóng G4 và nhóm B của G1): Grab, ĐÔI CÁNH, MEGA sẽ
  không bao giờ lấy được từ mail. Cần chỗ khai hóa đơn gõ tay, gắn `nguon="Nhập
  tay"`, khử trùng chung khóa với XML. Đây là việc bắt buộc để bảng kê khớp mẫu.
- **Cài `tesseract`** (đóng G3): bật lại test OCR end-to-end đang bị skip.
- **Lệnh `reconcile`** (đóng G7): so bảng kê với danh sách kỳ vọng, hiện làm tay.
- **Dọn `_chua-ro-cong-ty/`** (đóng G6) và **tra trạng thái hủy trên cổng TCT**
  (G8) — giá trị thấp, để sau cùng.

**Định nghĩa "hoàn thiện"**: chạy `python run.py` cho một kỳ bất kỳ, chọn công
ty, và bảng kê xuất ra **khớp 100% với bảng kê kế toán làm tay** — mọi hóa đơn
hoặc đến từ XML/cổng tự động, hoặc nằm trong file nhập tay có dấu vết; không còn
bước sửa Excel thủ công nào.

## 10. Cheat sheet

```bash
make install                  # tạo venv + cài editable + dev deps
make test                     # 164 passed, 1 skipped

python run.py                 # MENU: hỏi ngày → chọn công ty → chọn xlsx/csv

./.venv/bin/hdtool scan      --from 2026-06-01 --to 2026-06-30
./.venv/bin/hdtool collect   --from 2026-06-01 --to 2026-06-30 --include-suspect
./.venv/bin/hdtool report    --from 2026-06-01 --to 2026-06-30 --company miyano --format csv
./.venv/bin/hdtool run       --from 2026-06-01 --to 2026-06-30
./.venv/bin/hdtool reorganize --from 2026-06-01 --to 2026-06-30
```

Thêm hộp thư: khai `IMAP_USER_<n>` / `IMAP_APP_PASSWORD_<n>` trong `.env` —
`config.py` tự dò `_2`, `_3`, `_4`… **không cần sửa code**; host/port kế thừa
`IMAP_HOST`/`IMAP_PORT` nếu không khai riêng.

---

## 11. Bẫy đã gặp — đừng vấp lại

- **UID vs sequence number**: phải dùng `imap.uid(...)`, số thứ tự thay đổi giữa
  các phiên → fetch nhầm mail (đã fix ở `07ab3d4`).
- **Bản forward của Anh Doan** thường kèm XML hỏng 37 byte → rơi vào
  `_chua-ro-cong-ty`, nhưng bản gốc vẫn parse được nên **không mất hóa đơn** (đã
  kiểm chứng 118 = 118 sau khi migrate). Đừng "sửa" bằng cách nới parser.
- **Đừng nới classifier để bắt thêm HĐ**: đợt 6 cho thấy nới ra chủ yếu kéo về
  biên lai ngân hàng / email marketing. Cách đúng là `exclude_senders` +
  adapter + nhập tay.
- **Trang tra cứu có captcha ≠ không tự động được**: tìm link tải-thẳng đã ký
  trong body email trước (bài học VNPT + Fast).
- **Excel cắt số 0 đầu của số hóa đơn** — file mẫu bị, tool thì không. Khi đối
  soát, so theo giá trị chứ đừng so chuỗi thô.
- **PDF không bao giờ được ghi đè XML**: `build_report` bỏ PDF nếu đã có XML cùng
  khóa. Giữ nguyên hành vi này.
