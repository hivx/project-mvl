#!/usr/bin/env python3
"""Chạy hdtool ở chế độ TƯƠNG TÁC.

    python run.py

Tool sẽ hỏi ngay trên màn hình:
  • Từ ngày … đến ngày … (Enter để dùng kỳ mặc định trong config/settings.yaml)
  • Công ty nhận hóa đơn: miyano hay medcons
  • Xuất Excel (.xlsx) hay CSV

Rồi tự kết nối hộp thư (CHỈ ĐỌC), tải hóa đơn trong kỳ và xuất bảng kê cho công
ty đã chọn. Ngày ở đây là NGÀY LẬP HÓA ĐƠN (NLap).

(Tương đương: chạy `hdtool` không kèm lệnh. Muốn dùng dòng lệnh thì xem
`hdtool --help`: scan / collect / report / run / reorganize.)
"""
from hdtool.cli import main

if __name__ == "__main__":
    raise SystemExit(main([]))
