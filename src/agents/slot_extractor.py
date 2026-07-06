# -*- coding: utf-8 -*-
"""
CSHSP Slot Extractor — Sprint G
자연어에서 예약 슬롯(이름·전화번호·프로그램·희망일자·희망시간)을 추출한다.

- 규칙(정규식) 기반 초안 — LLM 연동 시 tool-use 기반 추출로 대체 가능한 동일 인터페이스
- 추출 실패 항목은 missing으로 반환 → 챗봇이 '필요한 정보만' 추가 질문
- 이름/전화번호는 본인확인 입력용으로만 사용하며 응답에 원문을 되돌려주지 않는다
"""
from __future__ import annotations

import re
from datetime import date, timedelta

PROGRAM_KEYWORDS = [
    (re.compile(r"(프리미엄|premium)", re.I), "PRG-PREMIUM"),
    (re.compile(r"(브이아이피|vip)", re.I), "PRG-VIP"),
    (re.compile(r"(스마트|smart)", re.I), "PRG-SMART"),
    (re.compile(r"(베이직|basic|기본\s*검진)", re.I), "PRG-BASIC"),
    (re.compile(r"(영\s*검진|young)", re.I), "PRG-YOUNG"),
    (re.compile(r"온\s*김에", re.I), "PRG-ONKIME"),
]

_PHONE_RE = re.compile(r"(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})")
_DATE_FULL_RE = re.compile(r"(\d{4})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})일?")
_DATE_MD_RE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")
_TIME_HM_RE = re.compile(r"(\d{1,2}):(\d{2})")
_TIME_KR_RE = re.compile(r"(오전|오후|아침|저녁)?\s*(\d{1,2})시\s*(반|(\d{1,2})분)?")
_NAME_RE = re.compile(r"(?:저는|이름은|성함은)\s*([가-힣]{2,4})(?:입니다|이고|이에요|예요|이며|임)?")

REQUIRED_FOR_RESERVATION = ["programId", "date", "time"]


def _extract_date(text: str, today: date) -> str | None:
    m = _DATE_FULL_RE.search(text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = _DATE_MD_RE.search(text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year if (month, day) >= (today.month, today.day) else today.year + 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    if "모레" in text:
        return (today + timedelta(days=2)).isoformat()
    if "내일" in text:
        return (today + timedelta(days=1)).isoformat()
    return None


def _extract_time(text: str) -> str | None:
    m = _TIME_HM_RE.search(text)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    m = _TIME_KR_RE.search(text)
    if m:
        ampm, hour = m.group(1), int(m.group(2))
        if ampm in ("오후", "저녁") and hour < 12:
            hour += 12
        minute = 30 if m.group(3) == "반" else int(m.group(4) or 0)
        return f"{hour:02d}:{minute:02d}"
    return None


def extract(text: str, today: date | None = None) -> dict:
    """자연어에서 예약 관련 슬롯 추출.

    반환: {"extracted": {name?, phone?, programId?, date?, time?},
           "missing": [예약에 필요한데 못 찾은 필드]}
    """
    text = str(text or "")
    today = today or date.today()
    out: dict[str, str] = {}

    m = _NAME_RE.search(text)
    if m:
        out["name"] = m.group(1)
    m = _PHONE_RE.search(text)
    if m:
        out["phone"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    for pattern, program_id in PROGRAM_KEYWORDS:
        if pattern.search(text):
            out["programId"] = program_id
            break
    d = _extract_date(text, today)
    if d:
        out["date"] = d
    t = _extract_time(text)
    if t:
        out["time"] = t

    missing = [f for f in REQUIRED_FOR_RESERVATION if f not in out]
    return {"extracted": out, "missing": missing}


FIELD_LABELS = {"programId": "검진 프로그램", "date": "희망 날짜", "time": "희망 시간",
                "name": "성함", "phone": "전화번호"}


def ask_for_missing(missing: list[str]) -> str:
    """부족한 정보만 골라 추가 질문 문구 생성."""
    labels = [FIELD_LABELS.get(f, f) for f in missing]
    return f"예약 신청을 위해 {', '.join(labels)}을(를) 알려주세요."
