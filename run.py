#!/usr/bin/env python3
"""Chạy nhanh tool tổng hợp hóa đơn.

Cách dùng: sửa TỪ_NGÀY / ĐẾN_NGÀY bên dưới rồi chạy:

    python run.py

(Tương đương lệnh CLI: hdtool run --from <từ> --to <đến> -o <file>)
Ngày ở đây là NGÀY LẬP HÓA ĐƠN (NLap). Tool tự quét rộng ngày email rồi lọc lại.
"""
from hdtool.cli import main

# ======================= CHỈNH Ở ĐÂY =======================
# Để trống "" nếu muốn dùng kỳ mặc định trong config/settings.yaml.
TU_NGAY  = "2026-06-01"   # từ ngày (YYYY-MM-DD)
DEN_NGAY = "2026-06-30"   # đến ngày (YYYY-MM-DD)
TAI_CA_NGHI_NGO = True    # True: tải cả email rổ "nghi ngờ"; False: chỉ "chắc chắn"
FILE_EXCEL = "bang-ke.xlsx"
# ===========================================================

if __name__ == "__main__":
    argv = ["run"]
    if TU_NGAY:
        argv += ["--from", TU_NGAY]
    if DEN_NGAY:
        argv += ["--to", DEN_NGAY]
    argv += ["-o", FILE_EXCEL]
    if TAI_CA_NGHI_NGO:
        argv.append("--include-suspect")
    raise SystemExit(main(argv))
