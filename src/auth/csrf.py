# -*- coding: utf-8 -*-
"""
CSHSP Admin Authentication — CSRF 방어 (Sprint8 Commit8-2)

세션과 연계된 CSRF Token을 헤더로 검증한다(Double Submit이 아니라 서버 세션에
저장된 값과의 대조 — 세션 저장소 자체가 이미 서버 관리형이므로 이 방식이 더
안전하다). JSON API 특성상 Header(`X-CSRF-Token`) 방식을 사용하고 Query
String으로는 절대 전달하지 않는다(PM 승인사항).
"""
from __future__ import annotations

import hmac


CSRF_HEADER_NAME = "X-CSRF-Token"


def csrf_token_matches(expected: str, provided: str | None) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(expected, provided)
