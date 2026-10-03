# -*- coding: utf-8 -*-
"""
Commit8-3b payload 정규화 계약 — Option B 개발용 입력 검증 가드

`docs/Commit8_3b_Payload_Normalization_Policy_Proposal.md` §3(권고안)·§4
(차단 방안 제안)을 구현한다. **`signing_v2.py`를 수정하지 않으며**,
`compute_payload_hash()`/`sign_v2()` 호출 **이전에** 호출부가 선택적으로
이 가드를 추가 호출하는 형태를 전제로 설계했다(제안서 §4 재확인). 이
모듈은 아직 어떤 운영 라우트에도 배선되지 않았고, 운영 정책으로
확정된 것도 아니다 — 격리 개발·로컬 전용이다.

## 지원 입력(제안서 §3 그대로 구현)
- object key: ASCII-only safe-token(`^[A-Za-z0-9_.\\-:]{1,200}$`,
  `signing_v2.py`의 필드 검증과 동일 패턴 재사용).
- value: `string`(NFC 정규화는 `compute_payload_hash()`가 별도로 수행 —
  이 가드의 책임이 아니며 트리밍도 하지 않음, V05 결과와 일관) / `boolean` /
  `null` / **정수**(10진 리터럴, 안전정수범위 내, `bool` 제외) / `list` /
  `dict`(재귀) — 전부 동일 규칙으로 재귀 적용.

## 거절 입력
- `float`(모든 비정수 숫자, `NaN`/`Infinity` 포함 — Python `float`
  타입이면 전부 이 분기에서 거절됨). **단, 이미 파싱된 Python 값만
  보는 `validate_payload_schema_interim()`은 "정수값을 가진 float
  리터럴"(`1.0` 등, 소수부가 0인 경우)이 처음부터 올 수 없다는
  보장이 없다** — 아래 "두 경로의 구분" 참조.
- 안전정수범위(`-9007199254740991`~`9007199254740991`, RFC 8785
  Appendix B 권고값 재사용) 밖의 정수.
- 비 ASCII(Unicode) object key.
- (raw JSON 경로, `parse_json_strict`/`parse_json_reject_duplicates`)
  원시 JSON 텍스트의 중복 object key — RFC 8785 §3.1 "JSON 객체는
  중복된 property name을 가져서는 안 된다(MUST NOT)" 요구사항 재확인.
- (raw JSON 경로, `parse_json_strict`만) 소수점·지수 표기가 있는 숫자
  리터럴(`1.0`, `1e0` 등) — 개발 계약상 payload 숫자는 정수 토큰
  `-?(0|[1-9][0-9]*)`만 허용한다. `-0`은 정수 `0`으로 정규화된다.
- Unicode 값(문자열) 자체는 거절하지 않는다 — 거절 대상은 **object
  key**뿐이다. 값에 한글·이모지 등 Unicode 문자열이 오는 것은 실제
  스키마에도 존재하므로(제안서 §1) 정상 지원 입력이다.

## 두 경로의 구분 — raw JSON 경로 vs 이미 파싱된 객체 경로
- **raw JSON 경로**(`parse_json_strict`): 입력이 **원시 텍스트**다.
  중복 키와 "숫자 리터럴에 소수점이 있었는가"를 **토큰 단위**로
  검사할 수 있다 — `1.0`과 `1`을 구분하는 유일한 지점.
- **이미 파싱된 객체 경로**(`validate_payload_schema_interim`): 입력이
  Python `dict`/`list`/... 등 **이미 파싱된 값**이다. 이 시점에는
  `1.0`과 `1`이 둘 다 원래 int였는지 float였는지와 무관하게 Python
  타입 체계상 서로 다른 타입(`int` vs `float`)으로는 남아 있지만,
  **"호출부가 raw JSON을 거치지 않고 Python 코드에서 직접
  `payload={"count": 1.0}`처럼 float 리터럴을 만들어 넘기는 경우"**까지
  막지는 못한다(그 경우는 Python 자체에서 `float` 타입이 이미 명확하므로
  이 함수가 `FLOAT_NOT_ALLOWED`로 정상 거절은 한다 — 다만 "원문에
  소수점이 있었는가"라는 *사실 확인*은 이 경로 혼자서는 할 수 없고,
  raw JSON 경로를 먼저 거쳤는지에 의존한다). **이 제한은 유지한다** —
  이 함수를 더 "영리하게" 고쳐서 해결할 수 있는 문제가 아니다.

## 이 가드가 보장하지 않는 것
- "통과 = ACCEPTED 보장"이 아니다. 통과하지 못한 입력이 서명 단계까지
  가지 않도록 막는 최소 방어선일 뿐이다(제안서 §4 재확인).
- 이 가드를 `compute_payload_hash()` 앞에 실제로 배선할지, 어느 계층에
  둘지는 ADR 개정 논의에서 결정할 사항이며, 이 모듈 자체가 그 배선을
  수행하지 않는다(운영 라우트 미연결, 운영 수신 계층 변경 없음 —
  `signing_v2_guarded.py`는 선택적 wrapper일 뿐 기존 수신 경로를
  바꾸지 않는다).
"""
from __future__ import annotations

import json
import re
from typing import Any

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\-:]{1,200}$")

# RFC 8785(JCS) Appendix B 권고값(2^53-1) 재사용 — 이 구현이 새로 만든 값이
# 아니다. 제안서 §2-1 "안전 정수 범위" 행 재확인.
SAFE_INTEGER_MIN = -9007199254740991
SAFE_INTEGER_MAX = 9007199254740991


class PayloadSchemaUnresolvedError(ValueError):
    """Option B 미지원 입력(미확정 정책 영역 또는 스키마 밖 타입)을 서명
    경로 진입 전에 차단하기 위한 예외. `reason`은 내부 분류값(운영
    오류코드 확정 아님, signing_v2.py의 "오류 분류는 내부용이다" 원칙과
    동일), `path`는 거절된 위치를 사람이 읽을 수 있는 형태로 기록한다
    (예: `"$.items[1].price"`)."""

    def __init__(self, reason: str, path: str):
        super().__init__(f"{reason} (경로: {path})")
        self.reason = reason
        self.path = path


def _check_key(key: Any, path: str) -> None:
    if not isinstance(key, str) or not _SAFE_TOKEN_RE.match(key):
        raise PayloadSchemaUnresolvedError("UNICODE_OR_INVALID_OBJECT_KEY", path)


def _check_value(value: Any, path: str) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        return  # bool은 int의 서브클래스이므로 반드시 int 분기보다 먼저 검사
    if isinstance(value, str):
        return
    if isinstance(value, int):
        if not (SAFE_INTEGER_MIN <= value <= SAFE_INTEGER_MAX):
            raise PayloadSchemaUnresolvedError("INTEGER_OUT_OF_SAFE_RANGE", path)
        return
    if isinstance(value, float):
        # NaN/Infinity도 Python float 타입이므로 이 분기에서 함께 거절된다.
        raise PayloadSchemaUnresolvedError("FLOAT_NOT_ALLOWED", path)
    if isinstance(value, list):
        for i, item in enumerate(value):
            _check_value(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        _validate_object(value, path)
        return
    raise PayloadSchemaUnresolvedError("UNSUPPORTED_TYPE", path)


def _validate_object(obj: dict, path: str) -> None:
    for key, value in obj.items():
        key_path = f"{path}.{key}" if isinstance(key, str) else f"{path}.<invalid-key>"
        _check_key(key, key_path)
        _check_value(value, key_path)


def validate_payload_schema_interim(payload: Any) -> None:
    """제안서 §4 의사코드의 실제 구현. 통과하면 반환값 없음(`None`),
    실패하면 `PayloadSchemaUnresolvedError`를 낸다. 최상위 `payload`는
    dict(JSON 객체)여야 한다(ADR-017 §12 "payload는 JSON 객체" 전제
    재확인) — 그 외 타입(list 등)이 최상위로 오면 거절한다."""
    if not isinstance(payload, dict):
        raise PayloadSchemaUnresolvedError("TOP_LEVEL_PAYLOAD_MUST_BE_OBJECT", "$")
    _validate_object(payload, "$")


class DuplicateKeyError(ValueError):
    """원시 JSON 텍스트에 중복 object key가 있을 때 발생한다(RFC 8785
    §3.1 "MUST NOT" 요구사항 재확인). 표준 `json.loads`는 이를
    강제하지 않으므로 `object_pairs_hook`으로 직접 탐지한다."""


def _reject_duplicates_pairs_hook(pairs):
    seen = set()
    result = {}
    for k, v in pairs:
        if k in seen:
            raise DuplicateKeyError(f"중복 object key: {k!r}")
        seen.add(k)
        result[k] = v
    return result


class RawNumberFormatError(ValueError):
    """원시 JSON 숫자 리터럴이 개발 계약(`-?(0|[1-9][0-9]*)`, 정수만
    허용)을 위반할 때 발생한다. `reason`은 `FLOAT_OR_EXPONENT_NOT_ALLOWED`
    또는 `INVALID_INTEGER_TOKEN`(선행 0 등, 이론상 Python 스캐너가 이
    형태로 `parse_int`를 호출할 일은 없지만 계약을 코드로도 명시하기
    위해 방어적으로 재검증한다)."""

    def __init__(self, reason: str, token: str):
        super().__init__(f"{reason}: {token!r}")
        self.reason = reason
        self.token = token


_INT_TOKEN_RE = re.compile(r"^-?(0|[1-9][0-9]*)$")


def _normalize_int_token(token: str) -> int:
    """`json.loads(..., parse_int=...)` 훅 — Python 스캐너는 소수점·지수
    부호가 없는 정수형 리터럴에 대해서만 이 함수를 호출한다. 개발
    계약(`-?(0|[1-9][0-9]*)`)을 명시적으로 재검증한 뒤 `int()`로
    변환한다 — `int("-0") == 0`이라 **-0은 자동으로 정수 0이 된다**
    (Python 쪽은 애초에 서명 있는 0을 구분하는 타입이 없어 별도 분기가
    필요 없다)."""
    if not _INT_TOKEN_RE.match(token):
        raise RawNumberFormatError("INVALID_INTEGER_TOKEN", token)
    return int(token)


def _reject_float_token(token: str) -> int:
    """`json.loads(..., parse_float=...)` 훅 — Python 스캐너는 소수점
    또는 `e`/`E` 지수 표기가 있는 숫자 리터럴에 대해 이 함수를
    호출한다. 개발 계약상 payload 숫자는 정수만 허용하므로 예외 없이
    거절한다(V04에서 실측 확인된 교차언어 모호성의 근본 원인 — 이
    훅은 "이미 파싱된 값"이 아니라 **원시 토큰 문자열**을 직접 보므로
    `1.0`과 `1`을 구분할 수 있다. 이것이 `validate_payload_schema_interim()`
    (이미 파싱된 객체 경로)로는 원천적으로 불가능했던 지점이다)."""
    raise RawNumberFormatError("FLOAT_OR_EXPONENT_NOT_ALLOWED", token)


def parse_json_strict(raw_json_text: str) -> Any:
    """**raw JSON 경로**의 유일한 진입점. 원시 JSON 텍스트를 파싱하며
    아래 두 가지를 토큰 단위로 검사한다(둘 다 "이미 파싱된 객체
    경로"(`validate_payload_schema_interim`)로는 복구 불가능한 정보라
    반드시 원시 텍스트 단계에서 처리해야 한다):

    1. **중복 object key 거절**(`object_pairs_hook`, 기존
       `parse_json_reject_duplicates`와 동일 로직) — 어느 중첩
       레벨에서든 중복되면 `DuplicateKeyError`.
    2. **숫자 토큰 형식 검증**(`parse_int`/`parse_float` 훅) — 정수
       토큰만 허용(`-?(0|[1-9][0-9]*)`), 소수점·지수표기(`1.0`, `1e0`
       등)는 `RawNumberFormatError("FLOAT_OR_EXPONENT_NOT_ALLOWED")`로
       즉시 거절. `-0`은 정수 `0`으로 정규화된다.

    이 함수가 성공적으로 반환한 결과(중복 키 없음 + 숫자는 전부 정수)만
    `validate_payload_schema_interim()`(안전정수범위 등 추가 검사)과
    `request_payload_schemas.validate_request_schema()`(요청별 필드
    검증)에 넘기는 것을 권장한다 — 세 단계는 역할이 분리되어 있으며
    어느 하나가 다른 하나를 대체하지 않는다."""
    return json.loads(
        raw_json_text,
        object_pairs_hook=_reject_duplicates_pairs_hook,
        parse_int=_normalize_int_token,
        parse_float=_reject_float_token,
    )


def parse_json_reject_duplicates(raw_json_text: str) -> Any:
    """[하위 호환용] 중복 키만 검사하고 숫자 형식은 검사하지 않는다.
    새 호출부는 `parse_json_strict()`를 쓸 것을 권장한다."""
    return json.loads(raw_json_text, object_pairs_hook=_reject_duplicates_pairs_hook)
