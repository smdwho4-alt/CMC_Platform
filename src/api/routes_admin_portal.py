# -*- coding: utf-8 -*-
"""
CSHSP Admin Portal Routes — Sprint 1~3

Single Admin Portal API. 이 파일은 두 개의 라우터 팩토리를 제공한다(PM Sprint 2
결정사항 2: 신규 Namespace는 /api/admin/만 사용, Sprint 1 기존 /api/admin-portal/*는
삭제하지 않음).
- create_admin_portal_router(): Sprint 1 라우터(/api/admin-portal/*) — health/reservations
- create_admin_namespace_router(): Sprint 2 라우터(/api/admin/*) — dashboard/statistics
  (Sprint 3 Commit 2 이후 상담관리 등 추가 예정, 신규 라우터 재생성 아님)

인증(Authentication)은 기존 api_server.py의 Mock 인증(X-User-Id 헤더 + ACTIVE 사용자)
패턴을 그대로 미러링한다 — require_user는 api_server.py 내부 closure라 외부에서
import할 수 없으므로, 여기서는 동일 로직을 별도로 구현한다(기존 코드 무수정,
패턴만 재사용).

Sprint 3 Commit 1(RBAC): 인증 위에 권한(Role Check)을 추가했다. 모든 /api/admin/*
및 /api/admin-portal/* 엔드포인트(공개 목적인 /health 제외)는
"Authentication → Role Check → Endpoint" 순서를 FastAPI Depends 체인으로 강제한다
(PM 결정사항 7). 권한 문자열은 roles.json에 이미 정의된 것만 재사용하며 새 권한
모델을 만들지 않는다(dashboard:view/reservation:view/statistics:view 등).
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in ("core", "services"):
    sys.path.insert(0, str(_ROOT / "src" / _p))

from fastapi import APIRouter, Depends, Header, HTTPException, Query  # noqa: E402

import core_data_loader as loader  # noqa: E402
import pii_mask  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402


def _build_require_user(data_dir: Path):
    """Mock 인증 의존성 팩토리. 이 파일 내 모든 라우터가 공유한다(로직 중복 방지)."""
    def require_user(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        if not x_user_id:
            raise HTTPException(401, "X-User-Id 헤더 필요 (Mock 인증)")
        user = next((u for u in loader.load_entity("User", data_dir) if u.get("id") == x_user_id), None)
        if not user or user.get("status") != "ACTIVE":
            raise HTTPException(401, f"유효하지 않은 사용자: {x_user_id}")
        return user
    return require_user


def _has_permission(user: dict[str, Any], data_dir: Path, *perms: str) -> bool:
    """roles.json의 permissions 배열을 검사한다(api_server.py의 has_perm 패턴 재사용,
    새 권한 모델을 만들지 않고 기존 권한 문자열을 그대로 사용 — Sprint3 PM 결정사항)."""
    role = next((r for r in loader.load_entity("Role", data_dir) if r.get("id") == user.get("roleId")), None)
    user_perms = (role or {}).get("permissions", [])
    return "*" in user_perms or any(p in user_perms for p in perms)


def _build_require_permission(data_dir: Path, *perms: str):
    """Authentication → Role Check 의존성 체인(Sprint 3 PM 결정사항 7).

    FastAPI Depends 체인으로 인증(require_user)을 먼저 통과시키고, 이어서 권한을
    검사한다 — 두 단계가 명시적으로 분리되어 순서가 코드 구조 자체로 강제된다.
    perms 중 하나라도 있으면(OR) 통과, 역할 permissions에 '*'가 있으면 전체 허용.
    """
    require_user = _build_require_user(data_dir)

    def require_permission(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        if not _has_permission(user, data_dir, *perms):
            raise HTTPException(403, f"권한 없음: {' 또는 '.join(perms)} 필요 (현재 역할 {user.get('roleId')})")
        return user

    return require_permission


_MAX_STAT_DAYS = 31  # GAS summary를 일자별로 반복 호출하는 상한 — 무제한 호출 방지 안전장치


def _date_range(date_from: str, date_to: str) -> list[str]:
    """'YYYY-MM-DD' 두 값을 받아 그 사이 모든 날짜 목록을 반환한다(순서 무관하게 정렬)."""
    try:
        d1 = _dt.date.fromisoformat(date_from)
        d2 = _dt.date.fromisoformat(date_to)
    except ValueError as e:
        raise ValueError(f"날짜 형식이 올바르지 않습니다(YYYY-MM-DD): {e}") from e
    if d2 < d1:
        d1, d2 = d2, d1
    days = (d2 - d1).days + 1
    if days > _MAX_STAT_DAYS:
        raise ValueError(f"조회 기간이 너무 깁니다(최대 {_MAX_STAT_DAYS}일). 기간을 좁혀 주세요.")
    return [(d1 + _dt.timedelta(days=i)).isoformat() for i in range(days)]


def _sheets_connection_status() -> tuple[str, str | None]:
    """(상태문자열, 오류메시지) — /health와 /dashboard가 공유하는 연결 확인 로직."""
    try:
        sheets.ping()
        return "connected", None
    except sheets.SheetsIntegrationNotConfigured:
        return "not_configured", "Sheets 연동이 설정되지 않았습니다. 관리자에게 문의하세요."
    except sheets.SheetsIntegrationError as e:
        return "error", str(e)


def create_admin_portal_router(data_dir: Path) -> APIRouter:
    """Sprint 1 기존 라우터(/api/admin-portal/*) — routes_agents.create_agents_router와 동일 패턴.
    Sprint 3 Commit 1: 권한 검사(Role Check) 추가(PM 결정사항 7 — Authentication → Role Check → Endpoint)."""
    router = APIRouter(prefix="/api/admin-portal", tags=["admin-portal"])
    require_reservation_view = _build_require_permission(data_dir, "reservation:view")

    @router.get("/health")
    def health():
        """Sheets 연동 상태 확인. 인증 없이 호출 가능 — Portal 셸이 초기 화면에서
        '연동 미설정'과 '일시 오류'를 구분해 표시하기 위한 것으로, 조회 전용이며
        Sheets 데이터를 반환하지 않는다(PII 없음)."""
        status, message = _sheets_connection_status()
        if status == "connected":
            return {"ok": True, "sheetsIntegration": status}
        return {"ok": False, "sheetsIntegration": status, "message": message}

    @router.get("/reservations")
    def list_reservations(
        status: str = Query(default=""),
        dateFrom: str = Query(default=""),
        dateTo: str = Query(default=""),
        search: str = Query(default=""),
        sortBy: str = Query(default=""),
        sortDir: str = Query(default="desc"),
        page: int = Query(default=0, ge=0),
        pageSize: int = Query(default=0, ge=0),
        user: dict[str, Any] = Depends(require_reservation_view),
    ):
        """예약 목록 조회(권한: reservation:view). search/sortBy/sortDir/page/pageSize는 Sprint 2 Commit 2에서
        추가된 Optional 파라미터로, 전달하지 않으면 Sprint 1과 완전히 동일하게 동작한다
        (PM 결정사항 4: 기본 Response Schema 불변, 신규 파라미터는 Optional)."""
        try:
            raw_list = sheets.list_reservations(
                status=status, date_from=dateFrom, date_to=dateTo,
                search=search, sort_by=sortBy, sort_dir=sortDir,
            )
        except sheets.SheetsIntegrationNotConfigured as e:
            raise HTTPException(503, str(e)) from e
        except sheets.SheetsIntegrationError as e:
            raise HTTPException(502, str(e)) from e

        page_list = raw_list
        extra: dict[str, Any] = {}
        if pageSize > 0:
            start = page * pageSize
            page_list = raw_list[start:start + pageSize]
            extra = {"page": page, "pageSize": pageSize, "totalCount": len(raw_list)}

        masked = [pii_mask.build_masked_reservation(r) for r in page_list]
        return {"ok": True, "count": len(masked), "data": masked, **extra}

    @router.get("/reservations/{reservation_no}")
    def get_reservation(reservation_no: str, user: dict[str, Any] = Depends(require_reservation_view)):
        try:
            raw = sheets.get_reservation(reservation_no)
        except sheets.SheetsIntegrationNotConfigured as e:
            raise HTTPException(503, str(e)) from e
        except sheets.SheetsIntegrationError as e:
            raise HTTPException(502, str(e)) from e
        if raw is None:
            raise HTTPException(404, f"예약번호 없음: {reservation_no}")
        return {"ok": True, "data": pii_mask.build_masked_reservation(raw)}

    return router


def create_admin_namespace_router(data_dir: Path) -> APIRouter:
    """Sprint 2 신규 라우터(/api/admin/*, PM 결정사항 2 — 신규 엔드포인트 전용 Namespace).

    Sprint 2 Commit 1: GET /api/admin/dashboard
    Sprint 2 Commit 4: GET /api/admin/statistics
    Sprint 3 Commit 1: 권한 검사 추가(PM 결정사항 7).
    """
    router = APIRouter(prefix="/api/admin", tags=["admin-dashboard"])
    require_dashboard_view = _build_require_permission(data_dir, "dashboard:view")
    require_statistics_view = _build_require_permission(data_dir, "statistics:view")

    @router.get("/dashboard")
    def dashboard(user: dict[str, Any] = Depends(require_dashboard_view)):
        """Dashboard 요약(권한: dashboard:view) — 예약현황/오늘예약/예약상태/최근예약/시스템상태(P1).

        PM 결정사항(Sprint2_Implementation_Plan_v1.0.md 승인 §PM 결정사항 1, 6):
        - 예약 관련 수치는 Google Sheets 기준(GAS summary 결과를 그대로 사용, FastAPI가
          원시 데이터로부터 재계산하지 않음).
        - 개별 하위 조회가 실패해도 전체 응답을 실패시키지 않고 부분 실패를 함께 반환한다
          (Dashboard는 여러 위젯의 조합이므로 하나가 죽어도 나머지는 보여줘야 함).
        """
        sheets_status, sheets_message = _sheets_connection_status()

        summary: dict[str, Any] | None = None
        summary_error: dict[str, str] | None = None
        try:
            summary = sheets.get_summary()
        except sheets.SheetsIntegrationNotConfigured as e:
            summary_error = {"type": "not_configured", "message": str(e)}
        except sheets.SheetsIntegrationError as e:
            summary_error = {"type": "error", "message": str(e)}

        recent: list[dict[str, Any]] = []
        recent_error: dict[str, str] | None = None
        try:
            # 기존 list_reservations() 그대로 재사용 — GAS가 이미 createdAt 내림차순 정렬해
            # 반환하므로(_actionList 확인 근거) 앞 5건이 곧 최근 예약이다. 신규 파라미터 불필요.
            raw_recent = sheets.list_reservations()
            recent = [pii_mask.build_masked_reservation(r) for r in raw_recent[:5]]
        except sheets.SheetsIntegrationNotConfigured as e:
            recent_error = {"type": "not_configured", "message": str(e)}
        except sheets.SheetsIntegrationError as e:
            recent_error = {"type": "error", "message": str(e)}

        return {
            "ok": True,
            "system": {"fastapi": "ok", "sheetsIntegration": sheets_status,
                       "sheetsMessage": sheets_message},
            "summary": summary,
            "summaryError": summary_error,
            "recentReservations": recent,
            "recentReservationsError": recent_error,
        }

    @router.get("/statistics")
    def statistics(
        dateFrom: str = Query(default=""), dateTo: str = Query(default=""),
        user: dict[str, Any] = Depends(require_statistics_view),
    ):
        """통계(권한: statistics:view) — 예약건수/상태별/기간별, 읽기 전용.

        PM 결정사항 6: FastAPI가 직접 계산하지 않는다. GAS의 기존 summary 액션은
        단일 날짜만 지원하므로(sheets_api_v3_final.gs :: _actionSummary 확인), 기간
        통계는 날짜별로 summary를 반복 호출해 그 결과를 합산하는 방식으로 가공한다
        — 원시 예약 레코드를 직접 집계하지 않고 항상 GAS summary의 출력만 다룬다.
        dateFrom/dateTo 생략 시 오늘 하루만 조회(Dashboard와 동일 비용).
        """
        if dateFrom and dateTo:
            try:
                dates = _date_range(dateFrom, dateTo)
            except ValueError as e:
                raise HTTPException(400, str(e)) from e
        else:
            dates = [""]  # GAS 기본값(오늘)에 위임

        total = 0
        by_status: dict[str, int] = {}
        by_date: list[dict[str, Any]] = []
        day_errors: list[dict[str, str]] = []

        for d in dates:
            try:
                s = sheets.get_summary(date=d)
            except sheets.SheetsIntegrationNotConfigured as e:
                raise HTTPException(503, str(e)) from e
            except sheets.SheetsIntegrationError as e:
                day_errors.append({"date": d, "message": str(e)})
                continue
            day_total = s.get("total", 0)
            total += day_total
            for k, v in (s.get("byStatus") or {}).items():
                by_status[k] = by_status.get(k, 0) + v
            by_date.append({"date": s.get("date", d), "total": day_total})

        return {
            "ok": True,
            "totalReservations": total,
            "byStatus": by_status,
            "byDate": by_date,
            "dayErrors": day_errors,
        }

    return router
