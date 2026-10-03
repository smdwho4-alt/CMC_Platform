"""Sheets 쓰기 전용 서비스 — Reservation Approval Foundation (Sprint 4 Commit 2).

sheets_readonly_service.py는 조회 전용으로 설계되어 있고(모듈 독스트링에 "쓰기
액션은 이 모듈에서 절대 호출하지 않는다"고 명시) 그 원칙을 지키기 위해 쓰기 기능을
그 파일에 추가하지 않고 이 신규 파일로 분리한다.

Google Apps Script(app/apps_script/sheets_api_v3_final.gs)의 기존 updateStatus
action만 호출한다 — GAS에 신규 action을 추가하지 않는다(GAS 코드 무수정, Sprint 4
Commit 2 금지 사항 준수). approve/reject가 다루는 상태값은
src/api/reservation_approval_states.py에서 검증한 뒤 이 함수가 호출된다.

연동 URL은 sheets_readonly_service.py와 동일하게 환경변수(CSHSP_GAS_WEBAPP_URL)만
사용한다(코드 하드코딩 없음).
"""
from __future__ import annotations

import os
from typing import Any

import requests

from sheets_readonly_service import SheetsIntegrationError, SheetsIntegrationNotConfigured

GAS_WEBAPP_URL_ENV = "CSHSP_GAS_WEBAPP_URL"
_TIMEOUT_SECONDS = 10
_WRITE_ACTIONS = ("updateStatus",)


def _get_webapp_url() -> str:
    # sheets_readonly_service._get_webapp_url()과 동일 로직(그 함수는 private이므로
    # 기존 파일을 수정하지 않기 위해 여기서 짧게 중복 구현한다).
    url = os.environ.get(GAS_WEBAPP_URL_ENV, "").strip()
    if not url:
        raise SheetsIntegrationNotConfigured(
            f"{GAS_WEBAPP_URL_ENV} 환경변수가 설정되지 않았습니다. "
            "예약 승인/거절 기능을 사용하려면 서버 환경변수로 GAS Web App URL을 설정해야 합니다."
        )
    return url


def _call_gas_write(action: str, body: dict[str, Any], *, session=None) -> dict[str, Any]:
    if action not in _WRITE_ACTIONS:
        raise ValueError(f"쓰기 서비스에서 허용되지 않는 action: {action!r}")

    url = _get_webapp_url()
    payload = {"action": action, **body}
    http = session or requests
    try:
        resp = http.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SheetsIntegrationError(f"GAS 호출 실패({action}): {exc}") from exc

    try:
        result = resp.json()
    except ValueError as exc:
        raise SheetsIntegrationError(f"GAS 응답 파싱 실패({action}): {exc}") from exc

    if not result.get("ok", False):
        raise SheetsIntegrationError(f"GAS 오류 응답({action}): {result.get('error', '알 수 없는 오류')}")

    return result


def update_status(reservation_no: str, status: str, *, session=None) -> dict[str, Any]:
    """예약 상태 변경(action=updateStatus). GAS 기존 action을 그대로 재사용한다."""
    if not reservation_no:
        raise ValueError("reservation_no는 필수입니다.")
    if not status:
        raise ValueError("status는 필수입니다.")
    return _call_gas_write("updateStatus", {"no": reservation_no, "status": status}, session=session)


def check_configured() -> None:
    """GAS Web App URL이 설정됐는지만 확인한다(값은 반환하지 않음, 네트워크
    요청 없음). `update_status_idempotent()`가 `gas_orchestration.
    execute_with_idempotency(prepare_dispatch=...)`에 넘기는 용도로 Sprint8
    Commit8-3b에서 추가했다 — 설정 오류를 "GAS에 도달했는지 알 수 없는 상태"
    (SENT_UNCERTAIN)가 아니라 "네트워크 시도 자체가 없었던 상태"
    (NOT_SENT_PREP_FAILED)로 정확히 분류하기 위함이다."""
    _get_webapp_url()


def update_status_idempotent(
    reservation_no: str,
    status: str,
    *,
    idempotency_key: str,
    fingerprint: str,
    conn: Any,
    now: Any = None,
    correlation_id: str | None = None,
    session: Any = None,
) -> Any:
    """`update_status()`를 idempotency 실행권 판정으로 감싼 추가 진입점
    (Sprint8 Commit8-3b, 기존 예약 승인/거절 흐름과의 최소 통합). 기존
    `update_status()`는 무수정 — 이 함수는 호출부가 선택적으로 쓸 수 있는
    새 래퍼일 뿐이며, 로직은 전부 이미 검증된 `gas_orchestration.
    execute_with_idempotency()`/`idempotency_store.py`를 재사용한다(새
    idempotency 로직을 여기서 다시 만들지 않는다).

    `update_status()`가 던지는 예외(`SheetsIntegrationError` 등)는 네트워크
    실패와 GAS측 확정 거부를 구분하지 않는다(그 함수 자체의 기존 설계, 이번
    통합에서 바꾸지 않음) — 그래서 이 예외는 재분류하지 않고 그대로
    `gas_orchestration`에 전파시켜 `SENT_UNCERTAIN`(결과 불확실)으로 취급한다
    (모듈 docstring의 "예외 타입별로 세부 분류를 시도하지 않는다" 원칙과
    일치). 반환값은 `gas_orchestration.OrchestrationResult`."""
    try:  # 지연 import: 기존 update_status() 호출부에 새 모듈 의존성을 강제하지 않음
        import gas_orchestration
    except ImportError:
        # 호출부(routes_admin_portal.py 등)가 이미 src/idempotency를 sys.path에
        # 넣어뒀다면 이 분기는 타지 않는다 — 이 모듈을 단독으로 테스트/재사용할
        # 때를 위한 안전망.
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "idempotency"))
        import gas_orchestration

    def _adapter(*, key: str, fingerprint: str):  # noqa: ARG001 - 콜러블 시그니처 고정(gas_orchestration)
        update_status(reservation_no, status, session=session)
        return gas_orchestration.GasResponse(success=True)

    return gas_orchestration.execute_with_idempotency(
        conn,
        key=idempotency_key,
        fingerprint=fingerprint,
        gas_adapter=_adapter,
        prepare_dispatch=check_configured,
        now=now,
        correlation_id=correlation_id,
    )
