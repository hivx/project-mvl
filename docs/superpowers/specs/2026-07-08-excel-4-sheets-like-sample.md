# Spec — Xuất Excel 4 sheet giống file mẫu

Ngày: 2026-07-08. Nguồn: file mẫu người dùng cung cấp
`docs/MVL 6.26_tai-hoa-don_muaVao_01-06-2026_30-06-2026.xlsx`.
Yêu cầu: **file Excel xuất ra khớp cấu trúc file mẫu** (đủ 4 sheet, cấp dòng SP).

## Nguyên tắc
- Số liệu chỉ từ XML. Cột nào XML không có (KQ kiểm tra TCT, link/mã tra cứu,
  hình thức TT, ngày ký) → để trống / gần đúng, KHÔNG bịa số.
- Dòng chiết khấu (`TChat=3`) → thành tiền & tiền thuế hiển thị **số âm** (như mẫu).
- Tiền thuế mỗi dòng = `round(thành_tiền × thuế_suất)` (ROUND_HALF_UP); KCT/0%→0.
- HĐ không có dòng SP chi tiết → mỗi dòng thuế suất (`LTSuat`) thành 1 dòng SP
  tổng hợp (tên hàng trống, SL=1, đơn giá=0). Không có cả LTSuat → 1 dòng từ tổng.

## Model mới (`models.py`)
- `ProductLine`: tinh_chat (mã TChat), ma_hang, ten_hang, dvt, so_luong, don_gia,
  thanh_tien, thue_suat. Thuộc `Invoice.product_lines`.
- `Invoice` thêm: dia_chi_ban, dia_chi_mua, ngay_ky, ty_gia, tong_cktm, tong_phi,
  hinh_thuc_tt, ma_tra_cuu (đều có default để không phá code cũ).

## Parser (`parse_xml.py`)
- Địa chỉ: `NBan/DChi`, `NMua/DChi`. Tỷ giá: `TTChung/TGia` (mặc định 1).
- CKTM: `TToan/TTCKTMai`. Phí: tổng `TToan//TPhi` (mặc định 0).
- Ngày ký: `TTChung//NKy`/`SigningTime` nếu có, else = ngày lập.
- Mã tra cứu: `TTChung//MHDon` nếu có.
- Dòng SP: `NDHDon//DSHHDVu//HHDVu` → TChat, MHHDVu, THHDVu, DVTinh, SLuong,
  DGia, ThTien, TSuat.

## Nhãn TÍNH CHẤT (TChat)
1→"Hàng hóa, dịch vụ" · 2→"Khuyến mại" · 3→"Chiết khấu thương mại" ·
4→"Ghi chú/diễn giải" · 5→"Hàng hoá đặc trưng" · khác→giữ mã.

## Loại hóa đơn (cột "LOẠI HÓA ĐƠN")
Ký tự thứ 3 của ký hiệu = `M` → "HĐ từ máy tính tiền", ngược lại "HĐ điện tử".

## 4 sheet (khớp cột mẫu)

### 1) "Hoa don Chi tiet SP" (A–AD, 30 cột) — 1 dòng/SP, header HĐ ở dòng đầu mỗi HĐ
A STT(theo HĐ, chỉ dòng đầu) B MẪU SỐ C KÝ HIỆU D SỐ E NGÀY LẬP F MST BÁN
G TÊN BÁN H ĐỊA CHỈ BÁN I MST MUA J TÊN MUA K ĐỊA CHỈ MUA L TỔNG CHƯA THUẾ
M TỔNG THUẾ N TỔNG CKTM O TỔNG PHÍ P TỔNG TT Q ĐVT TỆ R TỶ GIÁ S TRẠNG THÁI
T KQ KIỂM TRA(trống) U HĐ LIÊN QUAN V TÍNH CHẤT W MÃ HÀNG X TÊN HÀNG Y ĐVT
Z SỐ LƯỢNG AA ĐƠN GIÁ AB THUẾ SUẤT AC THÀNH TIỀN AD TIỀN THUẾ

### 2) "BK mua vao TT80" (A–O, 15 cột) — 1 dòng/SP, STT chạy theo dòng
A STT B Mẫu số C Ký hiệu D Số E Ngày F Tên bán G MST bán H Tên hàng I ĐVT
J Số lượng K Đơn giá L Giá trị chưa thuế M Thuế suất N Tiền thuế O Ghi chú

### 3) "DS hoa don" (A–AA, 27 cột) — 1 dòng/HĐ
A LOẠI HĐ B STT C MẪU SỐ D KÝ HIỆU E SỐ F NGÀY LẬP G NGÀY KÝ H MST BÁN
I TÊN BÁN J ĐỊA CHỈ BÁN K MST MUA L TÊN MUA M ĐỊA CHỈ MUA N TỔNG CHƯA THUẾ
O TỔNG THUẾ P TỔNG CKTM Q TỔNG PHÍ R TỔNG TT S TIỀN TỆ T TỶ GIÁ U TRẠNG THÁI
V KQ KIỂM TRA(trống) W HÌNH THỨC TT X LINK TRA CỨU(trống) Y MÃ TRA CỨU
Z CÓ XML("x") AA HĐ LIÊN QUAN

### 4) "DS san pham" (A–Z, 26 cột) — 1 dòng/SP, STT theo dòng
A STT B MẪU SỐ C KÝ HIỆU D SỐ E NGÀY LẬP F MST BÁN G TÊN BÁN H ĐỊA CHỈ BÁN
I MST MUA J TÊN MUA K ĐỊA CHỈ MUA L ĐVT TỆ M TỶ GIÁ N TRẠNG THÁI O KQ KIỂM TRA(trống)
P TÍNH CHẤT Q MÃ HÀNG R LOẠI HÀNG ĐẶC TRƯNG(trống) S TÊN HÀNG T ĐVT U SỐ LƯỢNG
V ĐƠN GIÁ W THUẾ SUẤT X THÀNH TIỀN Y TIỀN THUẾ Z THÔNG TIN KHÁC(trống)

## Tích hợp
- `write_workbook` xuất 4 sheet trên + GIỮ "Bỏ qua" và "Cần nhập tay" (hữu ích,
  không có trong mẫu). Bỏ 2 sheet cũ "Bảng kê"/"Tổng hợp" (được 4 sheet mới thay).
- Tiêu đề mỗi sheet + dòng "Từ ngày dd/mm/yyyy đến ngày dd/mm/yyyy": cần truyền
  kỳ (from/to) xuống writer.
- CSV: bảng kê chính đổi sang đúng cột **BK mua vao TT80**; vẫn kèm bo-qua.
- Ngày hiển thị: cột ngày là kiểu date (Excel), định dạng dd/mm/yyyy.

## Ngoài phạm vi
- Không tra cứu cổng TCT để điền KQ kiểm tra/link. Không đổi luồng IMAP/collect.
