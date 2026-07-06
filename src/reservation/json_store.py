# -*- coding: utf-8 -*-
"""
CSHSP JSON Store — Sprint B
Sprint A 엔벨로프({entity, schemaVersion, meta, records}) 구조를 보존하는
읽기/쓰기 헬퍼. 모든 파일 입출력은 UTF-8.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))


def now_iso() -> str:
    """KST 기준 ISO 8601 타임스탬프 (초 단위)"""
    return datetime.now(KST).isoformat(timespec="seconds")


def today_ymd() -> str:
    """KST 기준 YYYYMMDD"""
    return datetime.now(KST).strftime("%Y%m%d")


def read_doc(path: Path | str) -> dict[str, Any]:
    """엔벨로프 문서 읽기. 파일 없음/빈 파일이면 {'records': []} 반환."""
    path = Path(path)
    if not path.exists():
        return {"records": []}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"records": []}
    doc = json.loads(raw)
    if isinstance(doc, list):  # 순수 배열 형식 호환
        return {"records": doc}
    doc.setdefault("records", [])
    return doc


def write_doc(path: Path | str, doc: dict[str, Any]) -> None:
    """엔벨로프 보존 저장. lastModifiedAt 자동 갱신, UTF-8, 한글 원문 유지."""
    doc["lastModifiedAt"] = now_iso()
    Path(path).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def next_seq(records: list[dict[str, Any]], pattern: str) -> int:
    """records의 id/reservationNo 필드에서 pattern(그룹1=순번)의 최대 순번 + 1"""
    rx = re.compile(pattern)
    mx = 0
    for rec in records:
        for field in ("id", "reservationNo"):
            m = rx.match(str(rec.get(field) or ""))
            if m:
                mx = max(mx, int(m.group(1)))
    return mx + 1
