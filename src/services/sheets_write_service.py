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
