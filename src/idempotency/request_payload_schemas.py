# -*- coding: utf-8 -*-
"""
Commit8-3b payload 정규화 계약 — 요청별 스키마 가드(Option B 2단계)

`src/idempotency/payload_schema_guard.py`(공통 타입 가드: ASCII-only
object key, 정수·문자열·bool·null 등 "형식"만 검사)와는 **역할이
분리된 별도 계층**이다. ASCII 키라는 이유만으로 임의의 필드를 허용하지
않는다 — 이 모듈은 **operation별로 등록된 필드 집합·필수 여부·타입·
null 허용 여부**까지 검사한다. 공통 타입 가드를 통과했더라도 이
모듈이 모르는 필드가 있으면 거절한다.

## 조사 근거(제안서 §1 재확인, 2026-10-03 기준 실제 Pydantic 모델)
아래 각 스키마의 `source`는 정확한 파일:라인을 가리킨다 — 추측이
아니라 실제 코드를 읽고 옮긴 것이다. **실제 모델이 명시하지 않은
범위(최소/최대값, 허용 enum 등)는 이 구현이 임의로 만들지 않는다.**
예: `SlotGenerateBody.capacity`는 평범한 `int`이고 코드에
`Field(ge=.., le=..)` 같은 제약이 없으므로, 여기서도 "정수이고 공통
가드의 안전정수범위 내"라는 것 이상을 요구하지 않는다. 반대로
`RejectReservationBody.reason`은 실제 코드(`routes_admin_portal.py`의
`_validate_reason`)가 길이 2~200자를 **명시적으로 검증**하므로, 그
범위를 그대로 가져와 적용한다(발명이 아니라 재확인).

## 자유형 dict는 이번 서명 대상에서 제외
`ChatBody.context: dict[str, Any]`(`src/api/routes_agents.py:53`)와
`QSubmitBody.answers: list[dict[str, Any]]`(같은 파일:66)는 **이
레지스트리에 등록하지 않는다** — 세션 인증 기반 AI 채팅/문진 기능이며
ADR-017 HMAC 서명 프록시(관리자 GAS 쓰기) 대상이 아니다(제안서 §1
핵심 발견 재확인).

## 미등록 operation의 취급
`validate_request_schema()`는 레지스트리에 없는 `operation`을
`UNKNOWN_OPERATION`으로 **거절**한다 — "모르는 operation은 일단
통과시킨다"가 아니라 명시적 allow-list 원칙을 Option B 공통 가드와
동일하게 적용한다. 새 operation을 서명 대상에 추가하려면 반드시 이
레지스트리에 스키마를 먼저 등록해야 한다.

## 운영 미배선
이 모듈은 운영 라우트에 배선되지 않았다. 실제 Pydantic
`BaseModel`(FastAPI 자체 검증)과는 독립적으로 존재하는, HMAC 서명
전 단계의 **별도 참고용 재검증 계층**이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool
    python_types: Tuple[type, ...]
    allows_null: bool = False
    min_len: Optional[int] = None  # 실제 모델에 명시된 경우만 설정(발명 금지)
    max_len: Optional[int] = None


@dataclass(frozen=True)
class RequestSchema:
    operation: str
    source: str
    fields: Tuple[FieldSpec, ...]


class RequestSchemaError(ValueError):
    """요청별 스키마 위반. `reason`은 내부 분류값(운영 오류코드 확정
    아님 — signing_v2.py/payload_schema_guard.py와 동일 원칙)."""

    def __init__(self, reason: str, field_name: Optional[str] = None, detail: str = ""):
        msg = reason + (f" (field: {field_name})" if field_name else "") + (f" {detail}" if detail else "")
        super().__init__(msg)
        self.reason = reason
        self.field = field_name


_SCHEMAS = {
    "reservation_create": RequestSchema(
        operation="reservation_create",
        source="src/api/api_server.py:75 ReservationCreate",
        fields=(
            FieldSpec("patientId", True, (str,)),
            FieldSpec("programId", True, (str,)),
            FieldSpec("requestedDate", True, (str,)),
            FieldSpec("requestedTime", True, (str,)),
            FieldSpec("slotId", True, (str,)),
            FieldSpec("channel", False, (str,)),
            FieldSpec("allowWaiting", False, (bool,)),
            FieldSpec("memo", False, (str,), allows_null=True),
        ),
    ),
    "reservation_cancel": RequestSchema(
        operation="reservation_cancel",
        source="src/api/api_server.py:86 ReasonBody",
        fields=(FieldSpec("reason", False, (str,)),),
    ),
    "reservation_change": RequestSchema(
        operation="reservation_change",
        source="src/api/api_server.py:90 ChangeBody",
        fields=(
            FieldSpec("newSlotId", True, (str,)),
            FieldSpec("newDate", True, (str,)),
            FieldSpec("newTime", True, (str,)),
            FieldSpec("reason", False, (str,)),
        ),
    ),
    "slot_generate": RequestSchema(
        operation="slot_generate",
        source="src/api/api_server.py:97 SlotGenerateBody",
        fields=(
            FieldSpec("startDate", True, (str,)),
            FieldSpec("endDate", True, (str,)),
            FieldSpec("roomId", False, (str,)),
            # capacity: 실제 모델에 범위 제약 없음(Field(ge=,le=) 미사용,
            # grep 확인) — 공통 가드의 안전정수범위 이상을 임의로 요구하지 않는다.
            FieldSpec("capacity", False, (int,)),
        ),
    ),
    "consultation_status_update": RequestSchema(
        operation="consultation_status_update",
        source="src/api/routes_admin_portal.py:112 ConsultationStatusBody",
        fields=(
            FieldSpec("status", True, (str,)),
            FieldSpec("handledBy", False, (str,), allows_null=True),
        ),
    ),
    "reservation_reject": RequestSchema(
        operation="reservation_reject",
        source="src/api/routes_admin_portal.py:126 RejectReservationBody",
        fields=(
            # 실제 코드(_validate_reason, routes_admin_portal.py:129-141)가
            # 길이 2~200자를 명시적으로 검증함 — 그 범위를 그대로 재확인.
            FieldSpec("reason", True, (str,), min_len=2, max_len=200),
        ),
    ),
    "questionnaire_review": RequestSchema(
        operation="questionnaire_review",
        source="src/api/api_server.py:119 QReviewBody",
        fields=(
            # decision: 코드 주석은 "REVIEWED | REJECTED"를 언급하지만
            # Literal/enum으로 강제되지 않는 평범한 str이다(실제 코드
            # 재확인) — 주석만 보고 enum 제약을 임의로 만들지 않는다.
            FieldSpec("decision", True, (str,)),
            FieldSpec("note", False, (str,)),
        ),
    ),
    "crm_notification": RequestSchema(
        operation="crm_notification",
        source="src/api/api_server.py:124 CrmNotificationBody",
        fields=(
            FieldSpec("patientId", True, (str,)),
            FieldSpec("reservationId", False, (str,), allows_null=True),
            FieldSpec("type", False, (str,)),
            FieldSpec("templateCode", False, (str,)),
            FieldSpec("content", True, (str,)),
            FieldSpec("crmCategory", False, (str,)),
            FieldSpec("crmSummary", False, (str,), allows_null=True),
        ),
    ),
}


def validate_request_schema(operation: str, payload: dict) -> None:
    """operation 이름으로 등록된 스키마를 조회해 payload를 검증한다.
    공통 타입 가드(`payload_schema_guard.validate_payload_schema_interim`)를
    이미 통과한 payload를 받는 것을 전제로 한다(타입 검사 일부는 이
    함수에서도 다시 하지만, ASCII-key·안전정수범위 등은 공통 가드의
    책임이다 — 두 레이어는 서로 대체하지 않는다)."""
    schema = _SCHEMAS.get(operation)
    if schema is None:
        raise RequestSchemaError("UNKNOWN_OPERATION", detail=f"operation={operation!r}")

    allowed_names = {f.name for f in schema.fields}
    for key in payload:
        if key not in allowed_names:
            raise RequestSchemaError("UNREGISTERED_FIELD", key, detail=f"(operation={operation})")

    for f in schema.fields:
        if f.name not in payload:
            if f.required:
                raise RequestSchemaError("REQUIRED_FIELD_MISSING", f.name, detail=f"(operation={operation})")
            continue

        value = payload[f.name]
        if value is None:
            if not f.allows_null:
                raise RequestSchemaError("NULL_NOT_ALLOWED", f.name)
            continue

        # bool은 int의 서브클래스이므로 반드시 먼저 분기해 구분한다
        # (payload_schema_guard.py와 동일 원칙 재사용).
        if isinstance(value, bool):
            if bool not in f.python_types:
                raise RequestSchemaError("FIELD_TYPE_MISMATCH", f.name)
            continue
        if not isinstance(value, f.python_types):
            raise RequestSchemaError("FIELD_TYPE_MISMATCH", f.name)

        if isinstance(value, str):
            if f.min_len is not None and len(value) < f.min_len:
                raise RequestSchemaError("FIELD_TOO_SHORT", f.name, detail=f"min={f.min_len}")
            if f.max_len is not None and len(value) > f.max_len:
                raise RequestSchemaError("FIELD_TOO_LONG", f.name, detail=f"max={f.max_len}")


def list_known_operations() -> Tuple[str, ...]:
    return tuple(sorted(_SCHEMAS))
