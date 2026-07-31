# -*- coding: utf-8 -*-
"""
CSHSP API Layer — Sprint D
FastAPI 기반 REST API. Sprint B Reservation Engine을 그대로 노출한다.

실행:
    cd CMC_Platform_new
    python -m uvicorn src.api.api_server:app --port 8600
    (데이터 폴더 변경: 환경변수 CSHSP_DATA_DIR)

인증(Sprint8 Commit8-2): 보호 엔드포인트는 SQLite 기반 서버 세션 Cookie를
    우선 검증한다(routes_auth.build_require_session_user). 세션이 없을 때만,
    그리고 CSHSP_ENV != production이고 CSHSP_ALLOW_MOCK_AUTH=1이 명시적으로
    설정된 경우에만 기존 X-User-Id Mock으로 대체 동작한다(기본값은 차단).
    권한은 여전히 roles.json 기준(has_perm/need_perm 무변경).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "core"))
sys.path.insert(0, str(_ROOT / "src" / "reservation"))
sys.path.insert(0, str(_ROOT / "src" / "questionnaire"))
sys.path.insert(0, str(_ROOT / "src" / "auth"))
sys.path.insert(0, str(_HERE))

from fastapi import Depends, FastAPI, Header, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import core_data_loader as loader  # noqa: E402
import data_validator  # noqa: E402
import reservation_engine as engine  # noqa: E402
import state_machine as sm  # noqa: E402
from alternative_slot_recommender import recommend_alternative_slots  # noqa: E402
from file_lock import DataLock  # noqa: E402
from json_store import next_seq, now_iso, read_doc, write_doc  # noqa: E402
from slot_generator import generate_slots  # noqa: E402
from routes_auth import (  # noqa: E402
    build_require_csrf, build_require_session_user, create_auth_router,
)

API_VERSION = "sprint-d-1.0"
FULL_DETAIL_ROLES = {"ROLE-ADMIN", "ROLE-STAFF", "ROLE-DIRECTOR"}
# admin_api.js live 모드가 사용하는 번들 Entity
BUNDLE_ENTITIES = ["Reservation", "Patient", "Program", "Slot", "Room", "Equipment",
                   "Doctor", "Nurse", "Schedule", "AuditLog", "User", "Role"]


# ── 개인정보 마스킹 (서버 측 — Sprint C Privacy 이관) ──
def mask_birth(b: str | None) -> str:
    return (str(b)[:4] + "****") if b else "-"


def mask_phone(p: str | None) -> str:
    import re
    m = re.match(r"^(\d{2,3})-?(\d{3,4})-?(\d{4})$", str(p or ""))
    return f"{m.group(1)}-****-{m.group(3)}" if m else ("***" if p else "-")


def masked_patient(p: dict[str, Any]) -> dict[str, Any]:
    q = dict(p)
    q["birthDate"] = mask_birth(p.get("birthDate"))
    q["phone"] = mask_phone(p.get("phone"))
    q.pop("email", None)
    return q


# ── 요청 모델 ──
class ReservationCreate(BaseModel):
    patientId: str
    programId: str
    requestedDate: str
    requestedTime: str
    slotId: str
    channel: str = "API"
    allowWaiting: bool = False
    memo: str | None = None


class ReasonBody(BaseModel):
    reason: str = ""


class ChangeBody(BaseModel):
    newSlotId: str
    newDate: str
    newTime: str
    reason: str = ""


class SlotGenerateBody(BaseModel):
    startDate: str
    endDate: str
    roomId: str = "ROOM-0001"
    capacity: int = 6


class QuestionnaireItem(BaseModel):
    code: str
    question: str
    answer: str | None = None
    detail: str | None = None


class QuestionnaireStart(BaseModel):
    patientId: str
    reservationId: str
    type: str = "PRE_CHECKUP"
    templateVersion: str = "v2026.1"
    items: list[QuestionnaireItem] = []


class QReviewBody(BaseModel):
    decision: str  # REVIEWED | REJECTED
    note: str = ""


class CrmNotificationBody(BaseModel):
    patientId: str
    reservationId: str | None = None
    type: str = "KAKAO"
    templateCode: str = "RSV_PENDING"
    content: str
    crmCategory: str = "예약문의"
    crmSummary: str | None = None


def create_app(data_dir: str | Path | None = None, include_agents: bool = True,
               agents_llm_client=None) -> FastAPI:
    """include_agents=False: 에이전트 내부(in-process) 클라이언트용 — 순환 생성 방지.
    agents_llm_client: 테스트용 ClaudeClient 주입. None이면 ANTHROPIC_API_KEY 감지 시 자동 생성."""
    DATA_DIR = Path(data_dir or os.environ.get("CSHSP_DATA_DIR") or (_ROOT / "data"))

    app = FastAPI(title="CSHSP API Layer", version=API_VERSION,
                  description="천안의료원 건강검진센터 AI 플랫폼 REST API (Sprint D)")
    app.state.cshsp_data_dir = DATA_DIR
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"], allow_headers=["*"],
        allow_credentials=True,  # Sprint8 Commit8-2: 세션 Cookie 전송에 필요
    )

    # Sprint8 Commit8-2: 관리자 인증(로그인/로그아웃/현재 사용자) 라우터
    app.include_router(create_auth_router(DATA_DIR))

    # Sprint F: 수검자 대면 채팅/본인확인/문진 제출 라우터
    # (오케스트레이터의 in-process API 클라이언트는 include_agents=False 앱을 생성 → 순환 방지)
    if include_agents:
        from routes_agents import create_agents_router
        llm = agents_llm_client
        if llm is None and os.environ.get("ANTHROPIC_API_KEY"):
            # Sprint H: Key 감지 → Claude tool_loop 기본 경로 (Key는 환경변수로만 관리)
            from claude_client import ClaudeClient
            llm = ClaudeClient()
        app.include_router(create_agents_router(DATA_DIR, llm_client=llm))

    # Sprint 1: Single Admin Portal 조회 전용 라우터(Enterprise_Architecture_ToBe_v1.0.md §4)
    # 기존 라우트/미들웨어/Startup은 변경하지 않고, routes_agents와 동일한 include_router
    # 패턴으로 신규 라우터만 등록한다.
    from routes_admin_portal import create_admin_portal_router, create_admin_namespace_router
    app.include_router(create_admin_portal_router(DATA_DIR))
    # Sprint 2: 신규 Endpoint 전용 Namespace(/api/admin/*, PM 결정사항 2) — 별도 라우터로 등록
    app.include_router(create_admin_namespace_router(DATA_DIR))

    # ── 인증/권한 (Sprint8 Commit8-2: 세션 우선, Mock은 명시적 환경설정 시에만) ──
    require_user = build_require_session_user(DATA_DIR)
    require_csrf = build_require_csrf(require_user)

    def has_perm(user: dict[str, Any], perm: str) -> bool:
        role = next((r for r in loader.load_entity("Role", DATA_DIR) if r.get("id") == user.get("roleId")), None)
        perms = (role or {}).get("permissions", [])
        return "*" in perms or perm in perms

    def need_perm(user: dict[str, Any], perm: str) -> None:
        if not has_perm(user, perm):
            raise HTTPException(403, f"권한 없음: {perm} 필요 (현재 역할 {user.get('roleId')})")

    def full_detail(user: dict[str, Any]) -> bool:
        return user.get("roleId") in FULL_DETAIL_ROLES

    def run_engine(fn, *args, **kwargs):
        """엔진 호출 공통 래퍼: 쓰기 잠금 + 예외 → HTTP 상태 매핑"""
        try:
            with DataLock(DATA_DIR):
                return fn(*args, data_dir=DATA_DIR, **kwargs)
        except engine.EnginePermissionError as e:
            raise HTTPException(403, str(e))
        except engine.NotFoundError as e:
            raise HTTPException(404, str(e))
        except sm.InvalidTransitionError as e:
            raise HTTPException(409, str(e))
        except engine.EngineError as e:
            raise HTTPException(400, str(e))

    # ── 기본 ──
    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": API_VERSION,
                "dataDir": str(DATA_DIR), "entities": loader.summary(DATA_DIR)}

    @app.get("/api/entities/bundle")
    def entities_bundle(user=Depends(require_user)):
        """admin_api.js live 모드용 일괄 조회 (개인정보는 역할 기반 마스킹)"""
        bundle = {e: loader.load_entity(e, DATA_DIR) for e in BUNDLE_ENTITIES}
        if not full_detail(user):
            bundle["Patient"] = [masked_patient(p) for p in bundle["Patient"]]
        return bundle

    # ── Reservation API ──
    @app.get("/api/reservations")
    def list_reservations(status: str = "", query: str = "", user=Depends(require_user)):
        need_perm(user, "reservation:view")
        patients = {p["id"]: p for p in loader.load_entity("Patient", DATA_DIR)}
        programs = {p["id"]: p for p in loader.load_entity("Program", DATA_DIR)}
        q = query.strip().lower()
        rows = []
        for r in loader.load_entity("Reservation", DATA_DIR):
            if status and r.get("status") != status:
                continue
            p = patients.get(r.get("patientId"), {})
            prog = programs.get(r.get("programId"), {})
            if q:
                last4 = str(p.get("phone", "")).replace("-", "")[-4:]
                hay = [r.get("id"), r.get("reservationNo"), p.get("name"),
                       prog.get("code"), prog.get("name"), r.get("reservationDate")]
                if not (any(q in str(v or "").lower() for v in hay) or last4 == q):
                    continue
            rows.append({**r, "patientName": p.get("name"),
                         "patientBirthMasked": mask_birth(p.get("birthDate")),
                         "patientPhoneMasked": mask_phone(p.get("phone")),
                         "programCode": prog.get("code")})
        rows.sort(key=lambda r: str(r.get("createdAt")), reverse=True)
        return {"count": len(rows), "records": rows}

    @app.get("/api/reservations/pending")
    def pending_reservations(user=Depends(require_user)):
        return list_reservations(status="PENDING_APPROVAL", query="", user=user)

    @app.get("/api/reservations/{rid}")
    def reservation_detail(rid: str, user=Depends(require_user)):
        need_perm(user, "reservation:view")
        rec = loader.get_by_id("Reservation", rid, DATA_DIR)
        if not rec:
            raise HTTPException(404, f"예약 없음: {rid}")
        patient = loader.get_by_id("Patient", rec.get("patientId"), DATA_DIR)
        if patient and not full_detail(user):
            patient = masked_patient(patient)
        return {
            "reservation": rec,
            "patient": patient,
            "program": loader.get_by_id("Program", rec.get("programId"), DATA_DIR),
            "slot": loader.get_by_id("Slot", rec.get("slotId"), DATA_DIR) if rec.get("slotId") else None,
            "auditTrail": sorted(
                [l for l in loader.load_entity("AuditLog", DATA_DIR)
                 if l.get("entityId") in (rid, rec.get("slotId"))],
                key=lambda l: str(l.get("timestamp"))),
            "allowedNext": sm.allowed_next(rec.get("status")),
        }

    @app.post("/api/reservations", status_code=201)
    def create_reservation(body: ReservationCreate, user=Depends(require_user)):
        result = run_engine(
            engine.create_reservation_request,
            body.patientId, body.programId, body.requestedDate, body.requestedTime,
            body.slotId, body.channel, user["id"],
            allow_waiting=body.allowWaiting, memo=body.memo)
        if not result["success"]:
            raise HTTPException(422, detail={"verdict": result["verdict"], "reasons": result["reasons"],
                                             "alternatives": result["alternatives"]})
        return result

    @app.post("/api/reservations/{rid}/approve")
    def approve(rid: str, user=Depends(require_user)):
        return {"success": True, "reservation": run_engine(engine.approve_reservation, rid, user["id"])}

    @app.post("/api/reservations/{rid}/reject")
    def reject(rid: str, body: ReasonBody, user=Depends(require_user)):
        return {"success": True, "reservation": run_engine(engine.reject_reservation, rid, user["id"], body.reason)}

    @app.post("/api/reservations/{rid}/cancel")
    def cancel(rid: str, body: ReasonBody, user=Depends(require_user)):
        return {"success": True, "reservation": run_engine(engine.cancel_reservation, rid, user["id"], body.reason)}

    @app.post("/api/reservations/{rid}/change")
    def change(rid: str, body: ChangeBody, user=Depends(require_user)):
        result = run_engine(engine.change_reservation, rid,
                            body.newSlotId, body.newDate, body.newTime, user["id"], body.reason)
        if not result["success"]:
            raise HTTPException(422, detail={"verdict": result["verdict"], "reasons": result["reasons"],
                                             "alternatives": result["alternatives"]})
        return result

    @app.post("/api/reservations/{rid}/no-show")
    def no_show(rid: str, user=Depends(require_user)):
        need_perm(user, "reservation:change")
        return {"success": True, "reservation": run_engine(engine.mark_no_show, rid, user["id"])}

    @app.post("/api/reservations/{rid}/complete")
    def complete(rid: str, user=Depends(require_user)):
        need_perm(user, "reservation:change")
        return {"success": True, "reservation": run_engine(engine.complete_reservation, rid, user["id"])}

    # ── Slot API ──
    @app.get("/api/slots")
    def list_slots(status: str = "", date_from: str = Query("", alias="from"),
                   date_to: str = Query("", alias="to"), user=Depends(require_user)):
        # Slot은 비개인정보 → 인증된 사용자 전체 조회 허용
        rows = [s for s in loader.load_entity("Slot", DATA_DIR)
                if (not status or s.get("status") == status)
                and (not date_from or s.get("date", "") >= date_from)
                and (not date_to or s.get("date", "") <= date_to)]
        rows.sort(key=lambda s: (s.get("date", ""), s.get("time", "")))
        return {"count": len(rows), "records": rows}

    @app.get("/api/slots/recommend")
    def recommend(date: str, time: str = "", programId: str = "", user=Depends(require_user)):
        return {"records": recommend_alternative_slots(
            date, time or None, programId or None, data_dir=DATA_DIR)}

    @app.post("/api/slots/generate", status_code=201)
    def slots_generate(body: SlotGenerateBody, user=Depends(require_user)):
        need_perm(user, "slot:manage")
        with DataLock(DATA_DIR):
            created = generate_slots(body.startDate, body.endDate, data_dir=DATA_DIR,
                                     room_id=body.roomId, capacity=body.capacity)
        return {"created": len(created), "records": created}

    @app.post("/api/slots/{slot_id}/release-hold")
    def slot_release_hold(slot_id: str, user=Depends(require_user)):
        return {"success": True, "slot": run_engine(engine.release_hold, slot_id, user["id"])}

    # ── Admin API (일정/사용자/역할 조회) ──
    @app.get("/api/admin/schedules")
    def schedules(tab: str = "", user=Depends(require_user)):
        records = loader.load_entity("Schedule", DATA_DIR)
        if tab == "holiday":
            records = [s for s in records if s.get("type") == "HOLIDAY"]
        elif tab:
            records = [s for s in records if s.get("type", "").lower() == tab.lower()]
        return {"count": len(records), "records": records}

    @app.get("/api/admin/users")
    def users(user=Depends(require_user)):
        return {"records": [{k: u.get(k) for k in ("id", "name", "roleId", "department", "status")}
                            for u in loader.load_entity("User", DATA_DIR)]}

    @app.get("/api/admin/roles")
    def roles(user=Depends(require_user)):
        return {"records": loader.load_entity("Role", DATA_DIR)}

    @app.get("/api/admin/validate")
    def validate(user=Depends(require_user)):
        result = data_validator.validate_all(loader.load_all(DATA_DIR))
        return {"pass": not result["errors"], **result}

    # ── Questionnaire / CRM API (Sprint E: AI Agent 연계) ──
    @app.post("/api/questionnaires/start", status_code=201)
    def questionnaire_start(body: QuestionnaireStart, user=Depends(require_user)):
        """사전문진 시작 — 응답 수집용 DRAFT 생성 (의료 판단 없음)"""
        if not loader.get_by_id("Patient", body.patientId, DATA_DIR):
            raise HTTPException(404, f"환자 없음: {body.patientId}")
        if not loader.get_by_id("Reservation", body.reservationId, DATA_DIR):
            raise HTTPException(404, f"예약 없음: {body.reservationId}")
        with DataLock(DATA_DIR):
            doc = read_doc(DATA_DIR / "questionnaires.json")
            seq = next_seq(doc["records"], r"QST-(\d+)")
            rec = {
                "id": f"QST-{seq:04d}",
                "patientId": body.patientId, "reservationId": body.reservationId,
                "type": body.type, "templateVersion": body.templateVersion,
                "items": [i.model_dump() for i in body.items],
                "status": "DRAFT", "submittedAt": None, "reviewedBy": None,
                "createdAt": now_iso(), "updatedAt": now_iso(),
            }
            doc["records"].append(rec)
            write_doc(DATA_DIR / "questionnaires.json", doc)
        return {"success": True, "questionnaire": rec}

    @app.post("/api/crm/notifications", status_code=201)
    def crm_notification(body: CrmNotificationBody, user=Depends(require_user)):
        """CRM 알림 생성 준비 — Notification PENDING 적재 (+선택적 CRM 기록)"""
        if not (has_perm(user, "notification:draft") or has_perm(user, "notification:send")):
            raise HTTPException(403, "권한 없음: notification:draft 또는 notification:send 필요")
        if not loader.get_by_id("Patient", body.patientId, DATA_DIR):
            raise HTTPException(404, f"환자 없음: {body.patientId}")
        with DataLock(DATA_DIR):
            ndoc = read_doc(DATA_DIR / "notifications.json")
            seq = next_seq(ndoc["records"], r"NTF-(\d+)")
            ntf = {
                "id": f"NTF-{seq:04d}", "type": body.type, "templateCode": body.templateCode,
                "patientId": body.patientId, "reservationId": body.reservationId,
                "scheduledAt": now_iso(), "sentAt": None, "content": body.content,
                "status": "PENDING", "createdAt": now_iso(), "updatedAt": now_iso(),
            }
            ndoc["records"].append(ntf)
            write_doc(DATA_DIR / "notifications.json", ndoc)
            crm_rec = None
            if body.crmSummary and (has_perm(user, "crm:log") or has_perm(user, "crm:manage")):
                cdoc = read_doc(DATA_DIR / "crm.json")
                cseq = next_seq(cdoc["records"], r"CRM-(\d+)")
                crm_rec = {
                    "id": f"CRM-{cseq:04d}", "patientId": body.patientId,
                    "reservationId": body.reservationId, "channel": "AI_CHAT",
                    "direction": "INBOUND", "category": body.crmCategory,
                    "summary": body.crmSummary, "handledBy": None, "followUpDate": None,
                    "status": "OPEN", "createdAt": now_iso(), "updatedAt": now_iso(),
                }
                cdoc["records"].append(crm_rec)
                write_doc(DATA_DIR / "crm.json", cdoc)
        return {"success": True, "notification": ntf, "crm": crm_rec}

    # ── Questionnaire 직원용: 목록 조회 + 검토 (Sprint F) ──
    @app.get("/api/questionnaires")
    def questionnaires(status: str = "", user=Depends(require_user)):
        need_perm(user, "patient:view")
        import questionnaire_service
        records = questionnaire_service.list_by_status(status, DATA_DIR)
        patients = {p["id"]: p for p in loader.load_entity("Patient", DATA_DIR)}
        out = []
        for r in records:
            p = patients.get(r.get("patientId"), {})
            out.append({**r, "patientName": p.get("name"),
                        "patientBirthMasked": mask_birth(p.get("birthDate"))})
        return {"count": len(out), "records": out}

    @app.post("/api/questionnaires/{qid}/review")
    def questionnaire_review(qid: str, body: QReviewBody, user=Depends(require_user)):
        need_perm(user, "patient:view")
        import questionnaire_service
        try:
            with DataLock(DATA_DIR):
                rec = questionnaire_service.review(qid, user["id"], body.decision, body.note, DATA_DIR)
        except questionnaire_service.QuestionnaireError as e:
            raise HTTPException(400, str(e))
        return {"success": True, "questionnaire": rec}

    # ── Dashboard API ──
    @app.get("/api/dashboard/kpi")
    def dashboard_kpi(today: str = "", user=Depends(require_user)):
        from datetime import date as _date
        today = today or _date.today().isoformat()
        R = loader.load_entity("Reservation", DATA_DIR)
        slots = [s for s in loader.load_entity("Slot", DATA_DIR) if s.get("status") != "BLOCKED"]
        cap = sum(s.get("capacity", 0) for s in slots)
        reserved = sum(s.get("reservedCount", 0) for s in slots)
        online = sum(1 for r in R if r.get("channel") in ("WEB", "AI_ASSISTANT"))
        by = lambda st: sum(1 for r in R if r.get("status") == st)  # noqa: E731
        return {
            "date": today,
            "todayRequested": sum(1 for r in R if str(r.get("requestedAt") or r.get("createdAt", "")).startswith(today)),
            "pending": by("PENDING_APPROVAL"), "confirmed": by("CONFIRMED"),
            "cancelled": by("CANCELLED"), "noShow": by("NO_SHOW"), "waiting": by("WAITING"),
            "slotUtilization": round(reserved / cap * 100, 1) if cap else 0,
            "onlineRatio": round(online / len(R) * 100, 1) if R else 0,
        }

    @app.get("/api/dashboard/ai")
    def dashboard_ai(user=Depends(require_user)):
        """AI 상담 통계 (Sprint G) — 총 상담/전환/차단/본인확인/문진/상담원/시간대별"""
        sys.path.insert(0, str(_ROOT / "src" / "dashboard"))
        from ai_metrics import compute_ai_metrics
        return compute_ai_metrics(DATA_DIR)

    # ── Audit Log API ──
    @app.get("/api/audit-logs")
    def audit_logs(action: str = "", query: str = "", date: str = "",
                   limit: int = 200, user=Depends(require_user)):
        if not (has_perm(user, "audit:view") or has_perm(user, "reservation:view")):
            raise HTTPException(403, "권한 없음: audit:view 또는 reservation:view 필요")
        q = query.strip().lower()
        rows = [l for l in loader.load_entity("AuditLog", DATA_DIR)
                if (not action or l.get("action") == action)
                and (not date or str(l.get("timestamp", "")).startswith(date))
                and (not q or any(q in str(l.get(f) or "").lower()
                                  for f in ("entityId", "actorUserId", "action", "note")))]
        rows.sort(key=lambda l: str(l.get("timestamp")), reverse=True)
        return {"count": len(rows), "records": rows[:limit]}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8600)
