"""Export the scan candidate/suspect list for human review.

The original requirement: the tool must always output the "nghi ngờ" list so a
person can check both false positives and false negatives. This writes it as a
CSV (UTF-8 BOM so Excel shows Vietnamese correctly).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .models import EmailCandidate

CANDIDATE_HEADERS = [
    "Rổ", "Điểm", "Người gửi", "Tiêu đề", "Ngày email", "XML", "PDF", "Lý do",
    "Hộp thư",
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
