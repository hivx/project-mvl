# Tự động tra cứu & tải hóa đơn chỉ-link — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tool tự dò cách tải hóa đơn từ link tra cứu trong email, tự xác minh bằng cách parse ra `Invoice` hợp lệ, rồi nhớ công thức để lần sau đi tắt — thay cho việc viết một adapter Python cho mỗi cổng.

**Architecture:** Bốn module thuần mới (`lookup`, `portal_probe`, `ncc`, `worklist`) + một adapter dựng từ cấu hình (`registry_adapter`). `collect` gọi theo thứ tự: công thức trong registry → 3 adapter code sẵn có → dò tự động. Registry là **bộ nhớ đệm**, không phải điều kiện tiên quyết: cổng chưa từng gặp vẫn tải được ngay lần đầu.

**Tech Stack:** Python 3, `requests` (đã có), `PyYAML` (đã có), `html.parser` + regex của thư viện chuẩn. **Không thêm dependency mới.**

**Spec:** `docs/superpowers/specs/2026-08-25-tu-dong-tra-cuu-tai-hoa-don.md`

## Global Constraints

Mọi task đều phải giữ:

- **IMAP chỉ đọc** — `readonly=True` + `BODY.PEEK`. Không đánh dấu đã đọc/xóa/di chuyển.
- **Số liệu chỉ lấy từ XML.** PDF chỉ nhận **kèm** một XML đã hợp lệ. PDF đơn độc không được ghi vào `data/`.
- **Không thêm thư viện Python mới.** Parse HTML bằng regex + `html.parser`, theo đúng `einvoice_com_vn.py:26`.
- **Degrade an toàn**: mọi hàm chạm mạng bọc `except Exception: return []` / `ProbeResult` rỗng. Một email hỏng không được làm sập batch.
- **Giới hạn dò**: ≤5 request HTTP cho mỗi hóa đơn, ≤3 ứng viên link tải, timeout 30s mỗi request, nghỉ 1s giữa hai request cùng domain.
- **Không đoán mò URL** — chỉ đi theo link có thật trong email hoặc trong HTML trang tra cứu. **Không bao giờ tìm cách vượt captcha.**
- **Không đổi cấu trúc `data/`**: vẫn là `data/<công ty>/<YYYY-MM>/<email người gửi>/`.
- **TDD bắt buộc**: RED → GREEN → refactor → `make test` xanh → commit.
- Docstring/comment bám theo file hàng xóm (module mới viết tiếng Việt như `reports.py`/`csv_report.py`).
- Trước mỗi commit: `git status` không được có `.env`.

---

## Task 1: Khảo sát dữ liệu thật (T37 — không viết code)

Trả lời Open Question 1–4 của spec. Kết quả định hình thứ tự các task sau: nếu 40 dòng chỉ-link chủ yếu là SPA thì quy trình dò ăn ít; nếu là HTML thuần thì ăn gần hết.

**Files:**
- Create: `docs/superpowers/specs/2026-08-25-khao-sat-cong-tra-cuu.md`
- Create: `data/_chan-doan/` (sinh lúc chạy, đã gitignore theo `data/`)

**Interfaces:**
- Consumes: — (dùng tool hiện có)
- Produces: bảng phân loại domain → loại trang, dùng cho Task 5 và Task 9

- [ ] **Step 1: Dựng lại danh sách hóa đơn chỉ-link**

```bash
./.venv/bin/hdtool collect --from 2026-06-01 --to 2026-06-30 --include-suspect
```

Lệnh này chạy qua **cả 3 hộp thư** (kể cả `mvl.invoices2024@gmail.com` vừa thêm, chưa quét lần nào) và ghi `data/can-tai-tay-2026-06-01_2026-06-30.csv`.

- [ ] **Step 2: Thống kê theo domain**

```bash
./.venv/bin/python - <<'PY'
import csv, collections, urllib.parse, glob
c = collections.Counter()
for f in glob.glob("data/can-tai-tay-*.csv"):
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        link = (r.get("Link tra cứu") or r.get("Link") or "").strip()
        host = urllib.parse.urlparse(link).netloc.lower() if link else "(không có link)"
        c[host] += 1
for host, n in c.most_common():
    print(f"{n:4d}  {host}")
PY
```

- [ ] **Step 3: Với mỗi domain top, lấy trang tra cứu và lưu lại để phân loại**

```bash
mkdir -p data/_chan-doan
./.venv/bin/python - <<'PY'
import csv, glob, pathlib, urllib.parse, requests
seen = set()
out = pathlib.Path("data/_chan-doan"); out.mkdir(parents=True, exist_ok=True)
for f in glob.glob("data/can-tai-tay-*.csv"):
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        link = (r.get("Link tra cứu") or r.get("Link") or "").strip()
        if not link:
            continue
        host = urllib.parse.urlparse(link).netloc.lower()
        if host in seen:
            continue
        seen.add(host)
        try:
            resp = requests.get(link, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            (out / f"{host}.html").write_bytes(resp.content)
            print(host, resp.status_code, resp.headers.get("content-type", ""), len(resp.content))
        except Exception as exc:
            print(host, "LỖI", exc)
PY
```

- [ ] **Step 4: Phân loại tay từng file HTML thu được**

Mở từng file trong `data/_chan-doan/` và xếp vào một trong: `html-thuần` (có `<a>` chứa mã hoặc chữ "Tải XML") · `có-form` (có `<form>` + ô nhập mã) · `spa` (ít text, toàn `<script>`) · `captcha` (có `recaptcha`/`captcha`) · `file` (content-type không phải HTML — link tra cứu chính là link tải).

```bash
grep -il "recaptcha\|captcha" data/_chan-doan/*.html
grep -il "<form" data/_chan-doan/*.html
grep -ic "<script" data/_chan-doan/*.html
```

- [ ] **Step 5: Thử riêng link tải MISA (Open Question 1)**

```bash
./.venv/bin/python - <<'PY'
import requests
u = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"
r = requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
print(r.status_code, r.headers.get("content-type"), len(r.content))
print(r.content[:200])
PY
```

Tải được XML bằng GET thuần ⇒ ca MISA giải xong ở Task 7 mà không cần bước dò.

- [ ] **Step 6: Ghi kết quả khảo sát**

Viết `docs/superpowers/specs/2026-08-25-khao-sat-cong-tra-cuu.md` gồm: bảng `domain | số HĐ | loại trang | tải được bằng HTTP?`, trả lời dứt khoát 4 Open Question của spec, và kết luận **quy trình dò dự kiến ăn được bao nhiêu trong tổng số dòng chỉ-link**.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/specs/2026-08-25-khao-sat-cong-tra-cuu.md
git commit -m "docs: khảo sát cổng tra cứu HĐ chỉ-link (T37)"
```

---

## Task 2: Vá lỗi ghi đè file trùng tên (T44)

Độc lập với phần còn lại, làm sớm vì đang là lỗi mất dữ liệu tiềm ẩn: hai hóa đơn khác nhau cùng người gửi, cùng tháng, cùng tên đính kèm `hoadon.xml` thì cái sau đè cái trước.

**Files:**
- Modify: `src/hdtool/collect.py:151-160` (`save_invoice_files`)
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `Attachment(filename, kind, data)`
- Produces: `save_invoice_files(files, dest_dir) -> dict[str, Path]` — giữ nguyên chữ ký, chỉ đổi hành vi khi trùng tên

- [ ] **Step 1: Viết test đỏ**

```python
def test_save_invoice_files_khong_ghi_de_khi_khac_noi_dung(tmp_path):
    """Hai HĐ khác nhau trùng tên file -> phải giữ cả hai."""
    save_invoice_files([Attachment("hoadon.xml", "xml", b"<A/>")], tmp_path)
    save_invoice_files([Attachment("hoadon.xml", "xml", b"<B/>")], tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hoadon-2.xml", "hoadon.xml"]
    assert (tmp_path / "hoadon.xml").read_bytes() == b"<A/>"
    assert (tmp_path / "hoadon-2.xml").read_bytes() == b"<B/>"


def test_save_invoice_files_trung_noi_dung_thi_dung_lai_file_cu(tmp_path):
    """Tải lại đúng file cũ -> không đẻ bản sao (giữ tính idempotent)."""
    a = Attachment("hoadon.xml", "xml", b"<A/>")
    save_invoice_files([a], tmp_path)
    saved = save_invoice_files([a], tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["hoadon.xml"]
    assert saved["xml"].name == "hoadon.xml"
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_collect.py -k ghi_de -v
```
Expected: FAIL — file thứ hai bị ghi đè nên chỉ có 1 file.

- [ ] **Step 3: Sửa `collect.py`**

```python
def _unique_target(dest: Path, filename: str, data: bytes) -> Path:
    """Đường dẫn ghi được: giữ tên gốc, trùng tên mà khác nội dung thì thêm -2, -3…

    Trùng cả nội dung -> trả lại chính file cũ (tải lại không đẻ bản sao).
    """
    target = dest / filename
    if not target.exists() or target.read_bytes() == data:
        return target
    stem, suffix = target.stem, target.suffix
    n = 2
    while True:
        cand = dest / f"{stem}-{n}{suffix}"
        if not cand.exists() or cand.read_bytes() == data:
            return cand
        n += 1


def save_invoice_files(files: list[Attachment], dest_dir) -> dict:
    """Write invoice files into ``dest_dir`` and return {kind: path}."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    saved: dict = {}
    for a in files:
        target = _unique_target(dest, a.filename, a.data)
        target.write_bytes(a.data)
        saved.setdefault(a.kind, target)
    return saved
```

- [ ] **Step 4: Chạy full test**

```bash
make test
```
Expected: PASS, không test cũ nào gãy.

- [ ] **Step 5: Commit**

```bash
git add src/hdtool/collect.py tests/test_collect.py
git commit -m "fix: không ghi đè hóa đơn trùng tên file (T44)"
```

---

## Task 3: Sổ hóa đơn chỉ-link tích lũy (T38)

Thay `can-tai-tay-<from>_<to>.csv` (bị ghi đè mỗi lần chạy nên mất dấu) bằng một sổ tích lũy sửa tay được.

**Files:**
- Create: `src/hdtool/worklist.py`
- Test: `tests/test_worklist.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `WorkRow` dataclass: `message_id, ngay_mail, hop_thu, nguoi_gui, tieu_de, ncc, ma_tra_cuu, link_tra_cuu, trang_thai, chan_doan, file, ghi_chu` (đều `str`)
  - `load(path) -> dict[str, WorkRow]`
  - `merge(cu: dict[str, WorkRow], moi: list[WorkRow]) -> list[WorkRow]`
  - `save(path, rows: list[WorkRow]) -> Path`
  - `upsert(path, rows: list[WorkRow]) -> Path`
  - Hằng: `HEADERS: list[str]`, `USER_FIELDS = ("ma_tra_cuu", "ghi_chu")`

- [ ] **Step 1: Viết test đỏ**

```python
"""Sổ hóa đơn chỉ-link: tích lũy qua mọi lần chạy, người dùng sửa tay được."""
from pathlib import Path

from hdtool.worklist import WorkRow, load, merge, save, upsert


def test_save_ghi_utf8_bom_va_doc_lai_duoc(tmp_path):
    p = tmp_path / "so.csv"
    save(p, [WorkRow(message_id="m1", nguoi_gui="kt@ncc.vn", trang_thai="đã tải")])
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")   # Excel đọc tiếng Việt đúng
    assert load(p)["m1"].nguoi_gui == "kt@ncc.vn"


def test_merge_giu_o_nguoi_dung_dien_tay():
    """Người dùng gõ mã vào dòng 'thiếu mã' -> chạy lại KHÔNG được xóa mất."""
    cu = {"m1": WorkRow(message_id="m1", ma_tra_cuu="ABC123", ghi_chu="tự điền")}
    moi = [WorkRow(message_id="m1", ma_tra_cuu="", trang_thai="thiếu mã",
                   chan_doan="không bóc được mã")]
    out = merge(cu, moi)
    assert out[0].ma_tra_cuu == "ABC123"          # ô người dùng: giữ
    assert out[0].ghi_chu == "tự điền"            # ô người dùng: giữ
    assert out[0].trang_thai == "thiếu mã"        # ô tool: cập nhật


def test_merge_giu_dong_cu_khong_con_trong_lan_chay_moi():
    cu = {"m1": WorkRow(message_id="m1", trang_thai="đã tải")}
    out = merge(cu, [WorkRow(message_id="m2", trang_thai="chưa có công thức")])
    assert sorted(r.message_id for r in out) == ["m1", "m2"]


def test_upsert_hai_lan_khong_nhan_doi_dong(tmp_path):
    p = tmp_path / "so.csv"
    upsert(p, [WorkRow(message_id="m1", trang_thai="chưa có công thức")])
    upsert(p, [WorkRow(message_id="m1", trang_thai="đã tải", file="data/x.xml")])
    rows = load(p)
    assert len(rows) == 1
    assert rows["m1"].trang_thai == "đã tải"
    assert rows["m1"].file == "data/x.xml"
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_worklist.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'hdtool.worklist'`

- [ ] **Step 3: Viết `src/hdtool/worklist.py`**

```python
"""Sổ hóa đơn CHỈ-CÓ-LINK — tích lũy qua mọi lần chạy, người dùng sửa tay được.

Khác `reports.write_manual_links_csv` (ghi đè mỗi lần chạy): sổ này giữ lịch sử,
và giữ nguyên các ô người dùng tự điền (mã tra cứu, ghi chú) khi tool ghi lại.
UTF-8 BOM để Excel đọc tiếng Việt đúng.
"""
from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

HEADERS = ["Message-ID", "Ngày mail", "Hộp thư", "Người gửi", "Tiêu đề", "NCC",
           "Mã tra cứu", "Link tra cứu", "Trạng thái", "Chẩn đoán", "File", "Ghi chú"]

#: Ô do NGƯỜI DÙNG điền — tool không bao giờ ghi đè khi đã có giá trị.
USER_FIELDS = ("ma_tra_cuu", "ghi_chu")


@dataclass
class WorkRow:
    message_id: str
    ngay_mail: str = ""
    hop_thu: str = ""
    nguoi_gui: str = ""
    tieu_de: str = ""
    ncc: str = ""
    ma_tra_cuu: str = ""
    link_tra_cuu: str = ""
    trang_thai: str = ""
    chan_doan: str = ""
    file: str = ""
    ghi_chu: str = ""


_ORDER = [f.name for f in fields(WorkRow)]


def load(path) -> dict:
    """Đọc sổ -> {message_id: WorkRow}. File chưa có -> {}."""
    p = Path(path)
    if not p.exists():
        return {}
    out: dict = {}
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if not row or row[0] == HEADERS[0]:
                continue
            row = (row + [""] * len(_ORDER))[:len(_ORDER)]
            item = WorkRow(**dict(zip(_ORDER, row)))
            out[item.message_id] = item
    return out


def merge(cu: dict, moi: list) -> list:
    """Gộp dòng mới vào sổ cũ. Ô người dùng đã điền thì GIỮ NGUYÊN."""
    ket_qua = dict(cu)
    for row in moi:
        truoc = ket_qua.get(row.message_id)
        if truoc is None:
            ket_qua[row.message_id] = row
            continue
        gop = asdict(row)
        for ten in USER_FIELDS:
            if getattr(truoc, ten, ""):
                gop[ten] = getattr(truoc, ten)
        ket_qua[row.message_id] = WorkRow(**gop)
    return list(ket_qua.values())


def save(path, rows: list) -> Path:
    """Ghi sổ qua file tạm rồi thay thế — Excel đang mở thì báo lỗi rõ, không mất dữ liệu."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADERS)
        for r in rows:
            writer.writerow([getattr(r, name, "") for name in _ORDER])
    try:
        os.replace(tmp, p)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OSError(f"Không ghi được sổ {p} (Excel đang mở file?): {exc}") from exc
    return p


def upsert(path, rows: list) -> Path:
    """load + merge + save."""
    return save(path, merge(load(path), rows))
```

- [ ] **Step 4: Chạy test**

```bash
./.venv/bin/python -m pytest tests/test_worklist.py -v && make test
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hdtool/worklist.py tests/test_worklist.py
git commit -m "feat: sổ hóa đơn chỉ-link tích lũy, sửa tay được (T38)"
```

---

## Task 4: Bóc link tra cứu & mã ra khỏi email (T39)

**Files:**
- Create: `src/hdtool/lookup.py`
- Test: `tests/test_lookup.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `code_from_url(url: str) -> Optional[str]`
  - `find_code(text: str, html: str = "") -> Optional[str]`
  - `rank_links(urls: list[str], sender: str, issuer_domains: list[str]) -> list[str]`

- [ ] **Step 1: Viết test đỏ**

```python
"""Bóc link tra cứu + mã tra cứu ra khỏi email. Thuần, không mạng."""
from hdtool.lookup import code_from_url, find_code, rank_links

MISA = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"


def test_code_from_url_lay_tham_so_code():
    assert code_from_url(MISA) == "GJF211_PDLEP"


def test_code_from_url_bo_qua_url_khong_co_ma():
    assert code_from_url("https://ncc.vn/trang-chu") is None


def test_find_code_tu_nhan_trong_text():
    body = "Kính gửi Quý khách,\nMã tra cứu: GJF211_PDLEP\nTrân trọng."
    assert find_code(body) == "GJF211_PDLEP"


def test_find_code_tu_bang_html():
    """Nhiều nhà phát hành đặt mã trong <td> — bản text phẳng dính hai ô vào nhau."""
    html = "<table><tr><td>Mã tra cứu</td><td> ABC123XYZ </td></tr></table>"
    assert find_code("", html) == "ABC123XYZ"


def test_find_code_khong_bat_nham_tu_tieng_viet():
    assert find_code("Mã tra cứu: xem trong file đính kèm") is None


def test_rank_links_uu_tien_link_co_ma_va_domain_nha_phat_hanh():
    urls = ["https://cdn.ncc.vn/logo.png",
            "https://facebook.com/ncc",
            "https://ncc.vn",
            "https://meinvoice.vn/tra-cuu?code=ABC123"]
    assert rank_links(urls, "kt@ncc.vn", ["meinvoice"])[0] == "https://meinvoice.vn/tra-cuu?code=ABC123"


def test_rank_links_loai_anh_va_unsubscribe():
    urls = ["https://x.vn/a.jpg", "https://x.vn/unsubscribe?u=1", "mailto:a@x.vn"]
    assert rank_links(urls, "a@x.vn", []) == []
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_lookup.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'hdtool.lookup'`

- [ ] **Step 3: Viết `src/hdtool/lookup.py`**

```python
"""Bóc LINK TRA CỨU và MÃ TRA CỨU ra khỏi email hóa đơn.

Một email hóa đơn thường có 5–15 URL (logo, website, mạng xã hội, hủy đăng ký).
Lấy cái đầu tiên là sai — phải chấm điểm. Mã thì thường KHÔNG nằm trong link:
mail ghi "Mã tra cứu: ABC123" còn link chỉ dẫn tới form trống.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

#: Tham số query thường chứa mã tra cứu.
_CODE_PARAMS = ("code", "ma", "matracuu", "mst", "key", "id", "token", "hash", "c", "sc")

#: Nhãn đứng trước mã trong nội dung mail.
_CODE_LABELS = (r"M[ãa]\s+tra\s+c[ứu]u", r"M[ãa]\s+nh[ậa]n\s+h[óo]a\s+[đd]\S*n",
                r"M[ãa]\s+s[ố o]\s+b[íi]\s+m[ậa]t", r"M[ãa]\s+b[ảa]o\s+m[ậa]t",
                r"M[ãa]\s+H[ĐD]", r"Lookup\s+code", r"Code")

#: Hình dạng mã: 6–24 ký tự, CHỮ HOA + số + _ -
_CODE_SHAPE = r"[A-Z0-9][A-Z0-9_-]{5,23}"

_BAD_URL = ("unsubscribe", "facebook.", "zalo.", "youtube.", "linkedin.", "twitter.")
_IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")


def code_from_url(url: str) -> Optional[str]:
    """Mã nằm ngay trong query của URL (?Code=/?ma=/?c=…)."""
    try:
        qs = parse_qs(urlparse(url or "").query)
    except ValueError:
        return None
    for key, values in qs.items():
        if key.lower() in _CODE_PARAMS:
            for v in values:
                v = v.strip()
                if re.fullmatch(_CODE_SHAPE, v):
                    return v
    return None


def find_code(text: str, html: str = "") -> Optional[str]:
    """Mã trong nội dung: 'Mã tra cứu: ABC123' hoặc ô <td> kế bên nhãn."""
    for label in _CODE_LABELS:
        m = re.search(label + r"\s*[:\-]?\s*(" + _CODE_SHAPE + r")\b", text or "")
        if m:
            return m.group(1)
    for label in _CODE_LABELS:
        m = re.search(label + r"\s*</t[dh]>\s*<t[dh][^>]*>\s*(" + _CODE_SHAPE + r")\s*<",
                      html or "", re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _score(url: str, sender_domain: str, issuer_domains: list[str]) -> int:
    low = url.lower()
    parsed = urlparse(low)
    score = 0
    if code_from_url(url):
        score += 5
    if any(k in parsed.query for k in _CODE_PARAMS):
        score += 2
    if re.search(r"tra-?cuu|lookup|invoice|hoadon|hddt", parsed.path):
        score += 3
    if any(d in parsed.netloc for d in issuer_domains if d):
        score += 3
    if not parsed.query and sender_domain and sender_domain in parsed.netloc:
        score -= 3        # thường là trang chủ NCC
    return score


def rank_links(urls: list[str], sender: str, issuer_domains: list[str]) -> list[str]:
    """URL trong mail, xếp theo khả năng là link tra cứu (cao -> thấp)."""
    m = re.search(r"@([\w.\-]+)", sender or "")
    sender_domain = m.group(1).lower() if m else ""
    ung_vien = []
    for url in urls or []:
        low = (url or "").lower()
        if not low.startswith("http"):
            continue
        if low.endswith(_IMG_EXT) or any(b in low for b in _BAD_URL):
            continue
        diem = _score(url, sender_domain, issuer_domains or [])
        if diem > 0:
            ung_vien.append((diem, url))
    ung_vien.sort(key=lambda x: -x[0])
    return [u for _, u in ung_vien]
```

- [ ] **Step 4: Chạy test**

```bash
./.venv/bin/python -m pytest tests/test_lookup.py -v && make test
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hdtool/lookup.py tests/test_lookup.py
git commit -m "feat: bóc link tra cứu + mã ra khỏi email (T39)"
```

---

## Task 5: Phân loại trang & tìm link tải — phần thuần (T40)

**Files:**
- Create: `src/hdtool/portal_probe.py`
- Create: `tests/fixtures/portals/` (HTML rút gọn từ `data/_chan-doan/` của Task 1)
- Test: `tests/test_portal_probe.py`

**Interfaces:**
- Consumes: `Attachment` từ `collect`, `parse_invoice_xml` từ `parse_xml`
- Produces:
  - `classify_page(status: int, content_type: str, html: str, ma: str = "") -> str` — trả `"file" | "form" | "links" | "spa" | "captcha" | "error"`
  - `find_form(html: str, base_url: str) -> Optional[dict]` — `{"action": str, "method": str, "fields": dict[str, str]}`
  - `candidate_download_links(html: str, base_url: str, ma: str = "") -> list[str]`
  - `accept_files(files: list[Attachment]) -> Optional[Invoice]`

- [ ] **Step 1: Viết test đỏ**

```python
"""Phân loại trang tra cứu + tìm link tải. Thuần, không mạng."""
from pathlib import Path

from hdtool.collect import Attachment
from hdtool.portal_probe import (accept_files, candidate_download_links,
                                 classify_page, find_form)

FIXTURES = Path(__file__).parent / "fixtures"
XML_OK = (FIXTURES / "inv_10pct.xml").read_bytes()


def test_classify_file_khi_content_type_khong_phai_html():
    assert classify_page(200, "application/xml; charset=utf-8", "") == "file"
    assert classify_page(200, "application/zip", "") == "file"


def test_classify_error_khi_http_loi():
    assert classify_page(404, "text/html", "<h1>Not found</h1>") == "error"


def test_classify_captcha_thang_truoc_moi_thu_khac():
    """Trang có captcha thường CŨNG có form -> captcha phải được xét trước."""
    html = '<form action="/tra-cuu"><input name="MaTraCuu"><div class="g-recaptcha"></div></form>'
    assert classify_page(200, "text/html", html) == "captcha"


def test_classify_spa_khi_toan_script_khong_anchor_nao_chua_ma():
    html = "<html><body><div id='app'></div>" + "<script src='/bundle.js'></script>" * 3 + "</body></html>"
    assert classify_page(200, "text/html", html, ma="ABC123") == "spa"


def test_classify_links_khi_anchor_chua_ma():
    html = '<a href="/dl?Code=ABC123&Type=xml">Tải XML</a>'
    assert classify_page(200, "text/html", html, ma="ABC123") == "links"


def test_classify_form_khi_co_o_nhap_ma():
    html = ('<form action="/tra-cuu" method="post"><input name="MaTraCuu">'
            '<input type="hidden" name="__RequestVerificationToken" value="t1"></form>')
    assert classify_page(200, "text/html", html) == "form"


def test_find_form_mang_theo_hidden_field():
    html = ('<form action="/tra-cuu" method="post"><input name="MaTraCuu" value="">'
            '<input type="hidden" name="__RequestVerificationToken" value="t1"></form>')
    f = find_form(html, "https://x.vn/trang")
    assert f["action"] == "https://x.vn/tra-cuu"
    assert f["method"] == "post"
    assert f["fields"]["__RequestVerificationToken"] == "t1"
    assert "MaTraCuu" in f["fields"]


def test_candidate_uu_tien_link_chua_ma_va_bo_link_khong_lien_quan():
    html = ('<a href="/help">Hướng dẫn</a>'
            '<a href="/tai-ve?id=9">Tải hóa đơn</a>'
            '<a href="/dl?Code=ABC123&Type=xml">Tải XML</a>')
    out = candidate_download_links(html, "https://x.vn/trang", "ABC123")
    assert out[0] == "https://x.vn/dl?Code=ABC123&Type=xml"
    assert "https://x.vn/help" not in out


def test_accept_files_nhan_xml_hop_le():
    inv = accept_files([Attachment("hd.xml", "xml", XML_OK)])
    assert inv is not None and inv.so_hd == "123"


def test_accept_files_tu_choi_trang_html_gia_dang():
    assert accept_files([Attachment("hd.xml", "xml", b"<html><body>Loi</body></html>")]) is None


def test_accept_files_tu_choi_pdf_don_doc():
    """Nguyên tắc: số liệu chỉ từ XML. PDF đơn độc KHÔNG tính là thành công."""
    assert accept_files([Attachment("hd.pdf", "pdf", b"%PDF-1.4 fake")]) is None
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_portal_probe.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'hdtool.portal_probe'`

- [ ] **Step 3: Viết phần thuần của `src/hdtool/portal_probe.py`**

```python
"""Dò cổng tra cứu: phân loại trang, đọc form, tìm link tải, XÁC MINH kết quả.

Bằng chứng duy nhất được chấp nhận là bytes tải về parse ra `Invoice` hợp lệ —
nhờ vậy việc tool tự đoán "link nào là link tải" không bao giờ ghi rác vào data/.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from .collect import Attachment
from .models import Invoice
from .parse_xml import InvoiceParseError, parse_invoice_xml

_CAPTCHA = ("recaptcha", "g-recaptcha", "hcaptcha", "captcha")
_MA_INPUT = re.compile(r'name="([^"]*(?:ma|code|key)[^"]*)"', re.IGNORECASE)
_DL_HINT = ("xml", "download", "tai-ve", "taive", "export", "downloadhandler")
_DL_TEXT = re.compile(r">\s*(t[ảa]i\s+xml|t[ảa]i\s+h[óo]a\s+[đd]\S*n|xml)\s*<", re.IGNORECASE)


def classify_page(status: int, content_type: str, html: str, ma: str = "") -> str:
    """-> 'file' | 'captcha' | 'spa' | 'links' | 'form' | 'error'."""
    if status >= 400:
        return "error"
    ct = (content_type or "").lower()
    if ct and "html" not in ct and "text/plain" not in ct:
        return "file"
    doc = html or ""
    low = doc.lower()
    if any(k in low for k in _CAPTCHA):
        return "captcha"          # xét TRƯỚC form: trang captcha cũng có form
    if _anchors(doc, "", ma):
        return "links"
    if "<form" in low:
        return "form"
    if low.count("<script") >= 2 and "<a " not in low:
        return "spa"
    return "spa" if low.count("<script") >= 2 else "error"


def find_form(html: str, base_url: str) -> Optional[dict]:
    """Form đầu tiên: action tuyệt đối, method, và TOÀN BỘ input (kể cả hidden)."""
    m = re.search(r"<form\b([^>]*)>(.*?)</form>", html or "", re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    attrs, body = m.group(1), m.group(2)
    action = re.search(r'action="([^"]*)"', attrs, re.IGNORECASE)
    method = re.search(r'method="([^"]*)"', attrs, re.IGNORECASE)
    fields: dict = {}
    for inp in re.findall(r"<input\b[^>]*>", body, re.IGNORECASE):
        name = re.search(r'name="([^"]+)"', inp, re.IGNORECASE)
        if not name:
            continue
        value = re.search(r'value="([^"]*)"', inp, re.IGNORECASE)
        fields[name.group(1)] = value.group(1) if value else ""
    return {
        "action": urljoin(base_url, action.group(1) if action else ""),
        "method": (method.group(1) if method else "get").lower(),
        "fields": fields,
    }


def _anchors(html: str, base_url: str, ma: str = "") -> list[str]:
    """Ứng viên link tải, xếp theo độ tin cậy giảm dần."""
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                         html or "", re.IGNORECASE | re.DOTALL):
        href, text = m.group(1), m.group(2)
        diem = 0
        if ma and ma in href:
            diem += 5
        if any(h in href.lower() for h in _DL_HINT):
            diem += 3
        if _DL_TEXT.search(">" + text + "<"):
            diem += 2
        if diem:
            found.append((diem, urljoin(base_url, href)))
    found.sort(key=lambda x: -x[0])
    return [u for _, u in found]


def candidate_download_links(html: str, base_url: str, ma: str = "") -> list[str]:
    """Link tải ứng viên (anchor + URL trong <script> có chứa mã)."""
    out = _anchors(html, base_url, ma)
    if ma:
        for m in re.finditer(r"[\"'](/?[^\"'\s]*" + re.escape(ma) + r"[^\"'\s]*)[\"']", html or ""):
            url = urljoin(base_url, m.group(1))
            if url not in out:
                out.append(url)
    return out


def accept_files(files: list) -> Optional[Invoice]:
    """Chỉ nhận khi có XML parse ra Invoice hợp lệ. PDF đơn độc -> None."""
    for f in files or []:
        if f.kind != "xml":
            continue
        try:
            inv = parse_invoice_xml(f.data)
        except InvoiceParseError:
            continue
        if inv.so_hd and inv.ngay_lap and inv.mst_ban:
            return inv
    return None
```

- [ ] **Step 4: Chạy test**

```bash
./.venv/bin/python -m pytest tests/test_portal_probe.py -v && make test
```
Expected: PASS

- [ ] **Step 5: Thêm fixture HTML thật từ Task 1**

Chép 2–3 file từ `data/_chan-doan/` sang `tests/fixtures/portals/`, cắt bớt cho ngắn (giữ đúng phần quyết định: anchor / form / thẻ script / khối captcha), rồi thêm test hồi quy:

```python
def test_classify_fixture_that_khop_ket_qua_khao_sat():
    """Mỗi cổng gặp thật đẻ ra một ca hồi quy — chống việc sửa regex làm hỏng cổng cũ."""
    for ten, mong_doi in [("meinvoice.html", "spa"), ("ehoadon.html", "captcha")]:
        f = FIXTURES / "portals" / ten
        if not f.exists():
            continue
        assert classify_page(200, "text/html", f.read_text(encoding="utf-8", errors="replace")) == mong_doi
```

- [ ] **Step 6: Commit**

```bash
git add src/hdtool/portal_probe.py tests/test_portal_probe.py tests/fixtures/portals
git commit -m "feat: phân loại trang tra cứu + tìm link tải, xác minh bằng parse XML (T40)"
```

---

## Task 6: `probe()` chạm mạng + tích hợp `collect` (T41)

**Files:**
- Modify: `src/hdtool/portal_probe.py` (thêm `ProbeResult`, `probe`, `fetch_link_only`)
- Modify: `src/hdtool/cli.py:152-205` (`cmd_collect`)
- Test: `tests/test_portal_probe.py`

**Interfaces:**
- Consumes: `classify_page`, `find_form`, `candidate_download_links`, `accept_files` (Task 5); `worklist.WorkRow`, `worklist.upsert` (Task 3)
- Produces:
  - `ProbeResult` dataclass: `files: list[Attachment]`, `download_url: Optional[str]`, `page_kind: str`, `chan_doan: str`
  - `probe(url: str, ma: Optional[str] = None, session_factory=None) -> ProbeResult`
  - `fetch_link_only(links: list[str], ma: Optional[str] = None, session_factory=None) -> ProbeResult`
  - Hằng: `MAX_REQUESTS = 5`, `MAX_CANDIDATES = 3`

- [ ] **Step 1: Viết test đỏ**

```python
from hdtool.portal_probe import ProbeResult, probe


class FakeResp:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")


class FakeSession:
    """Trả response theo đúng URL được gọi; đếm số request."""
    def __init__(self, by_url):
        self.by_url = by_url
        self.headers = {}
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        return self.by_url.get(url, FakeResp(b"", status=404))

    def post(self, url, data=None, **kw):
        self.calls.append(url)
        return self.by_url.get(url, FakeResp(b"", status=404))


HTML_TRANG = b'<html><a href="/dl?Code=ABC123&Type=xml">Tai XML</a></html>'


def test_probe_tai_va_xac_minh_duoc_tu_trang_html_thuan():
    sess = FakeSession({
        "https://x.vn/tra-cuu?c=ABC123": FakeResp(HTML_TRANG, headers={"content-type": "text/html"}),
        "https://x.vn/dl?Code=ABC123&Type=xml": FakeResp(
            XML_OK, headers={"content-type": "application/xml",
                             "content-disposition": 'attachment;filename="hd.xml"'}),
    })
    res = probe("https://x.vn/tra-cuu?c=ABC123", "ABC123", lambda: sess)
    assert res.page_kind == "links"
    assert res.download_url == "https://x.vn/dl?Code=ABC123&Type=xml"
    assert [f.kind for f in res.files] == ["xml"]


def test_probe_dung_ngay_khi_gap_captcha_va_khong_tai_gi():
    sess = FakeSession({"https://x.vn/p": FakeResp(
        b'<div class="g-recaptcha"></div>', headers={"content-type": "text/html"})})
    res = probe("https://x.vn/p", "ABC123", lambda: sess)
    assert res.page_kind == "captcha" and res.files == []
    assert len(sess.calls) == 1          # KHÔNG thử tải thêm gì


def test_probe_khong_nhan_ung_vien_tra_ve_html():
    sess = FakeSession({
        "https://x.vn/p": FakeResp(HTML_TRANG, headers={"content-type": "text/html"}),
        "https://x.vn/dl?Code=ABC123&Type=xml": FakeResp(
            b"<html>Het han</html>", headers={"content-type": "text/html"}),
    })
    res = probe("https://x.vn/p", "ABC123", lambda: sess)
    assert res.files == [] and res.chan_doan


def test_probe_khong_vuot_qua_gioi_han_request():
    many = "".join(f'<a href="/dl{i}?Code=ABC123">Tai XML</a>' for i in range(10))
    sess = FakeSession({"https://x.vn/p": FakeResp(
        many.encode(), headers={"content-type": "text/html"})})
    probe("https://x.vn/p", "ABC123", lambda: sess)
    assert len(sess.calls) <= 5          # MAX_REQUESTS
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_portal_probe.py -k probe -v
```
Expected: FAIL — `ImportError: cannot import name 'probe'`

- [ ] **Step 3: Thêm phần chạm mạng vào `portal_probe.py`**

```python
import time
from dataclasses import dataclass, field

import requests

from .adapters import try_fetch_links
from .collect import _kind, expand_zips

MAX_REQUESTS = 5
MAX_CANDIDATES = 3

_CHAN_DOAN = {
    "captcha": "có captcha — cần trình duyệt",
    "spa": "SPA — cần trình duyệt",
    "error": "link hỏng hoặc hết hạn",
}


@dataclass
class ProbeResult:
    files: list = field(default_factory=list)
    download_url: Optional[str] = None
    page_kind: str = ""
    chan_doan: str = ""


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _filename(cd: str, fallback: str = "hoadon.xml") -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd or "")
    return m.group(1).strip() if m else fallback


def _as_files(resp) -> list:
    """Response -> Attachment (giải nén zip nếu cần)."""
    ct = (resp.headers.get("content-type") or "").lower()
    if "html" in ct or not getattr(resp, "content", b""):
        return []
    fname = _filename(resp.headers.get("content-disposition", ""))
    return expand_zips([Attachment(fname, _kind(fname), resp.content)])


def probe(url: str, ma: Optional[str] = None, session_factory=None) -> ProbeResult:
    """Dò một link tra cứu: lấy trang -> phân loại -> (POST form) -> tải -> xác minh."""
    try:
        session = (session_factory or _new_session)()
        used = 0
        resp = session.get(url, timeout=30)
        used += 1
        kind = classify_page(resp.status_code,
                             resp.headers.get("content-type", ""),
                             getattr(resp, "text", ""), ma or "")
        if kind == "file":
            files = _as_files(resp)
            return (ProbeResult(files, url, kind) if accept_files(files)
                    else ProbeResult([], None, kind, "tải được file nhưng không parse ra hóa đơn"))
        if kind in _CHAN_DOAN:
            return ProbeResult([], None, kind, _CHAN_DOAN[kind])

        html, base = getattr(resp, "text", ""), url
        if kind == "form":
            form = find_form(html, url)
            if not form or not ma:
                return ProbeResult([], None, kind, "trang cần nhập mã nhưng không có mã")
            for ten in list(form["fields"]):
                if _MA_INPUT.fullmatch(f'name="{ten}"') and not form["fields"][ten]:
                    form["fields"][ten] = ma
            resp = (session.post(form["action"], data=form["fields"], timeout=30)
                    if form["method"] == "post"
                    else session.get(form["action"], params=form["fields"], timeout=30))
            used += 1
            html, base = getattr(resp, "text", ""), form["action"]

        for cand in candidate_download_links(html, base, ma or "")[:MAX_CANDIDATES]:
            if used >= MAX_REQUESTS:
                break
            time.sleep(1)                       # lịch sự với cổng
            dl = session.get(cand, timeout=30)
            used += 1
            files = _as_files(dl)
            if accept_files(files):
                return ProbeResult(files, cand, "links")
        return ProbeResult([], None, kind or "links", "không tìm thấy link tải dùng được")
    except Exception as exc:  # noqa: BLE001 - không bao giờ làm sập batch
        return ProbeResult([], None, "error", f"lỗi mạng: {exc}")


def fetch_link_only(links: list, ma: Optional[str] = None, session_factory=None) -> ProbeResult:
    """Adapter code sẵn có trước (nhanh, đã kiểm chứng), không được thì mới dò."""
    files = try_fetch_links(links or [], ma)
    if files and accept_files(files):
        return ProbeResult(files, links[0] if links else None, "adapter")
    for url in (links or [])[:2]:
        res = probe(url, ma, session_factory)
        if res.files:
            return res
    return res if links else ProbeResult([], None, "error", "không có link tra cứu")
```

`time.sleep(1)` làm test chậm — trong test truyền `session_factory` và **monkeypatch** `portal_probe.time.sleep`:

```python
@pytest.fixture(autouse=True)
def _khong_ngu(monkeypatch):
    monkeypatch.setattr("hdtool.portal_probe.time.sleep", lambda *_: None)
```

- [ ] **Step 4: Chạy test**

```bash
./.venv/bin/python -m pytest tests/test_portal_probe.py -v && make test
```
Expected: PASS

- [ ] **Step 5: Nối vào `cmd_collect`**

Trong `src/hdtool/cli.py`, thay nhánh link-only hiện tại (`links = extract_links(...)` → `try_fetch_links` → `need_manual`) bằng:

```python
                    if not files:
                        links = lookup.rank_links(
                            extract_links(msg, settings.classifier.issuer_domains + ["tracuu", "hoadon"]),
                            c.sender, settings.classifier.issuer_domains)
                        # _body_text gộp CẢ text/plain lẫn text/html (collect.py:109)
                        # nên truyền cùng một chuỗi cho hai tham số là đủ.
                        body = _body_text(msg)
                        ma = (lookup.code_from_url(links[0]) if links else None) \
                            or lookup.find_code(body, body)
                        res = portal_probe.fetch_link_only(links, ma)
                        if not res.files:
                            so_rows.append(worklist.WorkRow(
                                message_id=c.message_id,
                                ngay_mail=str(c.internal_date or ""), hop_thu=c.account,
                                nguoi_gui=c.sender, tieu_de=c.subject,
                                ncc=urlparse(links[0]).netloc if links else "",
                                ma_tra_cuu=ma or "",
                                link_tra_cuu=links[0] if links else "",
                                trang_thai="thiếu mã" if not ma else "chưa tải được",
                                chan_doan=res.chan_doan))
                            continue
                        files = res.files
```

và cuối vòng lặp, thay `write_manual_links_csv` bằng:

```python
    if so_rows:
        so = settings.data_dir / "so-hoa-don-cho-tai.csv"
        worklist.upsert(so, so_rows)
        print(f"→ Sổ hóa đơn chỉ-link: {so} ({len(so_rows)} dòng cập nhật)")
```

Hóa đơn tải được cũng phải ghi một dòng `trang_thai="đã tải"` kèm `file=` để sổ phản ánh đủ.

- [ ] **Step 6: Chạy full test + kiểm tra bằng tay trên 1 kỳ nhỏ**

```bash
make test
./.venv/bin/hdtool collect --from 2026-06-01 --to 2026-06-30 --include-suspect
head -3 data/so-hoa-don-cho-tai.csv
```
Expected: test xanh; sổ có dòng và **mọi dòng chưa tải được đều có cột Chẩn đoán không rỗng**.

- [ ] **Step 7: Commit**

```bash
git add src/hdtool/portal_probe.py src/hdtool/cli.py tests/test_portal_probe.py
git commit -m "feat: dò cổng tra cứu tự động + ghi sổ chỉ-link trong collect (T41)"
```

---

## Task 7: Registry công thức + đi tắt (T42)

**Files:**
- Create: `src/hdtool/ncc.py`
- Create: `src/hdtool/adapters/registry_adapter.py`
- Create: `config/ncc-registry.yaml` (khởi tạo với 3 cổng đã có adapter)
- Modify: `src/hdtool/portal_probe.py` (`fetch_link_only` thêm nhánh registry + gọi `learn`)
- Test: `tests/test_ncc.py`, `tests/test_registry_adapter.py`

**Interfaces:**
- Consumes: `ProbeResult` (Task 6), `Attachment`, `accept_files`
- Produces:
  - `NccEntry` dataclass: `ten: str`, `nhan_dien: list[str]`, `bat_ma: dict`, `tai: dict`, `can_phien: bool = False`, `dung_adapter: str = ""`, `phai_do_lai: bool = False`, `hoc_tu: str = ""`, `ngay_hoc: str = ""`
  - `load_registry(path) -> list[NccEntry]`
  - `save_registry(path, entries: list[NccEntry]) -> Path`
  - `match(entries: list[NccEntry], url: str) -> Optional[NccEntry]`
  - `learn(download_url: str, ma: str, ten: str = "", ngay: str = "") -> NccEntry`
  - `build_url(entry: NccEntry, ma: str, loai: str = "xml") -> Optional[str]`
  - `RegistryAdapter(entry, session_factory=None)` với `.name`, `.can_handle(url)`, `.fetch(url, code=None)`

**Ghi chú lệch spec:** spec §5 bước 6 viết `learn()` trả `None` khi URL không chứa mã. Ở đây `learn()` **luôn trả `NccEntry`**, chỉ đặt `phai_do_lai=True` và `tai={}` — để vẫn ghi nhận được NCC đó vào registry. Sửa lại dòng đó trong spec khi làm task này.

- [ ] **Step 1: Viết test đỏ**

```python
"""Registry công thức tải theo NCC: học 1 lần, dùng mãi."""
from hdtool.ncc import NccEntry, build_url, learn, load_registry, match, save_registry

MISA = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"


def test_learn_suy_cong_thuc_va_sinh_luon_dong_pdf():
    e = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn", ngay="2026-08-25")
    assert e.tai["xml"] == "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code={ma}"
    assert e.tai["pdf"] == "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=pdf&Code={ma}"
    assert e.nhan_dien == ["meinvoice.vn"]
    assert e.hoc_tu == MISA and not e.phai_do_lai


def test_learn_danh_dau_phai_do_lai_khi_url_khong_chua_ma():
    """Link ký theo phiên (VNPT/Fast) không template hóa được -> vẫn auto, chỉ không đi tắt."""
    e = learn("https://x.vn/getinvoice?token=EPHEMERAL999", "ABC123", ten="x.vn")
    assert e.phai_do_lai and e.tai == {}


def test_build_url_thay_ma():
    e = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    assert build_url(e, "QQWZK_9911") == \
        "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=QQWZK_9911"


def test_build_url_tra_none_khi_chua_co_cong_thuc():
    assert build_url(NccEntry(ten="x", nhan_dien=["x.vn"], bat_ma={}, tai={}), "ABC") is None


def test_match_theo_nhan_dien():
    entries = [NccEntry(ten="MISA", nhan_dien=["meinvoice.vn"], bat_ma={}, tai={})]
    assert match(entries, "https://meinvoice.vn/tra-cuu?c=1").ten == "MISA"
    assert match(entries, "https://khac.vn/tra-cuu") is None


def test_roundtrip_yaml(tmp_path):
    p = tmp_path / "ncc.yaml"
    save_registry(p, [learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn", ngay="2026-08-25")])
    lai = load_registry(p)
    assert lai[0].tai["xml"].endswith("Code={ma}")
```

```python
"""Adapter dựng từ một dòng registry (không phải code riêng cho từng cổng)."""
from hdtool.adapters.registry_adapter import RegistryAdapter
from hdtool.ncc import learn

MISA = "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=GJF211_PDLEP"


def test_fetch_dung_cong_thuc_voi_ma_moi():
    entry = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    sess = FakeSession({
        "https://meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=NEW_CODE1":
            FakeResp(XML_OK, headers={"content-type": "application/xml",
                                      "content-disposition": 'attachment;filename="hd.xml"'}),
    })
    files = RegistryAdapter(entry, session_factory=lambda: sess).fetch("", "NEW_CODE1")
    assert [f.kind for f in files] == ["xml"]


def test_fetch_tra_rong_khi_cong_tra_html():
    entry = learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")
    sess = FakeSession({})     # mọi URL -> 404
    assert RegistryAdapter(entry, session_factory=lambda: sess).fetch("", "NEW_CODE1") == []
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_ncc.py tests/test_registry_adapter.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'hdtool.ncc'`

- [ ] **Step 3: Viết `src/hdtool/ncc.py`**

```python
"""Sổ công thức tải theo nhà cung cấp — BỘ NHỚ ĐỆM của quy trình dò.

Cổng chưa từng gặp vẫn tải được (portal_probe.probe chạy đủ các bước). Có công
thức chỉ để đi tắt: đỡ request, đỡ phụ thuộc giao diện cổng.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml


@dataclass
class NccEntry:
    ten: str
    nhan_dien: list
    bat_ma: dict = field(default_factory=dict)
    tai: dict = field(default_factory=dict)
    can_phien: bool = False
    dung_adapter: str = ""
    phai_do_lai: bool = False
    hoc_tu: str = ""
    ngay_hoc: str = ""


_TEN_FIELD = {f.name for f in fields(NccEntry)}


def load_registry(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    out = []
    for item in raw:
        item = {k: v for k, v in (item or {}).items() if k in _TEN_FIELD}
        item.setdefault("nhan_dien", [])
        out.append(NccEntry(**item))
    return out


def save_registry(path, entries: list) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump([asdict(e) for e in entries],
                                allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def match(entries: list, url: str) -> Optional[NccEntry]:
    low = (url or "").lower()
    for e in entries or []:
        if any(h and h.lower() in low for h in e.nhan_dien):
            return e
    return None


def learn(download_url: str, ma: str, ten: str = "", ngay: str = "") -> NccEntry:
    """Thay mã trong URL bằng {ma}. URL không chứa mã -> phai_do_lai=True."""
    host = urlparse(download_url or "").netloc.lower()
    entry = NccEntry(ten=ten or host, nhan_dien=[host] if host else [],
                     hoc_tu=download_url or "", ngay_hoc=ngay)
    if not ma or not download_url or ma not in download_url:
        entry.phai_do_lai = True
        return entry
    mau = download_url.replace(ma, "{ma}")
    entry.tai = {"xml": mau}
    pdf = re.sub(r"(?i)((?:type|format|loai)=)xml", r"\g<1>pdf", mau)
    if pdf != mau:
        entry.tai["pdf"] = pdf
    entry.bat_ma = {"tu_link": re.escape(mau.split("{ma}")[0]) + r"([A-Za-z0-9_-]+)"}
    return entry


def build_url(entry: NccEntry, ma: str, loai: str = "xml") -> Optional[str]:
    mau = (entry.tai or {}).get(loai)
    return mau.replace("{ma}", ma) if (mau and ma) else None
```

- [ ] **Step 4: Viết `src/hdtool/adapters/registry_adapter.py`**

```python
"""Adapter dựng từ MỘT DÒNG registry — không phải code riêng cho từng cổng.

Thêm nhà cung cấp mới = thêm dữ liệu vào config/ncc-registry.yaml (tool tự ghi
sau khi dò thành công), không phải viết file Python mới.
"""
from __future__ import annotations

import re
from typing import Optional

import requests

from ..collect import Attachment, _kind, expand_zips
from ..ncc import NccEntry, build_url


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _filename(cd: str, fallback: str) -> str:
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd or "")
    return m.group(1).strip() if m else fallback


class RegistryAdapter:
    """Tải theo công thức đã học. Lỗi -> [] để rơi về nhánh dò."""

    def __init__(self, entry: NccEntry, session_factory=None):
        self.entry = entry
        self.name = entry.ten
        self.match_hints = list(entry.nhan_dien or [])
        self._session_factory = session_factory or _new_session

    def can_handle(self, url: str) -> bool:
        low = (url or "").lower()
        return bool(self.entry.tai) and any(h.lower() in low for h in self.match_hints)

    def fetch(self, url: str, code: Optional[str] = None) -> list:
        if not code:
            return []
        try:
            session = self._session_factory()
            out: list = []
            for loai, fallback in (("xml", "hoadon.xml"), ("pdf", "hoadon.pdf")):
                target = build_url(self.entry, code, loai)
                if not target:
                    continue
                resp = session.get(target, timeout=30)
                if getattr(resp, "status_code", 0) != 200:
                    continue
                ct = (resp.headers.get("content-type") or "").lower()
                if "html" in ct or not getattr(resp, "content", b""):
                    continue
                fname = _filename(resp.headers.get("content-disposition", ""), fallback)
                out.extend(expand_zips([Attachment(fname, _kind(fname), resp.content)]))
            return out
        except Exception:  # noqa: BLE001 - không bao giờ làm sập batch
            return []
```

- [ ] **Step 5: Nối registry vào `fetch_link_only`**

```python
def fetch_link_only(links: list, ma=None, session_factory=None,
                    registry_path=None) -> ProbeResult:
    """Công thức -> adapter code -> dò. Dò thành công thì HỌC và ghi registry."""
    from . import ncc
    from .adapters.registry_adapter import RegistryAdapter

    entries = ncc.load_registry(registry_path) if registry_path else []
    for url in links or []:
        entry = ncc.match(entries, url)
        if entry and entry.tai and ma:
            files = RegistryAdapter(entry, session_factory).fetch(url, ma)
            if accept_files(files):
                return ProbeResult(files, ncc.build_url(entry, ma), "cong-thuc")
            break              # công thức hỏng -> rơi xuống dò để HỌC LẠI

    files = try_fetch_links(links or [], ma)
    if files and accept_files(files):
        return ProbeResult(files, (links or [None])[0], "adapter")

    res = ProbeResult([], None, "error", "không có link tra cứu")
    for url in (links or [])[:2]:
        res = probe(url, ma, session_factory)
        if res.files:
            if registry_path and res.download_url and ma:
                moi = ncc.learn(res.download_url, ma,
                                ten=urlparse(url).netloc, ngay=str(date.today()))
                entries = [e for e in entries if not ncc.match([e], url)] + [moi]
                ncc.save_registry(registry_path, entries)
            break
    return res
```

Thêm test khóa hành vi tự chữa lành **vào `tests/test_portal_probe.py`** (dùng lại `FakeSession`/`FakeResp`/`XML_OK` đã có ở đó; import thêm `learn`, `load_registry`, `save_registry` từ `hdtool.ncc`):

```python
def test_cong_thuc_hong_thi_ro_xuong_do_va_hoc_lai(tmp_path):
    reg = tmp_path / "ncc.yaml"
    save_registry(reg, [learn("https://x.vn/dl?Code=OLD", "OLD", ten="x.vn")])
    sess = FakeSession({
        "https://x.vn/dl?Code=ABC123": FakeResp(b"<html>404</html>",
                                                headers={"content-type": "text/html"}),
        "https://x.vn/p": FakeResp(b'<a href="/moi?Code=ABC123&Type=xml">Tai XML</a>',
                                   headers={"content-type": "text/html"}),
        "https://x.vn/moi?Code=ABC123&Type=xml": FakeResp(
            XML_OK, headers={"content-type": "application/xml"}),
    })
    res = fetch_link_only(["https://x.vn/p"], "ABC123", lambda: sess, registry_path=reg)
    assert res.files
    assert "moi?Code={ma}" in load_registry(reg)[-1].tai["xml"]
```

- [ ] **Step 6: Khởi tạo `config/ncc-registry.yaml`**

```yaml
# Sổ công thức tải theo nhà cung cấp. Tool tự ghi sau khi dò thành công; sửa tay được.
# Cổng phức tạp (CSRF + POST + zip) dùng adapter code sẵn có qua `dung_adapter`.
- ten: einvoice.com.vn
  nhan_dien: [einvoice.com.vn]
  dung_adapter: einvoice_com_vn
- ten: VNPT
  nhan_dien: [vnpt-invoice.com.vn]
  dung_adapter: vnpt_invoice
  phai_do_lai: true          # link ký theo phiên -> không template hóa được
- ten: Fast e-Invoice
  nhan_dien: [einvoice.fast.com.vn]
  dung_adapter: fast_einvoice
  phai_do_lai: true
```

- [ ] **Step 7: Chạy full test**

```bash
make test
```
Expected: PASS

- [ ] **Step 8: Sửa dòng lệch trong spec rồi commit**

```bash
git add src/hdtool/ncc.py src/hdtool/adapters/registry_adapter.py \
        src/hdtool/portal_probe.py config/ncc-registry.yaml \
        tests/test_ncc.py tests/test_registry_adapter.py \
        docs/superpowers/specs/2026-08-25-tu-dong-tra-cuu-tai-hoa-don.md
git commit -m "feat: registry công thức tải + tự học sau khi dò (T42)"
```

---

## Task 8: Lệnh `hdtool ncc` + mục trong menu (T43)

**Files:**
- Modify: `src/hdtool/cli.py` (thêm subparser `ncc` + `cmd_ncc`)
- Modify: `src/hdtool/interactive.py` (thêm mục menu)
- Test: `tests/test_cli.py`, `tests/test_interactive.py`

**Interfaces:**
- Consumes: `ncc.load_registry`, `worklist.load/upsert`, `portal_probe.fetch_link_only`
- Produces: `cmd_ncc(settings, args) -> int`; CLI `hdtool ncc [--tai]`

- [ ] **Step 1: Viết test đỏ**

```python
def test_cmd_ncc_liet_ke_cong_thuc_va_dong_dang_cho(tmp_path, capsys, monkeypatch):
    reg = tmp_path / "ncc.yaml"
    save_registry(reg, [learn(MISA, "GJF211_PDLEP", ten="meinvoice.vn")])
    so = tmp_path / "so-hoa-don-cho-tai.csv"
    worklist.save(so, [WorkRow(message_id="m1", ncc="ehoadon.vn",
                               trang_thai="chưa có công thức", chan_doan="có captcha")])
    settings = _settings_gia(tmp_path)          # data_dir = tmp_path
    cmd_ncc(settings, _args(tai=False))
    out = capsys.readouterr().out
    assert "meinvoice.vn" in out                # NCC đã có công thức
    assert "ehoadon.vn" in out and "có captcha" in out   # dòng đang chờ + lý do


def test_cmd_ncc_tai_dung_ma_nguoi_dung_dien_tay(tmp_path, monkeypatch):
    """Người dùng gõ mã vào sổ -> `hdtool ncc --tai` phải dùng đúng mã đó."""
    so = tmp_path / "so-hoa-don-cho-tai.csv"
    worklist.save(so, [WorkRow(message_id="m1", link_tra_cuu="https://x.vn/p",
                               ma_tra_cuu="ABC123", trang_thai="thiếu mã")])
    goi = {}
    monkeypatch.setattr("hdtool.cli.portal_probe.fetch_link_only",
                        lambda links, ma=None, **kw: goi.setdefault("ma", ma) or ProbeResult())
    cmd_ncc(_settings_gia(tmp_path), _args(tai=True))
    assert goi["ma"] == "ABC123"
```

- [ ] **Step 2: Chạy để chắc chắn FAIL**

```bash
./.venv/bin/python -m pytest tests/test_cli.py -k ncc -v
```
Expected: FAIL — `ImportError: cannot import name 'cmd_ncc'`

- [ ] **Step 3: Viết `cmd_ncc` trong `cli.py`**

```python
def cmd_ncc(settings: Settings, args) -> int:
    """Xem sổ NCC + sổ hóa đơn chỉ-link; `--tai` thử tải lại các dòng đang chờ."""
    from types import SimpleNamespace

    from . import ncc, portal_probe, worklist
    from .collect import invoice_dir, save_invoice_files

    reg_path = Path("config") / "ncc-registry.yaml"
    so_path = settings.data_dir / "so-hoa-don-cho-tai.csv"
    entries = ncc.load_registry(reg_path)
    rows = worklist.load(so_path)

    print("== NCC ĐÃ CÓ CÁCH TẢI ==")
    for e in entries:
        cach = "công thức" if e.tai else (f"adapter {e.dung_adapter}" if e.dung_adapter else "phải dò lại")
        print(f"  {e.ten:28s} {cach}")

    cho = [r for r in rows.values() if r.trang_thai != "đã tải"]
    print(f"\n== ĐANG CHỜ: {len(cho)} hóa đơn ==")
    for r in cho:
        print(f"  {r.ncc:24s} | {r.trang_thai:20s} | {r.chan_doan}")

    if not getattr(args, "tai", False):
        return 0

    cap_nhat = []
    for r in cho:
        if not r.link_tra_cuu:
            continue
        res = portal_probe.fetch_link_only([r.link_tra_cuu], r.ma_tra_cuu or None,
                                           registry_path=reg_path)
        if res.files:
            # _peek_company_date đọc candidate.internal_date (cli.py:232) -> cần shim
            shim = SimpleNamespace(internal_date=None)
            company, ngay = _peek_company_date(res.files, shim, settings)
            saved = save_invoice_files(res.files,
                                       invoice_dir(settings.data_dir, company, ngay,
                                                   _extract_email(r.nguoi_gui)))
            r.trang_thai, r.file, r.chan_doan = "đã tải", str(saved.get("xml") or ""), ""
            print(f"  ✓ {r.ncc} -> {r.file}")
        else:
            r.chan_doan = res.chan_doan
        cap_nhat.append(r)
    if cap_nhat:
        worklist.upsert(so_path, cap_nhat)
    return 0
```

Đăng ký subparser cạnh các lệnh hiện có:

```python
    p_ncc = sub.add_parser("ncc", help="Xem/nạp cách tải hóa đơn chỉ-link theo NCC")
    p_ncc.add_argument("--tai", action="store_true", help="Thử tải lại các dòng đang chờ")
    p_ncc.set_defaults(func=cmd_ncc)
```

- [ ] **Step 4: Nối vào menu tương tác — KHÔNG hỏi thêm câu nào**

Người dùng muốn "tool chạy auto hết", nên menu không mọc thêm câu hỏi: sau khi
`collect` xong, tự thử tải nốt các dòng đang chờ rồi mới tổng hợp. Sửa
`_default_execute` trong `src/hdtool/interactive.py:88`:

```python
    out(f"\n→ Kết nối hộp thư (chỉ đọc), tải hóa đơn {ch.from_date} … {ch.to_date}")
    rc = cli.cmd_collect(settings, args)
    if rc != 0:
        return rc
    out("→ Thử tải nốt hóa đơn chỉ có link tra cứu…")
    cli.cmd_ncc(settings, SimpleNamespace(tai=True))   # lỗi cổng không chặn bảng kê
    out(f"→ Tổng hợp cho công ty '{ch.company}', xuất {ch.fmt.upper()}…")
    return cli.cmd_report(settings, args)
```

Test hiện có tiêm `execute` nên không gãy. Thêm một test khóa hành vi mới:

```python
def test_menu_thu_tai_hd_chi_link_truoc_khi_tong_hop(monkeypatch):
    """Menu phải gọi cmd_ncc(tai=True) giữa collect và report."""
    thu_tu = []
    monkeypatch.setattr("hdtool.cli.cmd_collect", lambda s, a: thu_tu.append("collect") or 0)
    monkeypatch.setattr("hdtool.cli.cmd_ncc", lambda s, a: thu_tu.append(f"ncc:{a.tai}") or 0)
    monkeypatch.setattr("hdtool.cli.cmd_report", lambda s, a: thu_tu.append("report") or 0)
    ch = Choices(from_date=date(2026, 6, 1), to_date=date(2026, 6, 30),
                 company="miyano", fmt="csv")
    _default_execute(_settings_gia(), ch, "/tmp/x.csv", lambda *_: None)
    assert thu_tu == ["collect", "ncc:True", "report"]
```

- [ ] **Step 5: Chạy full test**

```bash
make test
./.venv/bin/hdtool ncc
```
Expected: test xanh; lệnh in ra hai bảng.

- [ ] **Step 6: Commit**

```bash
git add src/hdtool/cli.py src/hdtool/interactive.py tests/test_cli.py tests/test_interactive.py
git commit -m "feat: lệnh hdtool ncc — xem sổ NCC và tải lại HĐ đang chờ (T43)"
```

---

## Task 9: Chạy thật, đo kết quả, cập nhật tài liệu (T45)

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `src/hdtool/adapters/README.md`, `tasks/plan.md`, `docs/hdtool-tong-quan.md`
- Create: thêm fixture vào `tests/fixtures/portals/`

**Interfaces:**
- Consumes: toàn bộ Task 1–8
- Produces: số liệu kiểm chứng Success Criteria của spec

- [ ] **Step 1: Chạy thật**

```bash
./.venv/bin/hdtool collect --from 2026-06-01 --to 2026-06-30 --include-suspect
./.venv/bin/hdtool ncc
```

- [ ] **Step 2: Đo và đối chiếu Success Criteria**

```bash
./.venv/bin/python - <<'PY'
import csv, collections
rows = list(csv.DictReader(open("data/so-hoa-don-cho-tai.csv", encoding="utf-8-sig")))
c = collections.Counter(r["Trạng thái"] for r in rows)
print("Tổng dòng:", len(rows))
for k, v in c.most_common():
    print(f"  {v:4d}  {k}")
thieu = [r for r in rows if r["Trạng thái"] != "đã tải" and not r["Chẩn đoán"].strip()]
print("Dòng chưa tải mà THIẾU chẩn đoán (phải = 0):", len(thieu))
PY
```

Expected: dòng thiếu chẩn đoán **= 0** (Success Criteria #1).

- [ ] **Step 3: Kiểm chứng đi tắt (Success Criteria #2)**

Chạy `collect` lần hai trên cùng kỳ và xác nhận NCC đã học không GET lại trang tra cứu (số request giảm) — quan sát qua log in ra của `cmd_collect`.

- [ ] **Step 4: Kiểm chứng không có rác trong `data/` (Success Criteria #3)**

```bash
./.venv/bin/python - <<'PY'
from pathlib import Path
from hdtool.parse_xml import parse_invoice_xml, InvoiceParseError
xau = []
for p in Path("data").rglob("*.xml"):
    try:
        parse_invoice_xml(p.read_bytes())
    except InvoiceParseError as exc:
        xau.append((p, exc))
print("XML không parse được:", len(xau))
for p, exc in xau[:20]:
    print(" ", p, exc)
PY
```

Chỉ được còn các bản forward hỏng 37 byte đã biết — **không có file mới nào** do quy trình dò tạo ra.

- [ ] **Step 5: Biến HTML thu được thành fixture hồi quy**

Chép các trang mới trong `data/_chan-doan/` vào `tests/fixtures/portals/`, rút gọn, thêm ca vào `test_classify_fixture_that_khop_ket_qua_khao_sat`.

- [ ] **Step 6: Cập nhật tài liệu**

- `README.md`: thêm mục "Hóa đơn chỉ có link tra cứu" mô tả quy trình dò + sổ CSV + lệnh `hdtool ncc`; sửa phần "Giới hạn hiện tại" cho khớp.
- `CLAUDE.md`: cập nhật khối cấu trúc `src/hdtool/` (4 module mới) và đoạn "Bối cảnh quan trọng" về adapter.
- `src/hdtool/adapters/README.md`: ghi rõ registry là nơi khai chính, adapter code chỉ cho cổng phức tạp.
- `tasks/plan.md`: đánh dấu T37–T45 xong, kèm số đo thật.
- `docs/hdtool-tong-quan.md`: cập nhật §6 (số liệu), §7 (bảng cổng), §9 (trạng thái Đợt 7).

- [ ] **Step 7: Commit**

```bash
make test
git add -A
git commit -m "docs: Đợt 7 chạy thật — dò cổng tự động + sổ chỉ-link (T45)"
```

---

## Ngoài phạm vi kế hoạch này

- **T46 — nhánh trình duyệt** cho cổng SPA/captcha (meinvoice, easyinvoice, ehoadon): spec riêng, sau khi Task 9 cho biết còn lại bao nhiêu hóa đơn thuộc nhóm này.
- **Nhập tay có dấu vết** cho hóa đơn không có trong mail (Grab, ĐÔI CÁNH, MEGA).
- **Cài `tesseract`** để bật lại test OCR end-to-end đang skip.
