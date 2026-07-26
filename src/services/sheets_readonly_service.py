"""Sheets 조회 전용 서비스 — Business Service Layer 최소 연동 경로 (Sprint 1~2).

Google Apps Script(Integration Layer, app/apps_script/sheets_api_v3_final.gs)의
조회 전용 액션(ping/list/get/summary)만 호출한다. 쓰기 액션(create/updateStatus/
updateOps/update)은 이 모듈에서 절대 호출하지 않는다(PM 승인 제외범위).

Sprint 2 Commit 1: get_summary() 추가 — GAS의 기존 _actionSummary(당일 집계)를
그대로 호출한다. PM 결정사항 6("FastAPI가 직접 계산하지 않는다, GAS summary 결과를
가공") — 이 함수는 GAS 응답을 그대로 반환하며 통계 재계산을 하지 않는다.

연동 URL은 코드에 하드코딩하지 않고 환경변수(CSHSP_GAS_WEBAPP_URL)에서 읽는다.
(Enterprise_Architecture_ToBe_v1.0.md §8 "연동 정보 중앙화" 원칙 준수 — 클라이언트 코드에
포함되어 있던 기존 방식과 달리, 서버 환경변수로만 관리한다.)

GAS 응답 스키마(app/apps_script/sheets_api_v3_final.gs 확인 근거):
- 성공: {"ok": true, "data": ..., "count"?: N}
- 실패: {"ok": false, "error": "...", "code": N}
"""
from __future__ import annotations

import os
from typing import Any

import requests

GAS_WEBAPP_URL_ENV = "CSHSP_GAS_WEBAPP_URL"
_TIMEOUT_SECONDS = 10
_READONLY_ACTIONS = ("ping", "list", "get", "summary")
# GAS _actionList가 실제로 지원하는 필터 파라미터만 화이트리스트로 허용한다
# (app/apps_script/sheets_api_v3_final.gs :: _actionList 확인 근거).
_LIST_FILTER_KEYS = ("status", "dateFrom", "dateTo")


class SheetsIntegrationNotConfigured(RuntimeError):
    """CSHSP_GAS_WEBAPP_URL 환경변수가 설정되지 않았을 때 발생한다."""


class SheetsIntegrationError(RuntimeError):
    """GAS 호출 실패(네트워크 오류, 타임아웃, GAS 측 오류 응답 등)."""


def _get_webapp_url() -> str:
    url = os.environ.get(GAS_WEBAPP_URL_ENV, "").strip()
    if not url:
        raise SheetsIntegrationNotConfigured(
            f"{GAS_WEBAPP_URL_ENV} 환경변수가 설정되지 않았습니다. "
            "Sheets 조회 기능을 사용하려면 서버 환경변수로 GAS Web App URL을 설정해야 합니다."
        )
    return url


def _call_gas(action: str, params: dict[str, Any] | None = None, *, session=None) -> dict[str, Any]:
    if action not in _READONLY_ACTIONS:
        raise ValueError(f"조회 전용 서비스에서 허용되지 않는 action: {action!r}")

    url = _get_webapp_url()
    query = {"action": action, **(params or {})}
    http = session or requests
    try:
        resp = http.get(url, params=query, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SheetsIntegrationError(f"GAS 호출 실패({action}): {exc}") from exc

    try:
        body = resp.json()
    except ValueError as exc:
        raise SheetsIntegrationError(f"GAS 응답 파싱 실패({action}): {exc}") from exc

    if not body.get("ok", False):
        raise SheetsIntegrationError(f"GAS 오류 응답({action}): {body.get('error', '알 수 없는 오류')}")

    return body


def ping(*, session=None) -> dict[str, Any]:
    """연동 상태 확인용(action=ping)."""
    return _call_gas("ping", session=session)


_SEARCH_FIELDS = ("reservationNo", "name", "phone", "program")
_SORT_KEYS = ("createdAt", "wishDate", "status", "reservationNo")


def list_reservations(
    status: str = "", date_from: str = "", date_to: str = "",
    search: str = "", sort_by: str = "", sort_dir: str = "desc",
    *, session=None,
) -> list[dict[str, Any]]:
    """예약 목록 조회(action=list). GAS가 지원하는 필터(status/dateFrom/dateTo)는
    그대로 전달하고, GAS가 지원하지 않는 검색/정렬(search/sort_by/sort_dir)은
    GAS 응답을 받은 뒤 Python에서 후처리한다(Sprint 2 Commit 2, GAS 무수정 원칙).

    search/sort_by/sort_dir을 모두 생략하면 Sprint 1과 동일한 동작(GAS가 반환한
    순서 그대로)을 유지한다 — 기존 호출자(Dashboard 등)의 동작을 바꾸지 않는다.
    """
    raw_params = {"status": status, "dateFrom": date_from, "dateTo": date_to}
    params = {k: v for k, v in raw_params.items() if v and k in _LIST_FILTER_KEYS}
    body = _call_gas("list", params, session=session)
    data: list[dict[str, Any]] = body.get("data", [])

    if search:
        needle = search.strip().lower()
        data = [r for r in data if any(needle in str(r.get(f, "")).lower() for f in _SEARCH_FIELDS)]

    if sort_by in _SORT_KEYS:
        reverse = sort_dir != "asc"
        data = sorted(data, key=lambda r: str(r.get(sort_by, "")), reverse=reverse)

    return data


def get_reservation(reservation_no: str, *, session=None) -> dict[str, Any] | None:
    """예약 단건 조회(action=get)."""
    if not reservation_no:
        raise ValueError("reservation_no는 필수입니다.")
    body = _call_gas("get", {"no": reservation_no}, session=session)
    return body.get("data")


def get_summary(date: str = "", *, session=None) -> dict[str, Any]:
    """일자별 운영 현황 요약(action=summary). GAS _actionSummary를 그대로 호출·반환한다.

    GAS 응답 형태(sheets_api_v3_final.gs :: _actionSummary 확인):
    {date, total, byStatus, byRoom, byPayment, byDoctor, totalEstimatedCost}
    date를 생략하면 GAS가 자체적으로 오늘 날짜를 기본값으로 사용한다.
    """
    params = {"date": date} if date else {}
    body = _call_gas("summary", params, session=session)
    return body.get("data", {})
