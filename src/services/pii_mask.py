"""예약 조회 응답의 개인정보 필드 마스킹 유틸리티.

Sprint 1(Single Admin Portal 조회 기반) 전용 모듈이며, 다른 기존 서비스 로직은
호출하거나 변경하지 않는다.

PM 승인 마스킹 기준(Sprint1_PreImplementation_Check_v1.0.md §12 승인 항목 2):
- 성명(name): 첫 글자만 노출, 나머지는 '○'
- 생년월일(birth): 연도만 노출, 월/일은 '**'
- 휴대전화(phone): 앞 3자리·뒤 4자리 노출, 중간은 '****'
- 이메일(email): local-part 앞 3자만 노출, 나머지 '***', 도메인은 그대로
- 주소(address): 응답에 포함하지 않는다
- 주민등록번호: 이 모듈은 애초에 해당 필드를 다루지 않는다(GAS 응답 스키마에도 없음, 아래 참고)

참고: app/apps_script/sheets_api_v3_final.gs의 컬럼 매핑(_colKeyToField)을 확인한 결과,
현재 예약 시트에는 이메일·주소·주민등록번호 컬럼 자체가 존재하지 않는다. 아래 email/address
관련 로직은 향후 필드가 추가될 경우에 대비한 방어적 구현이며, 현재 데이터에는 적용될 일이 없다.
"""
from __future__ import annotations

MASK_CHAR = "○"


def mask_name(name: str) -> str:
    """'홍길동' → '홍○○'. 1글자 이하는 그대로 반환(마스킹할 나머지가 없음)."""
    if not name:
        return name
    if len(name) <= 1:
        return name
    return name[0] + MASK_CHAR * (len(name) - 1)


def mask_birth(birth: str) -> str:
    """'1980-05-05' → '1980-**-**'. 형식이 예상과 다르면 전체를 마스킹한다."""
    if not birth or len(birth) < 4 or not birth[:4].isdigit():
        return "****-**-**"
    return f"{birth[:4]}-**-**"


def mask_phone(phone: str) -> str:
    """'010-1234-5678' → '010-****-5678'. 숫자만 추출해 앞 3자리·뒤 4자리를 남긴다."""
    if not phone:
        return phone
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 7:
        return "***-****-****"
    return f"{digits[:3]}-****-{digits[-4:]}"


def mask_email(email: str) -> str:
    """'user1234@example.com' → 'use***@example.com'(현재 데이터에는 이메일 필드 없음, 방어적 구현)."""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[:3]}***@{domain}"


# Single Admin Portal 조회 응답에 포함할 필드 화이트리스트(Sprint 1 최소 범위).
# 여기에 없는 필드(담당자/예상비용/결제상태 등 운영 세부 필드, 주소·주민등록번호)는
# 이번 Sprint 응답에 포함하지 않는다. 필요 시 이후 Sprint에서 PM 승인을 받아 확장한다.
NON_PII_FIELDS = (
    "reservationNo", "createdAt", "program", "wishDate", "wishTime", "status", "note",
)

_MASKERS = {
    "name": mask_name,
    "birth": mask_birth,
    "phone": mask_phone,
    "email": mask_email,  # 현재 데이터에는 없는 필드지만 PM 승인 기준에 맞춰 방어적으로 포함
}


def build_masked_reservation(raw: dict) -> dict:
    """GAS 원본 예약 레코드에서 화이트리스트 필드만 선택하고 PII는 마스킹해 반환한다.

    - 화이트리스트에 없는 필드(주소 등)는 애초에 결과에 포함되지 않는다.
    - 주민등록번호는 GAS 응답 스키마 자체에 없으므로 이 함수가 다룰 대상이 아니다.
    """
    result: dict = {}
    for field in NON_PII_FIELDS:
        if field in raw:
            result[field] = raw[field]
    for field, masker in _MASKERS.items():
        value = raw.get(field)
        if value:
            result[field] = masker(value)
    return result
