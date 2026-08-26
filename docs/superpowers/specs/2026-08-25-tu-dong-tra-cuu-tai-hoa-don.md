# Spec: Tự động tra cứu & tải hóa đơn chỉ-link (cổng tự học)

Ngày: 2026-08-25. Nguồn yêu cầu: brainstorming với người dùng (Miyano/MVL) 2026-08-25.
Nối tiếp: Đợt 6 (`2026-07-09-ocr-pdf-and-http-link-adapter.md`), `tasks/plan.md`.
Trạng thái: **CHỜ DUYỆT — chưa viết dòng code nào.**

## 1. Objective (làm gì & vì sao)

**Vấn đề.** 40 hóa đơn của kỳ gần nhất vẫn nằm trong danh sách "cần tải tay" vì
email chỉ có **link tra cứu + mã**, không đính kèm file. Cách giải hiện tại là
viết **một adapter Python cho mỗi cổng** (đã có 3: einvoice.com.vn, VNPT, Fast).
Cách đó không mở rộng nổi: mỗi nhà cung cấp mới lại tốn một vòng khảo sát → viết
code → viết test → commit, và mỗi cổng lại có kiểu link tra cứu lẫn link tải
khác nhau.

**Giải pháp.** Đảo ngược: thay vì người viết adapter cho từng cổng, **tool tự dò**
cách tải ngay từ link tra cứu có sẵn trong email, **tự xác minh** bằng cách parse
ra `Invoice` hợp lệ, rồi **tự nhớ** công thức để lần sau đi tắt. Nhà cung cấp cũ
không bao giờ phải làm lại từ đầu.

**Điểm mấu chốt của thiết kế:** registry công thức là **bộ nhớ đệm, không phải
điều kiện tiên quyết**. Một cổng chưa từng gặp vẫn tải được ngay lần đầu (chạy đủ
6 bước dò); có công thức chỉ để đi tắt, đỡ request và đỡ phụ thuộc vào giao diện
cổng. Đây là khác biệt so với hướng "phải dạy tool trước khi dùng" đã bàn rồi bỏ.

**Ai dùng:** kế toán MVL kê khai GTGT.
**Thành công =** danh sách "cần tải tay" ngắn lại, và **mọi dòng còn lại đều có
chẩn đoán cụ thể** ("SPA — cần trình duyệt", "có captcha", "thiếu mã") thay vì
im lặng thất bại.

### Quyết định đã chốt với người dùng (brainstorming 2026-08-25)

1. **Giữ nguyên cây thư mục** `data/<công ty>/<YYYY-MM>/<email người gửi>/` —
   không migrate 511 file đang có. File tải từ cổng đi qua đúng luồng lưu của
   file đính kèm, không có nhánh riêng.
2. **Sổ tổng hợp là CSV** (UTF-8 BOM, mở bằng Excel), **tích lũy qua mọi lần
   chạy** và **sửa tay được** — thay cho `can-tai-tay-<from>_<to>.csv` hiện nay
   vốn bị ghi đè mỗi lần chạy nên mất dấu.
3. **Dò tự động qua HTTP là cơ chế chính.** Nhánh trình duyệt (Chrome bắt XHR cho
   cổng SPA/captcha) **ngoài phạm vi spec này**, để thành mục riêng sau.

## 2. Tech Stack

Không thêm dependency mới.

- `requests` — đã dùng trong 3 adapter hiện có; giữ nguyên kiểu `Session` +
  `session_factory` tiêm được để test.
- Parse HTML bằng **regex + `html.parser` của thư viện chuẩn**. Không thêm
  BeautifulSoup: 3 adapter hiện có đều parse bằng regex (`parse_download_form`
  ở `einvoice_com_vn.py:26`), giữ cho nhất quán và khỏi phình phụ thuộc.
- `PyYAML` — đã dùng để đọc `settings.yaml`.
- `parse_xml.parse_invoice_xml` — dùng làm **thước đo xác minh** (xem §5, bước 5).

## 3. Commands

```bash
make test                                    # ./.venv/bin/python -m pytest -q
./.venv/bin/hdtool collect --from 2026-06-01 --to 2026-06-30 --include-suspect
./.venv/bin/hdtool ncc                       # (mới) xem sổ NCC + trạng thái dò
./.venv/bin/hdtool ncc --tai                 # (mới) tải lại các dòng đang chờ
```

## 4. Project Structure (file đụng tới)

```
src/hdtool/lookup.py            # (MỚI) bóc link tra cứu + mã ra khỏi email — thuần
src/hdtool/portal_probe.py      # (MỚI) dò cổng: phân loại trang, tìm link tải, xác minh
src/hdtool/ncc.py               # (MỚI) registry công thức: nạp/ghi/khớp/học/dựng URL
src/hdtool/worklist.py          # (MỚI) sổ CSV tích lũy, merge không đè ô sửa tay
src/hdtool/adapters/registry_adapter.py   # (MỚI) tải theo công thức trong registry
src/hdtool/adapters/base.py     # sửa: registry nhận thêm adapter dựng từ YAML
src/hdtool/collect.py           # sửa: save_invoice_files chống ghi đè
src/hdtool/cli.py               # sửa: lệnh `ncc`; collect ghi sổ thay vì CSV một-lần
src/hdtool/interactive.py       # sửa: thêm mục "tra cứu/tải hóa đơn chỉ-link"
config/ncc-registry.yaml        # (MỚI) sổ công thức, tool ghi — người sửa được
data/so-hoa-don-cho-tai.csv     # (MỚI, sinh ra lúc chạy) sổ hóa đơn chỉ-link
data/_chan-doan/                # (MỚI, sinh ra lúc chạy) HTML trang dò hỏng, để soi lại
tests/fixtures/portals/*.html   # (MỚI) HTML thật đã lược, để test offline
tests/test_lookup.py            # (MỚI)
tests/test_portal_probe.py      # (MỚI)
tests/test_ncc.py               # (MỚI)
tests/test_worklist.py          # (MỚI)
tests/test_registry_adapter.py  # (MỚI)
tests/test_collect.py           # thêm test chống ghi đè
docs/hdtool-tong-quan.md        # cập nhật lộ trình
tasks/plan.md                   # thêm "Đợt 7"
```

## 5. Thiết kế — quy trình dò 6 bước

Mỗi bước là một hàm thuần test được, trừ chỗ ghi rõ "có mạng".

### Bước 1 — Bóc link tra cứu & mã ra khỏi email (`lookup.py`, thuần)

```python
def rank_links(urls: list[str], sender: str, issuer_domains: list[str]) -> list[str]:
    """Xếp hạng URL trong mail theo khả năng là link tra cứu (cao → thấp)."""

def code_from_url(url: str) -> Optional[str]:
    """Mã nằm ngay trong query (?code=/?ma=/?c=...)."""

def find_code(text: str, html: str) -> Optional[str]:
    """Mã nằm trong nội dung: 'Mã tra cứu: ABC123' hoặc trong ô <td> của bảng."""
```

Một email hóa đơn thường có 5–15 URL (logo, website, mạng xã hội, hủy đăng ký).
**Không được lấy cái đầu tiên.** Chấm điểm:

- **Cộng**: query có tham số kiểu mã (`code`, `ma`, `mst`, `key`, `id`, `token`,
  `hash`, `c`); path chứa `tra-cuu`/`tracuu`/`lookup`/`invoice`/`hoadon`; domain
  nằm trong `issuer_domains` của `settings.yaml`.
- **Loại thẳng**: đuôi ảnh, `mailto:`, `unsubscribe`, `facebook|zalo|youtube`,
  URL không query trùng domain người gửi (thường là trang chủ).

Mã **thường KHÔNG nằm trong link** — ca phổ biến nhất ở VN là mail ghi "Mã tra
cứu: ABC123" còn link chỉ dẫn tới form trống. Nhãn cần bắt: `Mã tra cứu`,
`Mã nhận hóa đơn`, `Mã số bí mật`, `Mã bảo mật`, `Mã HĐ`, `Lookup code`, `Code`.
Hình dạng mã: 6–24 ký tự, chữ HOA + số + `_-`.

**Phải parse cả bản HTML của mail**, vì rất nhiều nhà phát hành đặt mã trong bảng
(`<td>Mã tra cứu</td><td>ABC123</td>`) — bản text phẳng dễ dính hai ô vào nhau.

Không ra được cả link lẫn mã → dừng, ghi sổ `khong-tim-thay-link`.

### Bước 2 — Lấy trang tra cứu và phân loại (`portal_probe.py`, **có mạng**)

```python
def classify_page(status: int, content_type: str, html: str) -> str:
    """-> 'file' | 'form' | 'links' | 'spa' | 'captcha' | 'error'"""
```

| Phản hồi | Nghĩa | Xử lý |
|---|---|---|
| Content-Type xml/zip/octet-stream | Link tra cứu **chính là** link tải | → bước 5 (ca VNPT/Fast) |
| HTML có anchor chứa mã | Cổng HTML thuần | → bước 4 |
| HTML có `<form>` nhập mã | Cần POST mã trước | → bước 3 |
| HTML chứa `recaptcha`/`captcha`/`hcaptcha` | Có captcha | **dừng**, chẩn đoán `co-captcha` |
| Ít text, nhiều `<script>`, không anchor nào chứa mã | SPA (meinvoice, easyinvoice) | **dừng**, chẩn đoán `spa-can-trinh-duyet` |
| 403/404/timeout | Link hỏng/hết hạn | **dừng**, chẩn đoán `link-hong` |

Chẩn đoán phải **cụ thể**, không được ghi "lỗi" — đó chính là thứ quyết định sau
này người dùng phải làm gì.

### Bước 3 — Nếu là form nhập mã thì điền và POST (**có mạng**)

```python
def find_form(html: str, base_url: str) -> Optional[Form]:
    """action, method, toàn bộ input (kể cả hidden + CSRF token)."""
```

Nhiều cổng bắt gõ mã vào ô rồi bấm Tra cứu. Tool đã có mã từ bước 1 nên làm được:
mang theo **toàn bộ hidden field và CSRF token**, POST đúng `action`. Đây chính là
pattern `einvoice.com.vn` đã chạy thật — spec này chỉ **tổng quát hóa cái đang
có**, không phát minh gì mới. Form có captcha → dừng.

Bước này là lý do quy trình mạnh hơn hẳn "chỉ đọc anchor": nó mở được nhóm cổng
HTML-có-form, vốn là phần lớn các cổng nhỏ.

### Bước 4 — Liệt kê ứng viên link tải (`portal_probe.py`, thuần)

```python
def candidate_download_links(html: str, base_url: str, code: str) -> list[str]:
    """Ứng viên link tải, xếp theo độ tin cậy giảm dần."""
```

1. `<a href>` mà href **chứa mã tra cứu** — tin cậy nhất.
2. `<a href>` chứa `xml`, `download`, `tai-ve`, `taive`, `export`.
3. `<a>` mà **chữ hiển thị** là "Tải XML", "Tải hóa đơn", "XML".
4. `<form action>` của nút tải (tải bằng POST).
5. URL trong `<script>` inline có chứa mã.

Chuẩn hóa link tương đối → tuyệt đối. Không ứng viên nào → dừng, chẩn đoán
`khong-thay-link-tai`.

### Bước 5 — Tải thử và **xác minh bằng dữ liệu** (**có mạng**)

```python
def accept_files(files: list[Attachment]) -> Optional[Invoice]:
    """Chỉ nhận khi parse ra Invoice hợp lệ. Không thì trả None."""
```

Đây là **chốt chặn quan trọng nhất của toàn bộ thiết kế**. Với tối đa 3 ứng viên
đầu bảng:

- ZIP → giải nén (`collect.expand_zips`), tìm XML bên trong.
- XML → `parse_invoice_xml` phải ra `Invoice` **có số hóa đơn, ngày lập, MST bán**.
- PDF → chỉ nhận **kèm** một XML đã hợp lệ, làm bản thể hiện. **PDF đơn độc
  không tính là thành công** và không được ghi vào `data/` (nguyên tắc "số liệu
  chỉ lấy từ XML" không đổi).
- HTML → thất bại (thường bị đá về trang lỗi).

**Bằng chứng duy nhất được chấp nhận là bytes parse ra hóa đơn hợp lệ.** Nhờ vậy
việc tool tự đoán "link nào là link tải" mới an toàn: đoán sai thì tự biết ngay,
không bao giờ ghi rác vào `data/`. MST bên mua không thuộc `companies` → vẫn lưu
(có thể là CC nhầm — vẫn là hóa đơn thật) nhưng ghi cảnh báo vào sổ.

### Bước 6 — Học công thức (`ncc.py`, thuần)

```python
def learn(download_url: str, ma: str) -> Optional[dict]:
    """Thay mã trong URL bằng {ma} -> công thức. None nếu URL không chứa mã."""
```

Tìm mã trong URL vừa thành công, thay bằng `{ma}`, ghi vào registry kèm: cách lấy
mã, có phải POST form không, **có cần cookie phiên không**. Thấy cặp `Type=xml` ↔
`Type=pdf` (hoặc `format=`, `loai=`) thì sinh thêm dòng PDF nhưng **đánh dấu chưa
kiểm chứng** cho tới lần tải thật đầu tiên.

**Trường hợp URL không chứa mã** (chứa token sinh theo phiên — ca VNPT/Fast):
không template hóa được. Registry ghi `phai_do_lai: true`; mọi thứ **vẫn tự
động**, chỉ là mỗi hóa đơn chạy lại bước 1–5 thay vì đi tắt.

### Sổ công thức (`config/ncc-registry.yaml`)

```yaml
- ten: meinvoice.vn (MISA)
  nhan_dien: [meinvoice.vn]
  bat_ma:
    tu_link: 'Code=([A-Za-z0-9_]+)'
    tu_text: 'Mã tra cứu[:\s]+([A-Za-z0-9_]+)'
  tai:
    xml: 'https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code={ma}'
    pdf: 'https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=pdf&Code={ma}'
  can_phien: false          # true -> phải GET trang tra cứu trước để lấy cookie
  hoc_tu: '...Type=xml&Code=GJF211_PDLEP'    # link mẫu, giữ để đối chứng
  ngay_hoc: 2026-08-25

- ten: einvoice.com.vn
  nhan_dien: [einvoice.com.vn]
  dung_adapter: einvoice_com_vn              # cổng phức tạp -> dùng code sẵn có
```

### Luồng trong `collect` sau khi sửa

```
email không có đính kèm
  ├─ NCC có công thức + bóc được mã  → dựng URL → tải → xác minh → xong
  │      (hỏng → tự rơi xuống nhánh dò để HỌC LẠI, cập nhật registry)
  ├─ NCC có adapter code (3 cái sẵn) → như hiện nay
  └─ còn lại                          → DÒ (bước 2→5) → thành công thì HỌC (bước 6)
```

Tự chữa lành: cổng đổi URL làm công thức hỏng → tool tự dò lại, không cần can thiệp.

### Sổ hóa đơn (`data/so-hoa-don-cho-tai.csv`)

Khóa dòng = `Message-ID`. Cột: `Ngày mail | Hộp thư | Người gửi | Tiêu đề | NCC |
Mã tra cứu | Link tra cứu | Trạng thái | Chẩn đoán | File | Ghi chú`.

Trạng thái: `đã tải` · `thiếu mã` · `chưa có công thức` · `cần trình duyệt (SPA)` ·
`có captcha` · `link hỏng` · `lỗi mạng` · `bỏ qua`.

`data/` nằm trong `.gitignore` nên sổ này là **dữ liệu cục bộ**, không commit —
ngược lại `config/ncc-registry.yaml` **có commit**, nên công thức học được đi
theo repo và máy khác dùng lại ngay.

**Merge, không ghi đè**: tool chỉ cập nhật `Trạng thái`/`Chẩn đoán`/`File`; ô
`Mã tra cứu` và `Ghi chú` do người dùng điền thì **giữ nguyên**. Người dùng gõ mã
vào dòng "thiếu mã" → chạy lại → tool tải được. Ghi qua file tạm rồi `replace`;
Excel đang mở file thì báo lỗi rõ ràng, không mất dữ liệu.

## 6. Testing Strategy (TDD bắt buộc — RED → GREEN → refactor)

- `lookup.py`, `ncc.py`, `worklist.py`, và phần thuần của `portal_probe.py`
  (`classify_page`, `find_form`, `candidate_download_links`, `accept_files`)
  test **hoàn toàn offline** bằng fixtures. Đây là phần lớn giá trị.
- **Fixtures HTML thật**: khi chạy thật, trang dò hỏng được lưu vào
  `data/_chan-doan/`; lược bớt rồi đưa vào `tests/fixtures/portals/` làm ca test
  hồi quy. Mỗi cổng gặp trong thực tế đẻ ra ít nhất một fixture.
- Phần có mạng (`probe`, `RegistryAdapter`) test bằng `session_factory` giả —
  đúng pattern 3 adapter hiện có.
- Ca bắt buộc phải có:
  - Trang SPA → `spa`, KHÔNG cố tải.
  - Trang captcha → `captcha`, KHÔNG cố vượt.
  - Ứng viên trả HTML → `accept_files` trả `None`, không ghi file.
  - `learn()` với link MISA thật → ra đúng template + dòng PDF.
  - `learn()` với link chứa token phiên → trả `None`, ghi `phai_do_lai`.
  - Người dùng điền mã tay → merge sổ không xóa mất.
  - Hai hóa đơn cùng tên file → không cái nào bị ghi đè.
- **Không test mạng thật trong CI.**

## 7. Boundaries (ngoài phạm vi spec này)

- **Trình duyệt / bắt XHR / giải captcha.** Cổng SPA và captcha sẽ dừng ở bước 2
  với chẩn đoán rõ ràng. Đây là mục riêng sau spec này.
- **Đổi cấu trúc thư mục `data/`** — người dùng đã chốt giữ nguyên.
- **Nhập tay hóa đơn không có trong mail** (nhóm B: Grab, ĐÔI CÁNH, MEGA) — việc
  khác, spec khác.
- **Đoán mò URL.** Chỉ đi theo link có thật trong email hoặc trong HTML trang tra
  cứu. Không brute-force mã, không dò tổ hợp tham số.
- Giới hạn kỹ thuật: ≤5 request/hóa đơn, ≤3 ứng viên tải, timeout 30s, nghỉ giữa
  các request cùng domain. Không vượt captcha trong mọi trường hợp.

## 8. Success Criteria (kiểm chứng được)

1. Chạy `hdtool collect` kỳ 06/2026: số dòng "cần tải tay" giảm so với 40 hiện
   nay, và **100% dòng còn lại có chẩn đoán cụ thể** (không dòng nào để trống).
2. Với ít nhất **một** cổng HTML thuần: lần chạy thứ nhất dò ra và học được; lần
   thứ hai dùng công thức — chứng minh bằng số request giảm.
3. **Không hóa đơn nào được ghi vào `data/` mà không parse được thành `Invoice`.**
4. Người dùng điền mã tay vào sổ CSV → chạy lại → tool tải được hóa đơn đó.
5. `make test` xanh, thêm ≥20 test mới, **không cần mạng**.
6. Cây thư mục `data/` không đổi, không phải migrate.
7. Nguyên tắc gốc còn nguyên: IMAP chỉ đọc; số liệu chỉ từ XML.

## 9. Open Questions (spike trước khi code — rẻ)

1. **Link MISA có tải được bằng GET thuần không**, hay đòi cookie/referer?
   Nếu được, ca MISA giải xong ngay ở bước 6 mà không cần bước 2–5.
2. **Trang tra cứu meinvoice có đúng là SPA không** (README ghi vậy từ 2026-07)?
   Quyết định 5 trong 13 hóa đơn đang thiếu của kỳ 06/2026 có cứu được không.
3. **40 dòng "cần tải tay" phân bố theo domain nào, mỗi domain thuộc loại trang
   nào** (HTML thuần / có form / SPA / captcha)? Đây là số liệu quyết định quy
   trình dò đáng giá bao nhiêu — có thể ăn 30/40, cũng có thể chỉ 5/40.
4. Bao nhiêu cổng cần **cookie phiên** giữa GET trang tra cứu và GET link tải?
   Ảnh hưởng tới việc công thức có đi tắt được hay vẫn phải GET trang trước.

**Câu 3 phải trả lời trước** vì nó định hình thứ tự triển khai của cả đợt, và làm
được mà không cần viết code.

## 10. Task breakdown (đưa vào `tasks/plan.md` — Đợt 7)

| Task | Nội dung | Phụ thuộc | Cần mạng |
|------|----------|-----------|----------|
| **T37** | **Khảo sát**: chạy `collect` dựng lại danh sách chỉ-link, thống kê theo domain + loại trang. Trả lời Open Question 1–4. Không viết code. | — | có (IMAP readonly + GET cổng) |
| **T38** | `worklist.py` + sổ CSV tích lũy, merge không đè ô sửa tay; thay `can-tai-tay-*.csv` | — | không |
| **T39** | `lookup.py`: chấm điểm link + bóc mã (text lẫn HTML) | — | không |
| **T40** | `portal_probe.py` phần thuần: `classify_page`, `find_form`, `candidate_download_links`, `accept_files` | T39 | không |
| **T41** | `probe()` orchestrator + tích hợp vào `collect` | T39, T40, T38 | mock |
| **T42** | `ncc.py` registry + `learn()` + `RegistryAdapter` + nhánh đi tắt | T41 | mock |
| **T43** | Lệnh `hdtool ncc` (xem sổ / tải lại) + mục trong menu tương tác | T42, T38 | không |
| **T44** | Vá `save_invoice_files` ghi đè khi trùng tên (`collect.py:157`) | — | không |
| **T45** | Chạy thật, đo kết quả, đưa HTML thu được thành fixtures, cập nhật `README`/`CLAUDE.md`/`adapters/README.md`/`plan.md` | tất cả | có |
| **T46** | *(mục riêng, sau spec này)* Nhánh trình duyệt cho cổng SPA/captcha | T45 | có |

Thứ tự đề nghị: **T37 → T44 → T38 → T39 → T40 → T41 → T42 → T43 → T45**.
T44 tách riêng vì độc lập, nhỏ, và đang là lỗi mất dữ liệu tiềm ẩn.
