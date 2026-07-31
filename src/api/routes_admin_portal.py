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
import re
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in ("core", "services", "reservation", "auth"):
    sys.path.insert(0, str(_ROOT / "src" / _p))
sys.path.insert(0, str(_HERE))  # file_lock.py, reservation_approval_states.py (같은 src/api/ 디렉터리)

from fastapi import APIRouter, Depends, HTTPException, Query  # noqa: E402
from pydantic import BaseModel, field_validator  # noqa: E402

import core_data_loader as loader  # noqa: E402
import pii_mask  # noqa: E402
import reservation_approval_states as approval_states  # noqa: E402
import reservation_audit as audit  # noqa: E402
import reservation_engine as engine  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402
import sheets_write_service as sheets_write  # noqa: E402
from file_lock import DataLock  # noqa: E402
from json_store import now_iso, read_doc, write_doc  # noqa: E402
from routes_auth import build_require_csrf, build_require_session_user  # noqa: E402


def _build_require_user(data_dir: Path):
    """인증 의존성 팩토리(Sprint8 Commit8-2: 세션 우선, Mock은 명시적 환경설정
    시에만). 이 파일 내 모든 라우터가 공유한다(로직 중복 방지) —
    routes_auth.build_require_session_user()를 그대로 위임한다."""
    return build_require_session_user(data_dir)


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

    # Sprint8 Commit8-2: 상태변경 API에 CSRF를 추가로 붙일 때 동일 require_user
    # 객체를 재사용해 FastAPI Depends 캐시로 세션 검증이 한 번만 실행되게 한다.
    require_permission.require_user = require_user  # type: ignore[attr-defined]
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


# ── Sprint 3 Commit 2: CRM 통합(상담관리) — 기존 crm.json 스키마 그대로 재사용 ──
# PM 결정사항: CRM을 새로 만들지 않는다. 기존 crm_agent.py/POST /api/crm/notifications가
# 이미 만들어 둔 crm.json 레코드를 조회·상태변경만 한다. 생성(POST 신규 티켓)·삭제
# 기능은 이번 Sprint 범위에 없다(기존 생성 경로는 /api/crm/notifications 그대로 유지).
_CRM_STATUS_ORDER = ["OPEN", "IN_PROGRESS", "CLOSED"]  # 순차 전이만 허용(역행 금지)


class ConsultationStatusBody(BaseModel):
    status: str
    handledBy: str | None = None


# ── Sprint 4 Commit 2: 예약 승인/거절(Reservation Approval Foundation) ──
# PM 결정 2(Sprint4_Commit2_Implementation_Plan_v1.0.md §12-2): 거절 사유는 필수이며
# 검증 실패 시 422를 반환한다(Pydantic validator가 FastAPI 표준 422로 자동 변환).
_REJECT_REASON_MIN_LEN = 2
_REJECT_REASON_MAX_LEN = 200
_LONG_DIGIT_RUN = re.compile(r"\d{6,}")  # 전화번호·주민등록번호로 의심되는 연속 숫자 방어(완전 탐지 아님)
_DIGIT_SEPARATOR = re.compile(r"(?<=\d)[\s\-](?=\d)")  # '010-1234-5678'처럼 숫자 사이 구분자만 제거(완전 탐지 목적 아님, 날짜 등 오탐 가능성 있음 — 알려진 제약)


class RejectReservationBody(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("거절 사유를 입력해 주세요.")
        if len(v) < _REJECT_REASON_MIN_LEN:
            raise ValueError(f"거절 사유가 너무 짧습니다(최소 {_REJECT_REASON_MIN_LEN}자).")
        if len(v) > _REJECT_REASON_MAX_LEN:
            raise ValueError(f"거절 사유가 너무 깁니다(최대 {_REJECT_REASON_MAX_LEN}자).")
        if _LONG_DIGIT_RUN.search(_DIGIT_SEPARATOR.sub("", v)):
            raise ValueError("거절 사유에 전화번호·주민등록번호로 의심되는 긴 숫자를 입력할 수 없습니다. 개인정보를 입력하지 마세요.")
        return v


def _crm_masking_tier(user: dict[str, Any]) -> str:
    """PM 승인 3단계 마스킹 정책 — 역할별 조회 수준.
    ROLE-ADMIN=admin(원문), ROLE-DIRECTOR=supervisor(전체이름), 그 외=operator(마스킹).
    새 역할이 추가되면 기본값은 가장 보수적인 'operator'로 떨어진다(안전한 기본값)."""
    role_id = user.get("roleId")
    if role_id == "ROLE-ADMIN":
        return "admin"
    if role_id == "ROLE-DIRECTOR":
        return "supervisor"
    return "operator"


def _mask_name_by_tier(name: str | None, tier: str) -> str | None:
    if not name:
        return name
    if tier in ("admin", "supervisor"):
        return name  # PM 예시: Admin=원문, Supervisor=전체이름(둘 다 마스킹 없음 — 현재 CRM에는
                     # 이름 외 다른 PII 필드가 없어 이 두 단계가 결과적으로 동일하게 보임)
    return pii_mask.mask_name(name)  # operator: 홍○○


def _patient_name_map(data_dir: Path) -> dict[str, str]:
    """patientId -> name (patients.json, 존재하지 않으면 빈 dict)."""
    try:
        patients = loader.load_entity("Patient", data_dir)
    except Exception:  # noqa: BLE001 — 조회 실패 시 이름 없이 진행(치명적 오류 아님)
        return {}
    return {p.get("id"): p.get("name") for p in patients if p.get("id")}


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
    Sprint 3 Commit 2: GET /api/admin/consultations, POST /api/admin/consultations/{id}/status
    """
    router = APIRouter(prefix="/api/admin", tags=["admin-dashboard"])
    require_dashboard_view = _build_require_permission(data_dir, "dashboard:view")
    require_statistics_view = _build_require_permission(data_dir, "statistics:view")
    # crm:manage(ROLE-CRM/ROLE-ADMIN) 또는 crm:log(ROLE-AI-AGENT, 조회만) 또는
    # audit:view(ROLE-DIRECTOR, 운영 감독 목적의 조회)가 있으면 상담 목록을 볼 수 있다.
    # 상태변경(쓰기)은 아래에서 crm:manage만 별도로 요구한다(더 엄격).
    require_consultation_view = _build_require_permission(data_dir, "crm:manage", "crm:log", "audit:view")
    require_consultation_manage = _build_require_permission(data_dir, "crm:manage")
    # Sprint 4 Commit 2: 기존 reservation:approve 권한 문자열을 그대로 재사용한다
    # (reservation_engine.py::approve_reservation()/reject_reservation()과 동일 권한,
    # 새 권한 모델을 만들지 않는다 — PM 권한 원칙).
    require_reservation_approve = _build_require_permission(data_dir, "reservation:approve")
    # Sprint8 Commit8-2: 상태변경(쓰기) API에 CSRF 검증 추가(PM 승인사항 §12 최소
    # 대상: 승인/거절/상태변경). require_user 객체를 재사용해 세션 검증 중복 없음.
    require_csrf_reservation_approve = build_require_csrf(require_reservation_approve.require_user)
    require_csrf_consultation_manage = build_require_csrf(require_consultation_manage.require_user)

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

    @router.get("/consultations")
    def list_consultations(
        status: str = Query(default=""),
        channel: str = Query(default=""),
        user: dict[str, Any] = Depends(require_consultation_view),
    ):
        """상담(CRM) 목록 조회 — 기존 crm.json 재사용, 신규 모델 없음(PM 결정사항 1).
        channel 필터는 Sprint 3 Commit 4(AI 지원 기반)에서 channel=AI_CHAT으로
        AI가 생성한 상담만 걸러보는 데 사용될 예정이며, 이번 Commit에서 이미
        지원해 둔다(신규 엔드포인트 추가 없이 파라미터만 재사용)."""
        doc = read_doc(data_dir / "crm.json")
        records = doc.get("records", [])
        if status:
            records = [r for r in records if r.get("status") == status]
        if channel:
            records = [r for r in records if r.get("channel") == channel]

        tier = _crm_masking_tier(user)
        names = _patient_name_map(data_dir)
        result = []
        for r in records:
            result.append({
                "id": r.get("id"),
                "patientId": r.get("patientId"),
                "patientName": _mask_name_by_tier(names.get(r.get("patientId")), tier),
                "reservationId": r.get("reservationId"),
                "channel": r.get("channel"),
                "direction": r.get("direction"),
                "category": r.get("category"),
                "summary": r.get("summary"),  # PM 결정사항 4: summary는 원문 그대로(마스킹 안 함)
                "handledBy": r.get("handledBy"),
                "followUpDate": r.get("followUpDate"),
                "status": r.get("status"),
                "createdAt": r.get("createdAt"),
                "updatedAt": r.get("updatedAt"),
            })
        return {"ok": True, "count": len(result), "data": result, "maskingTier": tier}

    @router.post("/consultations/{consultation_id}/status")
    def update_consultation_status(
        consultation_id: str, body: ConsultationStatusBody,
        user: dict[str, Any] = Depends(require_consultation_manage),
        _csrf: dict[str, Any] = Depends(require_csrf_consultation_manage),
    ):
        """상담 상태 변경 — OPEN→IN_PROGRESS→CLOSED 순차 전이만 허용(PM 승인 범위).
        CRM 생성·삭제, 예약 수정·삭제, 고객정보 수정은 이 엔드포인트에서 다루지
        않는다(PM 결정사항 2 금지 목록). 상태값 외 다른 필드(summary/category 등)는
        이 엔드포인트로 변경할 수 없다."""
        if body.status not in _CRM_STATUS_ORDER:
            raise HTTPException(400, f"허용되지 않은 상태값: {body.status} (허용: {_CRM_STATUS_ORDER})")

        with DataLock(data_dir):
            doc = read_doc(data_dir / "crm.json")
            records = doc.get("records", [])
            rec = next((r for r in records if r.get("id") == consultation_id), None)
            if rec is None:
                raise HTTPException(404, f"상담 없음: {consultation_id}")

            current = rec.get("status", "OPEN")
            if current not in _CRM_STATUS_ORDER:
                raise HTTPException(409, f"알 수 없는 현재 상태: {current}")
            cur_idx = _CRM_STATUS_ORDER.index(current)
            new_idx = _CRM_STATUS_ORDER.index(body.status)
            if new_idx != cur_idx + 1:
                raise HTTPException(
                    409,
                    f"허용되지 않은 상태 전이: {current} → {body.status} "
                    f"(순차 전이만 허용: {' → '.join(_CRM_STATUS_ORDER)})",
                )

            if body.handledBy:
                handler = next((u for u in loader.load_entity("User", data_dir)
                                 if u.get("id") == body.handledBy), None)
                if not handler or handler.get("status") != "ACTIVE":
                    raise HTTPException(400, f"유효하지 않은 담당자: {body.handledBy}")
                rec["handledBy"] = body.handledBy

            rec["status"] = body.status
            rec["updatedAt"] = now_iso()
            write_doc(data_dir / "crm.json", doc)

        tier = _crm_masking_tier(user)
        names = _patient_name_map(data_dir)
        return {
            "ok": True,
            "data": {
                "id": rec.get("id"),
                "patientName": _mask_name_by_tier(names.get(rec.get("patientId")), tier),
                "status": rec.get("status"),
                "handledBy": rec.get("handledBy"),
                "updatedAt": rec.get("updatedAt"),
            },
        }

    # ── Sprint 4 Commit 3 / 3A: Reservation Slot Integration (Hardening) ──
    # 승인(예약확정)일 때만 Slot을 조회·점유한다(거절은 Slot을 소비하지 않으므로 대상 아님).
    # 기존 reservation_engine.py의 Slot 갱신/해제 로직(_update_slot/_release_slot)을
    # 그대로 재사용하며 신규 Slot Engine을 만들지 않는다(PM 재사용 원칙).
    #
    # Commit 3A(Hardening): Repository의 실제 Slot 상태값을 재조사해 확정했다
    # (reservation_engine.py/slot_generator.py 확인 — 'OPEN'은 존재하지 않고
    # 'AVAILABLE'이 정상 상태다). 승인 가능 상태를 AVAILABLE 하나로 제한하고,
    # FULL/BLOCKED/HOLD/CLOSED/그 외 알 수 없는 값을 전부 명시적으로 차단한다.
    # 상태 확인이 Capacity 확인보다 먼저 수행된다(PM 안전 우선 원칙).
    _SLOT_ALLOWED_STATUSES = {"AVAILABLE"}
    _SLOT_STATUS_ERROR_CODES = {
        "FULL": "SLOT_FULL",
        "BLOCKED": "SLOT_BLOCKED",
        "HOLD": "SLOT_ON_HOLD",
        "CLOSED": "SLOT_NOT_AVAILABLE",  # 현재 데이터 모델에 실존하지 않는 값이나 정책 대비 매핑
    }
    # WAITING은 Repository에 실존하는 상태값이지만 PM 지시(§3 Slot 상태 정책)의 허용/차단
    # 목록 어디에도 명시되지 않았다 — "정원이 남아도 허용 상태가 아니면 점유하지 않는다"는
    # 안전 우선 원칙에 따라 허용 목록에 넣지 않고 catch-all(SLOT_INVALID_STATE)로 차단한다
    # (Commit 3A에서 내린 판단, 완료 보고에 명시).
    _SLOT_MESSAGES = {
        "SLOT_NOT_AVAILABLE": "해당 시간대에는 예약 가능한 슬롯이 없습니다.",
        "SLOT_FULL": "해당 시간대의 예약 정원이 마감되었습니다.",
        "SLOT_BLOCKED": "해당 시간대는 운영상 예약이 차단되어 있습니다.",
        "SLOT_ON_HOLD": "해당 시간대는 현재 예약이 보류되어 있습니다.",
        "SLOT_INVALID_STATE": "예약 슬롯 상태를 확인할 수 없습니다. 관리자에게 문의해 주세요.",
        "SLOT_RESERVATION_CONFLICT": "예약과 슬롯 정보가 일치하지 않아 처리할 수 없습니다. 관리자 확인이 필요합니다.",
    }

    def _slot_error(code: str) -> HTTPException:
        # 기존 API 오류 응답 구조({code, message})를 그대로 재사용한다(신규 포맷 없음).
        return HTTPException(409, {"code": code, "message": _SLOT_MESSAGES[code]})

    # ── Sprint 4 Commit 5-2: Approval Pipeline Policy Integration ──
    # Commit 5-1에서 만든 validation_context/resolve_program()을 승인 Pipeline에
    # 실제로 연결한다. 신규 Policy Engine/Repository/Service Layer를 만들지 않고
    # 기존 engine.resolve_program()/engine.validate_slot()만 호출한다(PM 재사용 원칙).
    # Program Mapping 실패/정책 차단/Unknown Verdict/Exception 4가지 실패 경로는 전부
    # Slot Reserve 이전에 raise되므로, 기존 Slot Reserve/Sheets Write/Audit/Rollback
    # 로직(Commit2/3/3A)에는 어떤 코드도 손대지 않는다 — 아래에서 새로 추가되는
    # 코드는 기존 "상태 확인" 이전에 삽입되는 블록 하나뿐이다.
    # Sprint 4 Commit 5-2A(PM 리뷰 반영): validate_slot()은 Policy Layer만 담당하고
    # Execution Layer(Slot 자체 status/Capacity/중복점유 — Commit3A가 이미 소유)를
    # 대체하지 않는다. validate_slot()은 Sprint B 때부터 FULL/HOLD/WAITING/DUPLICATED
    # 판정과 Capacity 판정을 자체적으로 갖고 있는데, 이 4개 verdict는 전부 Slot의
    # status/capacity 필드만 근거로 하며 Commit3A의 _SLOT_ALLOWED_STATUSES/Capacity
    # 검사와 동일한 데이터를 본다 — 그래서 이 4개는 여기서 차단하지 않고 그대로
    # 통과시켜 아래 기존 Commit3A 로직이 최종 판정·코드(SLOT_FULL/SLOT_ON_HOLD/
    # SLOT_INVALID_STATE 등)를 생성하도록 위임한다.
    # BLOCKED verdict는 두 가지 경로에서 나올 수 있어 모호하다: (a) Slot 자체
    # status=="BLOCKED"(Execution Layer, Commit3A의 SLOT_BLOCKED와 동일 근거) —
    # 위임한다. (b) 휴진일/의사·간호사 근무불가/검사실 운영불가/장비 사용불가/운영시간
    # 외(Policy Layer, Commit3A는 전혀 알지 못하는 영역) — 여기서 차단해야만 한다
    # (그러지 않으면 의사가 없는 날에도 승인이 나가는 실제 버그가 된다). 이미 위에서
    # 조회해 둔 slot 변수의 실제 status 값으로 두 경우를 구분한다(reservation_engine.py
    # 재수정 없이, routes 레이어에서만 판단).
    _EXECUTION_LAYER_VERDICTS = {"FULL", "HOLD", "WAITING", "DUPLICATED"}

    def _server_log(event: str, **fields: Any) -> None:
        # PM §12: reservation_no/slot_id/program/오류코드만 남긴다. 환자명·전화번호·
        # 주민번호 등 개인정보는 절대 남기지 않는다. 새 로깅 시스템은 도입하지 않는다
        # (Commit 3A에서 확인한 기존 관례 — 이 코드베이스에 logging 모듈 사용례가 없음).
        parts = " ".join(f"{k}={v}" for k, v in fields.items())
        print(f"[POLICY][{event}] {parts}", file=sys.stderr)

    def _reserve_slot_for_approval(reservation: dict[str, Any], user: dict[str, Any]) -> str:
        wish_date = reservation.get("wishDate")
        wish_time = reservation.get("wishTime")
        reservation_no = reservation.get("reservationNo")
        program_input = reservation.get("program")
        with DataLock(data_dir):
            # Lock 내부에서 최신 Slot 목록을 재조회한다(PM §6 — Lock 이전에 읽은 값을
            # 신뢰하지 않는다). 이 함수 호출 전에는 Slot을 조회하지 않는다.
            slots = loader.load_entity("Slot", data_dir)

            slot = next(
                (s for s in slots if s.get("date") == wish_date and s.get("time") == wish_time), None,
            )
            if slot is None:
                raise _slot_error("SLOT_NOT_AVAILABLE")

            # Program Mapping(PM §4) — resolve_program()만 재사용, Fuzzy/부분일치 없음.
            # 실패 시 Slot Reserve/Sheets Write/Audit 없이 422로 즉시 차단, Server Log만 기록.
            program = engine.resolve_program(program_input, data_dir)
            if program is None:
                _server_log("RESERVATION_PROGRAM_UNMAPPED", reservation_no=reservation_no,
                            slot_id=slot.get("id"), program=program_input)
                raise HTTPException(422, {
                    "code": "RESERVATION_PROGRAM_UNMAPPED",
                    "message": "예약의 검진 프로그램을 확인할 수 없어 승인을 진행할 수 없습니다. 관리자에게 문의해 주세요.",
                })

            # Validation Context(PM §5) — Sheets 예약은 구조적으로 환자 식별자가 없으므로
            # validation_context="reservation_approval"로 PATIENT_DUPLICATE 검사만
            # 명시적으로 제외한다(Commit 5-1에서 확정한 정책). patient_id=None은 이
            # 컨텍스트가 그 검사를 이미 비활성화했기 때문에 전달되는 값이며, None 자체가
            # 우회 메커니즘으로 쓰이지 않는다(PM이 금지한 암묵적 우회와는 다른 경우).
            try:
                policy = engine.validate_slot(
                    slot["id"], None, wish_date, data_dir, program["id"],
                    exclude_reservation_id=None, validation_context="reservation_approval",
                )
            except Exception as exc:  # noqa: BLE001 — PM §7: validate_slot() 예외 → 500(정책 검증 실패)
                _server_log("SLOT_POLICY_VALIDATION_FAILED", reservation_no=reservation_no,
                            slot_id=slot.get("id"), program=program_input, error=str(exc))
                raise HTTPException(500, {
                    "code": "SLOT_POLICY_VALIDATION_FAILED",
                    "message": "예약 정책 검증 중 오류가 발생했습니다. 관리자에게 문의해 주세요.",
                }) from exc

            # INVALID도 BLOCKED와 마찬가지로 두 경로에서 나올 수 있다: (a) 프로그램 제한
            # 슬롯 불일치(validate_slot()의 최상단 체크, Commit3A는 전혀 모르는 영역 —
            # Policy Layer) (b) Slot status가 AVAILABLE/FULL/BLOCKED/HOLD/WAITING/
            # DUPLICATED 중 어느 것도 아닌 미확정 값(CLOSED/빈 문자열/null/알 수 없는 값)에
            # 대한 validate_slot()의 catch-all(Commit3A의 _SLOT_ALLOWED_STATUSES fallback과
            # 동일 근거, Execution Layer). validate_slot()의 프로그램 제한 체크는 이 파이프
            # 라인에서 결정적으로 재현 가능하므로(동일 slot/program 데이터), 그 조건을 그대로
            # 재확인해 두 경로를 구분한다(reservation_engine.py 재수정 없이 routes 레이어에서만
            # 판단).
            program_restricted_mismatch = bool(
                slot.get("programRestriction") and program.get("id")
                and slot["programRestriction"] != program["id"]
            )

            verdict = policy.get("verdict") if isinstance(policy, dict) else None
            if verdict == "AVAILABLE":
                pass  # 계속 진행 — 아래 기존 Slot 상태검사로
            elif (
                verdict in _EXECUTION_LAYER_VERDICTS
                or (verdict == "BLOCKED" and slot.get("status") == "BLOCKED")
                or (verdict == "INVALID" and not program_restricted_mismatch)
            ):
                # Execution Layer 영역(Commit5-2A) — Slot 자체 status/Capacity 근거이므로
                # 여기서 차단하지 않는다. 아래 기존 Commit3A 로직이 동일 데이터를 다시 보고
                # 최종 코드(SLOT_FULL/SLOT_BLOCKED/SLOT_ON_HOLD/SLOT_INVALID_STATE 등)를
                # 생성한다 — validate_slot()의 이 판정은 여기서 그대로 버려진다(재사용 아님,
                # 이중 판정 방지를 위해 의도적으로 무시).
                pass
            elif verdict in {"BLOCKED", "INVALID"}:
                # 진짜 Policy Layer 차단만 여기서 처리한다: BLOCKED인데 Slot 자체 status는
                # BLOCKED가 아닌 경우(휴진일/의사·간호사 근무불가/검사실 운영불가/장비 사용
                # 불가/운영시간 외) 또는 INVALID인데 프로그램 제한 슬롯 불일치가 실제 원인인
                # 경우. Commit3A는 이 영역을 전혀 모르므로 여기서 차단하지 않으면 정책 위반
                # 승인이 나갈 수 있다.
                raise HTTPException(409, {
                    "code": "RESERVATION_POLICY_BLOCKED",
                    "message": "예약 정책 검증에 의해 이 예약을 확정할 수 없습니다.",
                })
            else:
                # Unknown Verdict(PM §8) — validate_slot() 정의에 없는 값/반환 구조 이상/
                # verdict 누락 등. 정의된 INVALID는 여기 해당하지 않는다(위에서 이미 처리).
                _server_log("POLICY_UNKNOWN_VERDICT", reservation_no=reservation_no,
                            slot_id=slot.get("id"), program=program_input, verdict=str(verdict))
                raise HTTPException(500, {
                    "code": "SLOT_POLICY_VALIDATION_FAILED",
                    "message": "예약 정책 검증 결과를 확인할 수 없습니다. 관리자에게 문의해 주세요.",
                })

            # 검증 순서(PM §4): 존재 확인 → 상태 확인 → Capacity 확인 → 중복 점유 확인.
            status = slot.get("status")
            if status not in _SLOT_ALLOWED_STATUSES:
                raise _slot_error(_SLOT_STATUS_ERROR_CODES.get(status, "SLOT_INVALID_STATE"))

            reserved = int(slot.get("reservedCount", 0) or 0)
            capacity = int(slot.get("capacity", 0) or 0)
            if reserved >= capacity:
                raise _slot_error("SLOT_FULL")

            # 동일 예약번호 중복 점유 방지(PM §5) — 같은 Slot이든 다른 Slot이든, 이미
            # 어딘가에 이 예약번호가 점유 기록으로 남아 있으면 새로 점유하지 않는다.
            # Sheets 상태가 이미 예약확정인 경우는 이 함수에 도달하기 전에 상태전이
            # 검증(§2)에서 이미 409로 걸러지므로, 여기 도달했다는 것은 Sheets는 아직
            # 예약접수인데 Slot에는 점유 흔적이 남은 불일치 상황이다 — 자동 정정하지
            # 않고 SLOT_RESERVATION_CONFLICT로 차단한다(PM 정책 B/C).
            if any(reservation_no in (s.get("sheetsReservationNos") or []) for s in slots):
                raise _slot_error("SLOT_RESERVATION_CONFLICT")

            new_count = reserved + 1
            full = new_count >= capacity
            nos = list(slot.get("sheetsReservationNos") or [])
            nos.append(reservation_no)
            engine._update_slot(data_dir, slot["id"], {  # noqa: SLF001 — 기존 구현 재사용(신규 Engine 금지)
                "reservedCount": new_count,
                "status": "FULL" if full else "AVAILABLE",
                "sheetsReservationNos": nos,
            })
            if full:
                audit.append_audit(data_dir, "SLOT_FULL", "Slot", slot["id"], user.get("id"),
                                   after={"status": "FULL", "reservedCount": new_count})
            return slot["id"]

    def _rollback_slot_reservation(slot_id: str, user: dict[str, Any], reservation_no: str) -> None:
        # Sheets 쓰기 실패 시 Slot 점유를 되돌린다. sheetsReservationNos 배열 정리와
        # 기존 _release_slot(정원 복구 + SLOT_RELEASED Audit) 호출을 하나의 DataLock
        # 보호 구간 안에서 처리한다(PM §7 — 원상복구가 원자적으로 이뤄지도록).
        with DataLock(data_dir):
            doc = read_doc(data_dir / "slots.json")
            slot = next((s for s in doc.get("records", []) if s.get("id") == slot_id), None)
            if slot is not None:
                nos = list(slot.get("sheetsReservationNos") or [])
                if reservation_no in nos:
                    nos.remove(reservation_no)
                    slot["sheetsReservationNos"] = nos
                    slot["updatedAt"] = now_iso()
                    write_doc(data_dir / "slots.json", doc)
            # PM §8: 보상 처리(Rollback)를 일반 예약취소와 명확히 구분한다. 기존
            # append_audit() 시그니처는 바꾸지 않고, note에 보상 처리임을 명시한다
            # (정상 취소 문구인 "{id} 취소로 Slot 복구"와 겹치지 않게 별도 표기).
            engine._release_slot(  # noqa: SLF001 — 기존 구현 재사용(신규 Engine 금지)
                data_dir, slot_id, user.get("id"), was_confirmed=True,
                note=f"[ROLLBACK/COMPENSATION] reservationNo={reservation_no} "
                     f"trigger=SHEETS_WRITE_FAILED — Sheets 쓰기 실패에 따른 보상 처리"
                     f"(일반 취소 아님, Slot 자동 해제)",
            )

    def _safe_rollback_slot(
        slot_id: str, user: dict[str, Any], reservation_no: str, original_error: Exception,
    ) -> None:
        # PM §9-B: Rollback 자체가 실패하면 일반 Audit 실패(§9-C, Best Effort 유지)보다
        # 심각하게 다룬다. 새 로깅 시스템은 도입하지 않는다(기존 코드베이스에 logging
        # 모듈 사용례가 없음을 확인함) — 원인을 그대로 메시지에 남겨 500으로 노출해
        # 운영자가 Slot 데이터를 직접 점검하도록 유도하는 것이 기존 관례(예외 전파)와
        # 가장 가깝다.
        try:
            _rollback_slot_reservation(slot_id, user, reservation_no)
        except Exception as rollback_exc:  # noqa: BLE001 — 의도적으로 광범위 포착(§9-B 정책)
            raise HTTPException(
                500,
                {"code": "SLOT_ROLLBACK_FAILED",
                 "message": f"Sheets 쓰기 실패({original_error}) 이후 Slot 롤백도 실패했습니다"
                            f"({rollback_exc}). Slot 데이터(slotId={slot_id})를 관리자가 직접 확인해야 합니다."},
            ) from rollback_exc

    # ── Sprint 4 Commit 2: 예약 승인/거절(Reservation Approval Foundation) ──
    # 대상은 Google Sheets 예약(SSOT, ADR-013)이며 로컬 JSON 예약(api_server.py의
    # /api/reservations/{rid}/approve 등)은 건드리지 않는다 — URL 네임스페이스가
    # 다르므로(/api/admin/reservations/* vs /api/reservations/*) 충돌 없음.
    def _process_reservation_approval(
        reservation_no: str, target_status: str, user: dict[str, Any], reason: str | None,
    ) -> dict[str, Any]:
        # 1) read — Sheets의 현재 상태를 승인/거절 직전에 다시 조회한다(가능한 범위의
        #    동시성 보호. GAS updateStatus는 compare-and-swap을 지원하지 않으므로 이
        #    read→validate→write로 경쟁 조건을 줄이되 완전히 없애지는 못한다 —
        #    Sprint4_Commit2_Implementation_Plan_v1.0.md §12-5 참조).
        try:
            current = sheets.get_reservation(reservation_no)
        except sheets.SheetsIntegrationNotConfigured as e:
            raise HTTPException(503, str(e)) from e
        except sheets.SheetsIntegrationError as e:
            raise HTTPException(502, str(e)) from e
        if current is None:
            raise HTTPException(404, f"예약번호 없음: {reservation_no}")

        current_status = current.get("status")

        # 2) validate — 예약접수 상태에서만 승인/거절 가능(PM 결정 1).
        try:
            approval_states.assert_can_transition(current_status, target_status)
        except approval_states.InvalidApprovalTransitionError as e:
            raise HTTPException(
                409,
                f"현재 상태({current_status})에서 처리할 수 없습니다 — 다른 사용자가 "
                "이미 처리했거나 승인/거절 대상 상태가 아닙니다.",
            ) from e

        # 3) Sprint 4 Commit 3 — 승인(예약확정)일 때만 Slot 조회·점유. Google Sheets
        #    쓰기 전에 Slot 확보가 끝나 있어야 한다(PM 원칙: Slot 확보 → Sheets 쓰기).
        slot_id: str | None = None
        if target_status == "예약확정":
            slot_id = _reserve_slot_for_approval(current, user)

        # 4) write — GAS 기존 updateStatus action만 사용(신규 action 없음, GAS 무수정).
        try:
            sheets_write.update_status(reservation_no, target_status)
        except sheets_write.SheetsIntegrationNotConfigured as e:
            if slot_id:
                _safe_rollback_slot(slot_id, user, reservation_no, e)
            raise HTTPException(503, str(e)) from e
        except sheets_write.SheetsIntegrationError as e:
            # Sheets 쓰기 실패 시 Slot Rollback(PM 필수 구현 사항).
            if slot_id:
                _safe_rollback_slot(slot_id, user, reservation_no, e)
            raise HTTPException(502, {"code": "SHEETS_WRITE_FAILED", "message": str(e)}) from e

        # Audit은 Sheets 상태 변경 성공 이후에만 기록한다(PM Audit 원칙, Commit 2부터
        # 유지). 기존 reservation_engine.py::approve_reservation()과 동일하게 "쓰기
        # 성공 → 감사기록" 순서이며, 감사기록 자체가 실패하는 경우의 보상 트랜잭션은
        # 기존 시스템에도 없으므로(Best Effort) 이번 Commit도 동일 정책을 따른다.
        event = "RESERVATION_APPROVED" if target_status == "예약확정" else "RESERVATION_REJECTED"
        after: dict[str, Any] = {"status": target_status}
        if slot_id:
            after["slotId"] = slot_id
        audit.append_audit(
            data_dir, event, "Reservation", reservation_no, user.get("id"),
            before={"status": current_status}, after=after,
            channel="ADMIN_PORTAL", note=reason,
        )

        return {
            "ok": True,
            "data": {
                "reservationNo": reservation_no,
                "previousStatus": current_status,
                "status": target_status,
                "slotId": slot_id,
                "processedBy": user.get("id"),
                "processedAt": now_iso(),
            },
        }

    @router.post("/reservations/{reservation_no}/approve")
    def approve_reservation(
        reservation_no: str, user: dict[str, Any] = Depends(require_reservation_approve),
        _csrf: dict[str, Any] = Depends(require_csrf_reservation_approve),
    ):
        """예약 승인(권한: reservation:approve) — 예약접수 → 예약확정만 허용."""
        return _process_reservation_approval(reservation_no, "예약확정", user, reason=None)

    @router.post("/reservations/{reservation_no}/reject")
    def reject_reservation(
        reservation_no: str, body: RejectReservationBody,
        user: dict[str, Any] = Depends(require_reservation_approve),
        _csrf: dict[str, Any] = Depends(require_csrf_reservation_approve),
    ):
        """예약 거절(권한: reservation:approve, 기존 reject_reservation()과 동일 권한 재사용)
        — 예약접수 → 거절만 허용. 거절 사유는 필수이며 Sheets에는 저장하지 않고
        Audit 로그에만 기록한다(PM 결정 2)."""
        return _process_reservation_approval(reservation_no, "거절", user, reason=body.reason)

    return router
