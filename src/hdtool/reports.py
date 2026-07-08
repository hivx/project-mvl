"""Export the scan candidate/suspect list for human review.

The original requirement: the tool must always output the "nghi ngờ" list so a
person can check both false positives and false negatives. This writes it as a
CSV (UTF-8 BOM so Excel shows Vietnamese correctly).
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .models import EmailCandidate

CANDIDATE_HEADERS = [
    "Rổ", "Điểm", "Người gửi", "Tiêu đề", "Ngày email", "XML", "PDF", "Lý do",
    "Hộp thư",
]

MANUAL_LINK_HEADERS = [
    "Hộp thư", "Người gửi", "Tiêu đề", "Nhà phát hành", "Link tra cứu",
]


def write_candidates_csv(candidates: Iterable[EmailCandidate], path) -> Path:
    """Write certain+suspect candidates to a reviewable CSV; return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CANDIDATE_HEADERS)
        for c in candidates:
            writer.writerow([
                c.bucket,
                c.score,
                c.sender,
                c.subject,
                c.internal_date.isoformat() if c.internal_date else "",
                "x" if c.has_xml else "",
                "x" if c.has_pdf else "",
                "; ".join(c.reasons),
                c.account,
            ])
    return path


def _host(url: str) -> str:
    net = urlparse(url).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def _guess_issuer(sender: str, links: list) -> str:
    """Nhà phát hành để tải tay: ưu tiên host của link tra cứu, nếu không có link
    thì lấy domain của người gửi."""
    if links:
        h = _host(links[0])
        if h:
            return h
    m = re.search(r"@([\w.\-]+)", sender or "")
    return m.group(1).lower() if m else ""


def write_manual_links_csv(items, path) -> Path:
    """Ghi danh sách hóa đơn CHỈ-CÓ-LINK (cần tải tay qua cổng) ra CSV.

    ``items``: iterable các cặp (EmailCandidate, links: list[str]). Trả về đường
    dẫn. UTF-8 BOM để Excel đọc tiếng Việt đúng.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(MANUAL_LINK_HEADERS)
        for cand, links in items:
            writer.writerow([
                cand.account,
                cand.sender,
                cand.subject,
                _guess_issuer(cand.sender, links),
                links[0] if links else "",
            ])
    return path
