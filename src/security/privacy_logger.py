# -*- coding: utf-8 -*-
"""
CSHSP Privacy Logger — Sprint G
로그·감사기록에 개인정보 원문이 남지 않도록 마스킹한다.

마스킹 대상:
- 휴대폰 번호 (010-1234-5678 → 010-****-5678)
- 주민등록번호 형태 (******-*******)
- 이메일 (앞 2자만 노출)

날짜(YYYY-MM-DD)는 예약일자와 구분이 불가능해 마스킹하지 않는다 —
생년월일은 애초에 로그에 넣지 않는 것을 원칙으로 한다 (저장 최소화).
"""
from __future__ import annotations

import logging
import re

_PHONE_RE = re.compile(r"(01[016789])[-.\s]?\d{3,4}[-.\s]?(\d{4})")
_RRN_RE = re.compile(r"\b\d{6}[-\s]?\d{7}\b")
_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]{1,2})[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def mask_pii(text: str) -> str:
    """문자열 내 개인정보를 마스킹한 사본 반환."""
    t = str(text or "")
    t = _PHONE_RE.sub(r"\1-****-\2", t)
    t = _RRN_RE.sub("******-*******", t)
    t = _EMAIL_RE.sub(r"\1***@\2", t)
    return t


class PiiMaskingFilter(logging.Filter):
    """logging 필터 — 메시지/인자에 마스킹 적용."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_pii(str(record.msg))
        if record.args:
            record.args = tuple(mask_pii(str(a)) for a in record.args)
        return True


def get_masked_logger(name: str = "cshsp") -> logging.Logger:
    """PII 마스킹 필터가 적용된 로거 반환."""
    logger = logging.getLogger(name)
    if not any(isinstance(f, PiiMaskingFilter) for f in logger.filters):
        logger.addFilter(PiiMaskingFilter())
    return logger
