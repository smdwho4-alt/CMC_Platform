# -*- coding: utf-8 -*-
"""
CSHSP Safety Guard — Sprint E
AI Concierge의 안전 차단 계층. 모든 사용자 입력은 에이전트 처리 전에 이 모듈을 통과한다.

차단 원칙 (플랫폼 원칙 7):
- 진단 요청 차단 (DIAGNOSIS)
- 처방/약 상담 차단 (PRESCRIPTION)
- 검사결과 해석 차단 (RESULT_INTERPRETATION)
- 응급 의심 표현은 즉시 119/응급실 안내 (EMERGENCY)
- "즉시 확정" 요청은 차단이 아니라 절차 안내로 전환 (CONFIRM_REDIRECT)
"""
from __future__ import annotations

import re

# 예약 확정 고정 안내 문구 — 모든 예약 신청 응답에 반드시 포함 (원칙: AI는 확정하지 않는다)
STAFF_CONFIRM_NOTICE = (
    "※ 예약은 아직 확정되지 않았습니다. 검진센터 직원 확인(승인) 후 확정되며, "
    "확정되면 카카오/문자 알림으로 안내드립니다. (문의 041-570-7333)"
)

MEDICAL_REFERRAL_NOTICE = (
    "해당 내용은 의료 판단이 필요한 사항이라 AI 예약비서가 안내드릴 수 없습니다. "
    "의료진 상담이 필요합니다. 검진센터(041-570-7333)로 연결해 드리거나 상담 접수를 도와드릴까요?"
)

EMERGENCY_NOTICE = (
    "응급 상황이 의심됩니다. 즉시 119 또는 가까운 응급실을 이용해 주세요. "
    "AI 예약비서는 응급 대응을 할 수 없습니다."
)

_RULES: list[tuple[str, list[re.Pattern]]] = [
    ("EMERGENCY", [
        re.compile(r"(가슴이?\s*(아파|아프|답답)|호흡\s*곤란|숨이?\s*(안|못)\s*쉬|의식이?\s*없|피를?\s*토|쓰러졌)"),
    ]),
    ("DIAGNOSIS", [
        re.compile(r"(암|종양|폐렴|당뇨|고혈압|디스크)\s*(인가요|일까요|입니까|같나요|맞나요|아닐까요)"),
        re.compile(r"(무슨|어떤)\s*(병|질환|질병)"),
        re.compile(r"(진단(해|을|서)|병명|아픈\s*(이유|원인))"),
        re.compile(r"증상.{0,12}(심각|위험|괜찮)"),
    ]),
    ("PRESCRIPTION", [
        re.compile(r"(약|처방)\s*(을|좀|추천|주세요|바꿔|끊어)"),
        re.compile(r"(복용|투약).{0,10}(해도|괜찮|중단|바꾸)"),
        re.compile(r"처방전"),
    ]),
    ("RESULT_INTERPRETATION", [
        re.compile(r"(결과|수치|판정|소견).{0,15}(해석|설명|의미|무슨\s*뜻|정상|이상|나쁜|괜찮)"),
        re.compile(r"(혈당|콜레스테롤|간수치|혈압)\s*(이|가)?\s*\d+"),
        re.compile(r"재검.{0,10}(왜|이유|심각)"),
    ]),
]

_INJECTION_PATTERNS = [
    re.compile(r"(이전|위|기존)\s*(지시|명령|규칙|프롬프트).{0,8}(무시|잊어|버려)"),
    re.compile(r"시스템\s*프롬프트.{0,10}(보여|알려|출력|공개)"),
    re.compile(r"(너의|네)\s*(규칙|지침|설정).{0,10}(무시|바꿔|공개)"),
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"(reveal|show|print)\s+(your\s+)?(system\s+prompt|instructions)", re.IGNORECASE),
    re.compile(r"(관리자|직원|의사)\s*(모드|권한)(으로|로)\s*(전환|변경|동작)"),
]

INJECTION_NOTICE = (
    "요청하신 방식으로는 도와드릴 수 없습니다. 저는 천안의료원 건강검진센터 예약·안내 업무만 수행하며, "
    "내부 지침 변경·공개 요청은 처리하지 않습니다. 검진 관련 문의를 도와드릴까요?"
)

_CONFIRM_PATTERNS = [
    re.compile(r"(바로|즉시|지금|당장)\s*확정"),
    re.compile(r"확정(해줘|해\s*주세요|시켜)"),
    re.compile(r"승인.{0,6}(해줘|해\s*주세요|처리)"),
]


def check(text: str) -> dict:
    """입력 텍스트 안전 검사.

    반환: {"allowed": bool, "category": str|None, "message": str|None}
      - allowed=False → 에이전트는 message만 응답하고 도구 호출 금지
      - category=CONFIRM_REDIRECT → 처리는 계속하되 절차 안내 필수
    """
    t = str(text or "")
    for p in _INJECTION_PATTERNS:  # Sprint G: 프롬프트 인젝션 기본 차단
        if p.search(t):
            return {"allowed": False, "category": "PROMPT_INJECTION", "message": INJECTION_NOTICE}
    for category, patterns in _RULES:
        for p in patterns:
            if p.search(t):
                msg = EMERGENCY_NOTICE if category == "EMERGENCY" else MEDICAL_REFERRAL_NOTICE
                return {"allowed": False, "category": category, "message": msg}
    for p in _CONFIRM_PATTERNS:
        if p.search(t):
            return {"allowed": True, "category": "CONFIRM_REDIRECT",
                    "message": "예약 즉시 확정은 불가능합니다. " + STAFF_CONFIRM_NOTICE}
    return {"allowed": True, "category": None, "message": None}


def ensure_staff_notice(message: str) -> str:
    """예약 신청 관련 응답에 고정 안내 문구를 보장한다."""
    return message if STAFF_CONFIRM_NOTICE in message else f"{message}\n\n{STAFF_CONFIRM_NOTICE}"
