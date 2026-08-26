# Spec: Gỡ vướng mắc tải hóa đơn + giới hạn phạm vi hộp thư

Ngày: 2026-08-26. Nguồn: người dùng chạy thật Đợt 7 rồi phản hồi.
Nối tiếp: `2026-08-25-tu-dong-tra-cuu-tai-hoa-don.md` và khảo sát
`2026-08-25-khao-sat-cong-tra-cuu.md`.
Trạng thái: **CHỜ DUYỆT — chưa viết dòng code nào.**

## 1. Objective (làm gì & vì sao)

Sau Đợt 7, sổ `data/so-hoa-don-cho-tai.csv` còn **67 dòng chưa tải được**. Soi
từng dòng cho thấy chúng **không đồng nhất** — gộp chung dưới nhãn "chưa tải
được" làm vấn đề trông vừa lớn hơn vừa khó hơn thực tế:

| Nhóm | Dòng | Vướng gì | Hướng giải |
|------|-----:|----------|------------|
| **A** meinvoice (36) · ehoadon (9) · easyinvoice (6) | **51** | captcha / SPA | trình duyệt (Playwright) |
| **B** SMBC eInvoice | 5 | zip **mã hóa**, mật khẩu nằm ở **email khác** | ghép cặp + giải nén (thư viện chuẩn) |
| **C** GSM/hilo | 2 | bản `Re:` không đính kèm | hóa đơn gốc đã có — nhận là bản sao |
| **D** ViettelPost · Google · VNPT · Cục Thuế | 9 | **không phải hóa đơn** | lọc khỏi ứng viên |

Kèm một yêu cầu vận hành: **chạy cho công ty nào thì chỉ quét hộp thư của công
ty đó**. Hiện `collect` quét cả 3 hộp thư nên chọn miyano vẫn thấy medcons chạy qua.

**Thành công =** sổ chỉ còn những dòng thực sự là hóa đơn chưa lấy được, và
nhóm A lấy được qua trình duyệt với số lần gõ captcha ít nhất có thể.

### Quyết định đã chốt với người dùng (2026-08-26)

1. **Một spec gộp** cả bốn nhóm + phạm vi hộp thư.
2. **Dùng Playwright** cho nhánh trình duyệt, không spike thăm dò trước.
3. **Hộp thư khai thuộc công ty nào**; chọn công ty thì chỉ quét hộp thư đó.
   **Thư mục và bảng kê VẪN chia theo MST bên mua** (đúng luật), kèm cảnh báo
   khi hóa đơn lạc công ty.

## 2. Tech Stack

**Thêm một phụ thuộc — có chủ ý, phá lệ "không thêm thư viện" của repo:**

- **`playwright`** (+ `playwright install chromium`, ~150MB). Đây là ngoại lệ
  người dùng đã duyệt. Lý do: captcha bắt buộc có người thật, mà Playwright giữ
  được **phiên đăng nhập giữa các hóa đơn** (persistent context) — nếu cổng giữ
  phiên thì 22 hóa đơn meinvoice chỉ tốn **một** lần gõ captcha thay vì 22.
  Máy đã có `/usr/bin/google-chrome`; vẫn dùng chromium của Playwright để bản
  build ổn định.
- Nhóm B **không cần thư viện mới**: đã kiểm chứng `zipfile` của thư viện chuẩn
  giải được (`compress_type=8`, ZipCrypto cũ, không phải AES).
- Phần còn lại dùng nguyên `requests` / `PyYAML` đã có.

Playwright **chỉ được import bên trong hàm** của `browser.py`, để thiếu nó thì
mọi lệnh khác vẫn chạy (degrade an toàn, giống cách `pdf_extract` xử lý tesseract).

## 3. Commands

```bash
make test
./.venv/bin/pip install playwright && ./.venv/bin/playwright install chromium   # HỎI TRƯỚC
./.venv/bin/hdtool collect --from 2026-06-01 --to 2026-06-30 --company miyano
./.venv/bin/hdtool ncc                    # xem sổ
./.venv/bin/hdtool ncc --trinh-duyet      # (mới) mở Chrome, đi hết dòng nhóm A
```

## 4. Project Structure (file đụng tới)

```
src/hdtool/zipmail.py        # (MỚI) ghép cặp email zip+mật khẩu, giải nén có mật khẩu
src/hdtool/browser.py        # (MỚI) phiên Playwright + tải 1 hóa đơn qua trình duyệt
src/hdtool/config.py         # + mailboxes (hộp thư -> công ty); accounts_for(company)
src/hdtool/classify.py       # + exclude_subjects
src/hdtool/collect.py        # giữ lại zip mã hóa để ghép cặp thay vì bỏ
src/hdtool/cli.py            # --company cho collect/run; cờ --trinh-duyet cho ncc
src/hdtool/interactive.py    # truyền công ty đã chọn xuống collect
src/hdtool/worklist.py       # + trạng thái "trùng bản gốc", "thiếu mật khẩu zip"
config/settings.yaml         # + mailboxes, + exclude_subjects, + exclude_senders
tests/test_zipmail.py        # (MỚI)
tests/test_browser.py        # (MỚI) test phần thuần; phần Playwright đánh dấu skip
tests/test_config.py         # + mailboxes/accounts_for
tests/test_classify.py       # + exclude_subjects
```

## 5. Thiết kế theo từng nhóm

### E. Phạm vi hộp thư (làm trước — bạn đang vướng hằng ngày)

`config/settings.yaml` thêm mục `mailboxes`:

```yaml
mailboxes:
  info@miyano.com.vn:         miyano
  mvl.invoices2024@gmail.com: miyano
  anh.doan@medcons.vn:        medcons
```

```python
def accounts_for(settings, company: Optional[str]) -> list[Account]:
    """Hộp thư cần quét cho một công ty. Không khai -> quét (an toàn, không mất HĐ)."""
```

- `company=None` (không chọn công ty) → quét tất cả, y như hiện nay.
- Hộp thư **không khai** trong `mailboxes` → **vẫn quét cho mọi công ty**. Mặc
  định an toàn: thà quét thừa còn hơn mất hóa đơn.
- `collect` và `run` nhận thêm `--company`; menu truyền công ty đã chọn xuống.
- **Thư mục và bảng kê không đổi**: vẫn theo MST bên mua đọc từ XML. Khi hóa đơn
  tải từ hộp thư của công ty X nhưng bên mua là công ty Y, in cảnh báo:
  `⚠ HĐ 00012 từ hộp miyano nhưng bên mua là MEDCONS -> data/medcons/`.

Rủi ro đã biết và chấp nhận: hóa đơn miyano còn sót trong hộp `anh.doan@medcons.vn`
sẽ không được quét khi chạy cho miyano. Cảnh báo ở trên là cách phát hiện.

### D. Lọc nhiễu (rẻ nhất, làm ngay sau E)

9 dòng trong sổ không phải hóa đơn: cảnh báo đăng nhập Google/ViettelPost, "Xác
thực thông tin", thông báo tài khoản trả trước của VNPT, xác thực tờ khai của
Cục Thuế.

Thêm `exclude_subjects` bên cạnh `exclude_senders` đã có:

```yaml
exclude_senders:
  - vcbdigibank
  - viettelpost.com.vn
  - accounts.google.com
  - dichvucongcucthue@gdt.gov.vn

exclude_subjects:            # khớp chuỗi con, không phân biệt hoa thường
  - "cảnh báo đăng nhập"
  - "xác thực thông tin"
  - "thông báo tài khoản trả trước"
  - "security alert"
  - "xác thực tờ khai"
```

**Vì sao VNPT phải lọc theo TIÊU ĐỀ chứ không theo người gửi:**
`hoadondientu@vnpt-invoice.vn` là nhà phát hành thật — chặn cả người gửi sẽ đánh
rơi hóa đơn VNPT chỉ-link. Giữ nguyên luật an toàn sẵn có: **email có XML thì
luôn giữ**, dù khớp bộ lọc nào.

### C. Bản `Re:`/`Fwd:` không đính kèm

Email không có đính kèm, không có link dùng được, nhưng **tiêu đề chuẩn hóa**
(bỏ tiền tố `Re:`/`Fwd:`/`Fw:`) trùng với một hóa đơn đã tải → ghi sổ trạng thái
**"trùng bản gốc"** kèm đường dẫn file gốc, thay vì "không có link".

Đây không phải tính năng tải thêm — nó làm sổ nói đúng sự thật: hóa đơn đó
**không thiếu**, chỉ là bản sao trong hộp thư.

### B. SMBC — zip mã hóa + mật khẩu ở email khác

Mẫu đã kiểm chứng thật (4/4 hóa đơn, 2026-02 → 2026-07, mỗi tháng một tờ
115.500đ phí dịch vụ ngân hàng):

```
Email 1: tiêu đề "[ SMBC HN - eInvoice] [8754440] [0005301][30062026] …"
         đính kèm invoice.zip (mã hóa)  ->  01GTKT.xml + invoice.pdf
Email 2: tiêu đề Y HỆT, không đính kèm
         body: "Password unzip file: ya0N1ZzrPPxp"
```

`src/hdtool/zipmail.py` — ba hàm thuần, test không cần mạng:

```python
def chuan_hoa_tieu_de(s: str) -> str:
    """Bỏ mọi tiền tố Fwd:/Fw:/Re: và chuẩn hóa khoảng trắng, để ghép cặp."""

def tim_mat_khau(body: str) -> Optional[str]:
    """'Password unzip file: ABC123' -> 'ABC123'. Không thấy -> None."""

def giai_nen_co_mat_khau(zip_bytes: bytes, mat_khau: str) -> list[Attachment]:
    """zipfile + pwd=. Sai mật khẩu / AES / hỏng -> [] (không làm sập batch)."""
```

Luồng trong `collect`: **hai lượt trong cùng một lần chạy**. Lượt 1 duyệt hết
email ứng viên, gom `{tiêu đề chuẩn hóa: zip_bytes}` và `{tiêu đề chuẩn hóa:
mật khẩu}`. Lượt 2 ghép, giải nén, đưa vào đúng luồng lưu file như đính kèm
thường. Hai email có thể đến theo thứ tự bất kỳ nên **không** giải nén ngay khi
gặp zip.

Ghép không ra mật khẩu → sổ ghi **"thiếu mật khẩu zip"**. Người dùng dán mật
khẩu vào **cột `Mã tra cứu`** (dùng lại đúng cột đã có, đã nằm trong
`USER_FIELDS` nên không bị tool ghi đè) — không đẻ thêm cột mới.

**Không lưu mật khẩu xuống đĩa.** Giải nén trong bộ nhớ, chỉ ghi ra XML/PDF.

### A. Nhánh trình duyệt (Playwright) — 51 dòng

`src/hdtool/browser.py`:

```python
def mo_phien(user_data_dir, headless: bool = False):
    """Persistent context -> cookie/phiên sống qua nhiều hóa đơn trong một lần chạy."""

def tai_qua_trinh_duyet(page, url: str, ma: Optional[str],
                        cho_nguoi_dung_giay: int = 180) -> list[Attachment]:
    """Mở trang, điền mã nếu có ô, CHỜ NGƯỜI DÙNG giải captcha, bắt sự kiện tải."""
```

Nguyên tắc giữ nguyên: **tool không bao giờ tự giải captcha.** Nó mở trang, điền
sẵn mã tra cứu, rồi in ra terminal:

```
[3/22] CG GLOBAL — mã A9FESJZXNP0E
   → Cửa sổ Chrome đã mở. Giải captcha rồi bấm Tra cứu / Tải XML.
   → Đang chờ (tối đa 180 giây)…  Ctrl-C để bỏ qua hóa đơn này.
```

File lấy qua **sự kiện download của Playwright** (`expect_download`), không đụng
tới thư mục Downloads của máy — tránh nhặt nhầm file khác.

Sau khi có bytes, đi qua **đúng chốt chặn cũ** `accept_files`: không parse ra
`Invoice` thì không ghi gì.

**Điểm cộng đáng giá:** URL tải mà Playwright bắt được đưa thẳng vào
`ncc.learn()`. Nếu URL đó chứa mã tra cứu và tải lại được bằng HTTP thuần, những
hóa đơn sau của cổng đó **không cần trình duyệt nữa**. Nhánh trình duyệt vì thế
tự thu hẹp phạm vi của chính nó.

Hồ sơ Chrome đặt ở `data/.chrome-profile/` (nằm trong `data/` nên đã gitignore).

`hdtool ncc --trinh-duyet`: lọc các dòng sổ có chẩn đoán captcha/SPA, mở **một**
phiên, đi lần lượt, cập nhật sổ sau mỗi hóa đơn (Ctrl-C giữa chừng không mất
tiến độ đã làm).

## 6. Testing Strategy (TDD bắt buộc)

- `zipmail.py` test **hoàn toàn offline**: tự tạo zip mã hóa bằng `zipfile` trong
  fixture, kiểm tra ghép cặp theo tiêu đề (kể cả `Fwd: Fwd:` lồng nhau), bóc mật
  khẩu, giải nén, và sai mật khẩu → `[]`.
- `accounts_for` và `exclude_subjects` là hàm thuần → test bằng bảng dữ liệu.
- Nhận diện bản `Re:` trùng: test bằng hai `EmailCandidate` giả.
- `browser.py`: tách phần thuần (chọn selector, dựng URL, quyết định điền ô nào)
  ra test được; phần chạy Playwright đánh dấu
  `@pytest.mark.skipif(playwright chưa cài)` — cùng lối `test_pdf_ocr_integration`.
- **Không test mạng thật trong CI.**

Ca bắt buộc: email zip đến **trước** email mật khẩu và ngược lại đều phải ghép
được; hộp thư không khai trong `mailboxes` vẫn được quét; email khớp
`exclude_subjects` **nhưng có XML** thì vẫn giữ.

## 7. Boundaries (ngoài phạm vi)

- **Không tự giải captcha** trong mọi trường hợp — người dùng gõ, tool chỉ dựng sẵn.
- Không đổi cấu trúc `data/`, không migrate.
- Không đổi quy tắc bảng kê: bên mua vẫn xác định bằng MST trong XML.
- Không đụng nhập tay hóa đơn không có trong mail (Grab, ĐÔI CÁNH, MEGA) — spec khác.
- Không chạy trình duyệt trong `collect` tự động; chỉ chạy khi gọi
  `ncc --trinh-duyet` (có người ngồi trước máy).

## 8. Success Criteria (kiểm chứng được)

1. Chạy `collect --company miyano`: log **không xuất hiện** hộp thư của medcons.
2. Sổ **không còn dòng nào thuộc nhóm D** (9 dòng nhiễu biến mất khỏi danh sách chờ).
3. **4 hóa đơn SMBC** parse được từ zip mã hóa và vào bảng kê của ĐÚNG kỳ mỗi
   tờ (02, 05, 06, 07/2026 — mỗi kỳ một tờ 115.500đ), `Nguồn = XML`.
4. 2 dòng GSM/hilo mang trạng thái "trùng bản gốc" kèm đường dẫn file gốc.
5. `ncc --trinh-duyet` tải được **ít nhất 1 hóa đơn meinvoice** thật, và nếu cổng
   giữ phiên thì hóa đơn thứ hai **không** hỏi captcha lại (ghi lại số liệu thật).
6. Mọi file tải qua trình duyệt đều parse ra `Invoice` hợp lệ.
7. `make test` xanh, không cần mạng, không cần Playwright để chạy bộ test.

## 9. Open Questions

1. ~~Bảng `mailboxes` cần xác nhận~~ — **ĐÃ CHỐT 2026-08-26**:
   `mvl.invoices2024@gmail.com` **chỉ thuộc miyano**. Hệ quả đã chấp nhận: chạy
   medcons sẽ không quét hộp này, nên các bản forward hóa đơn medcons nằm trong
   đó bị bỏ qua — chấp nhận được vì bản gốc vẫn ở `anh.doan@medcons.vn`. Cảnh báo
   "lạc công ty" ở §5.E là cách phát hiện nếu giả định này sai.
2. meinvoice có giữ phiên sau khi giải captcha lần đầu không? Quyết định 22 lần
   gõ captcha hay 1. Chỉ trả lời được khi chạy thật ở T51.
3. ViettelPost có bao giờ gửi hóa đơn GTGT thật không? Nếu có thì phải chuyển từ
   `exclude_senders` sang `exclude_subjects` như đã làm với VNPT.

## 10. Task breakdown (Đợt 8)

| Task | Nội dung | Phụ thuộc | Cần mạng |
|------|----------|-----------|----------|
| **T47** | `mailboxes` trong settings + `accounts_for` + `--company` cho collect/run + menu truyền xuống + cảnh báo lạc công ty | — | không |
| **T48** | `exclude_subjects` + bổ sung `exclude_senders`; giữ luật "có XML thì luôn giữ" | — | không |
| **T49** | Nhận diện bản `Re:`/`Fwd:` trùng → trạng thái "trùng bản gốc" | T48 | không |
| **T50** | `zipmail.py` + luồng hai lượt trong `collect` (SMBC) | — | mock |
| **T51** | `browser.py`: phiên Playwright + tải 1 hóa đơn có người giải captcha | T47 | có |
| **T52** | `ncc --trinh-duyet`: đi hàng loạt, cập nhật sổ sau mỗi hóa đơn | T51 | có |
| **T53** | Học công thức từ URL trình duyệt bắt được → hóa đơn sau bỏ qua trình duyệt | T52 | có |
| **T54** | Chạy thật, đo theo §8, cập nhật README/CLAUDE/plan/tổng quan | tất cả | có |

Thứ tự: **T47 → T48 → T49 → T50 → T51 → T52 → T53 → T54**.
T47–T50 không cần Playwright, làm xong đã gỡ 16/67 dòng và làm sổ nói đúng sự thật.
