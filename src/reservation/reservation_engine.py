# -*- coding: utf-8 -*-
"""
CSHSP Reservation Engine — Sprint B
천안의료원 건강검진센터 예약 판단 엔진

원칙:
- AI는 예약을 직접 확정하지 않는다. 신청은 PENDING_APPROVAL로 생성되고
  직원 승인(reservation:approve 권한) 후에만 CONFIRMED가 된다.
- 모든 예약은 이 엔진을 통과해야 하며, 모든 이벤트는 audit_logs.json에 기록된다.
- Sprint A의 Core Data Loader / 상태 표준을 재사용한다.
- 의료 판단 기능은 포함하지 않는다.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[0] / "core"))
sys.path.insert(0, str(_HERE))

import core_data_loader as loader  # noqa: E402
import reservation_audit as audit  # noqa: E402
import state_machine as sm  # noqa: E402
from alternative_slot_recommender import recommend_alternative_slots  # noqa: E402
from json_store import next_seq, now_iso, read_doc, today_ymd, write_doc  # noqa: E402

WEEKDAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 중복예약 판단 시 '살아있는' 예약으로 보는 상태
ACTIVE_STATUSES = {"REQUESTED", "PENDING_APPROVAL", "CONFIRMED", "WAITING", "CHANGED"}
OPERATING_START, OPERATING_END = "08:00", "17:00"  # 검사실 운영시간


class EngineError(Exception):
    """Reservation Engine 공통 예외"""


class EnginePermissionError(EngineError):
    """권한 없음"""


class NotFoundError(EngineError):
    """대상 레코드 없음"""


# ── 내부 헬퍼 ──────────────────────────────────────────────

def _dir(data_dir: Path | str | None) -> Path:
    return Path(data_dir) if data_dir else loader.DATA_DIR


def _weekday(date_str: str) -> str:
    return WEEKDAY[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


def _find(records: list[dict], rec_id: str) -> dict | None:
    return next((r for r in records if r.get("id") == rec_id), None)


def _has_permission(user_id: str, perm: str, data_dir: Path) -> bool:
    user = _find(loader.load_entity("User", data_dir), user_id)
    if not user or user.get("status") != "ACTIVE":
        return False
    role = _find(loader.load_entity("Role", data_dir), user.get("roleId"))
    perms = role.get("permissions", []) if role else []
    return "*" in perms or perm in perms


def _check_requester(requested_by: str, data_dir: Path) -> None:
    """USR- 계정이면 예약 신청 권한 필요. 그 외(수검자 본인 채널)는 허용."""
    if str(requested_by).startswith("USR-"):
        if not (_has_permission(requested_by, "reservation:request", data_dir)
                or _has_permission(requested_by, "reservation:approve", data_dir)):
            raise EnginePermissionError(f"예약 신청 권한 없음: {requested_by}")


def _assert_transition(rec: dict, target: str, actor: str, data_dir: Path) -> None:
    """상태 전이 검증. 실패 시 INVALID_TRANSITION 감사기록 후 예외."""
    try:
        sm.assert_transition(rec.get("status"), target)
    except sm.InvalidTransitionError as e:
        audit.append_audit(
            data_dir, "INVALID_TRANSITION", "Reservation", rec.get("id"), actor,
            before={"status": rec.get("status")}, after={"status": target}, note=str(e),
        )
        raise


def _update_slot(data_dir: Path, slot_id: str, updates: dict) -> dict | None:
    doc = read_doc(data_dir / "slots.json")
    slot = _find(doc["records"], slot_id)
    if slot is None:
        return None
    slot.update(updates)
    slot["updatedAt"] = now_iso()
    write_doc(data_dir / "slots.json", doc)
    return slot


def _release_slot(data_dir: Path, slot_id: str, actor: str, was_confirmed: bool, note: str) -> None:
    """Slot 점유 해제: 확정분이면 정원 반환, 상태는 정원 기준으로 복구."""
    doc = read_doc(data_dir / "slots.json")
    slot = _find(doc["records"], slot_id)
    if slot is None:
        return
    before = {"status": slot.get("status"), "reservedCount": slot.get("reservedCount")}
    if was_confirmed and int(slot.get("reservedCount", 0)) > 0:
        slot["reservedCount"] = int(slot["reservedCount"]) - 1
    slot["status"] = "AVAILABLE" if int(slot.get("reservedCount", 0)) < int(slot.get("capacity", 0)) else "FULL"
    slot.pop("holdReason", None)
    slot["updatedAt"] = now_iso()
    write_doc(data_dir / "slots.json", doc)
    audit.append_audit(data_dir, "SLOT_RELEASED", "Slot", slot_id, actor,
                       before=before, after={"status": slot["status"], "reservedCount": slot.get("reservedCount")},
                       note=note)


def _queue_notification(data_dir: Path, reservation: dict, template_code: str, content: str) -> dict:
    """승인 등 이벤트에 대한 Notification 생성 준비 (PENDING 큐 적재)."""
    doc = read_doc(data_dir / "notifications.json")
    seq = next_seq(doc["records"], r"NTF-(\d+)")
    rec = {
        "id": f"NTF-{seq:04d}",
        "type": "KAKAO",
        "templateCode": template_code,
        "patientId": reservation.get("patientId"),
        "reservationId": reservation.get("id"),
        "scheduledAt": now_iso(),
        "sentAt": None,
        "content": content,
        "status": "PENDING",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    doc["records"].append(rec)
    write_doc(data_dir / "notifications.json", doc)
    return rec


# ── 3. Slot 검증 ──────────────────────────────────────────

# Sprint 4 Commit 5-1(Validation Context): validate_slot()의 호출 목적에 따라
# 일부 검사를 명시적으로 건너뛸 수 있게 한다. 새 Policy Engine이 아니라 기존
# 함수의 최소 파라미터화다 — 컨텍스트별로 끌 검사 이름의 집합만 사전 정의해 두고,
# 함수 본문에서는 "이 검사가 disabled_checks에 있는가"만 확인한다.
# 기본값(slot_generation)은 기존 호출부(create_reservation_request/
# change_reservation)와 100% 동일하게 전체 검사를 수행한다 — 하위 호환 보장.
#
# PM 최종 정책(Commit 5-1 보완): PATIENT_DUPLICATE 검사를 명시적으로 제외하는
# 컨텍스트는 reservation_approval 단 하나뿐이다. simulation은 slot_generation과
# 동일하게 전체 검사를 수행한다(dry-run 조회라도 환자 중복 여부는 그대로 알려줘야
# 의미가 있으므로) — reservation_approval과 동일 취급했던 이전 구현은 PM 승인
# 설계와 달랐다.
# 알 수 없는 컨텍스트 문자열이 전달되면 아래 dict.get() 기본값(빈 집합)에 의해
# 전체 검사가 수행된다 — 이는 "실패 시 차단"이 아니라 "정의되지 않은 컨텍스트는
# 이미 검증된 가장 안전한 동작(전체 검사)으로 처리한다"는 Safe Default다.
_CONTEXT_DISABLED_CHECKS: dict[str, frozenset[str]] = {
    "slot_generation": frozenset(),                             # 전체 검사(기존 동작 그대로)
    "reservation_approval": frozenset({"PATIENT_DUPLICATE"}),    # Sheets 예약 승인(Commit5) — 환자 식별자가 구조적으로 없음, 이 검사만 제외
    "simulation": frozenset(),                                   # 전체 검사(PM 최종 정책 — slot_generation과 동일)
}


def resolve_program(program_input: str | None, data_dir: Path | str | None = None) -> dict[str, Any] | None:
    """Sprint 4 Commit 5-1(Program Mapping Helper): 문자열(코드 또는 이름)을
    Program Entity로 매핑한다. 새 Repository/ORM/Service Layer를 만들지 않고
    기존 loader.load_entity("Program")만 재사용한다.

    매칭 순서: Program.code 완전일치 → 실패 시 Program.name 완전일치 → 실패 시 None.
    Fuzzy/부분일치는 하지 않는다(Health Check에서 확인된 '온김에검진' 사례처럼
    code가 아니라 name과만 일치하는 프로그램이 있어 2단계 매칭이 필요하다).
    매핑 실패를 예외로 취급하지 않는다 — 호출자가 실패 처리 정책(Fail Closed 등)을
    결정한다.
    """
    if not program_input:
        return None
    data_dir = _dir(data_dir)
    programs = loader.load_entity("Program", data_dir)
    for p in programs:
        if p.get("code") == program_input:
            return p
    for p in programs:
        if p.get("name") == program_input:
            return p
    return None


def validate_slot(
    slot_id: str,
    patient_id: str,
    requested_date: str,
    data_dir: Path | str | None = None,
    program_id: str | None = None,
    exclude_reservation_id: str | None = None,
    validation_context: str = "slot_generation",
) -> dict[str, Any]:
    """예약 가능 여부 판단.

    반환: {"verdict": AVAILABLE|FULL|WAITING|DUPLICATED|HOLD|BLOCKED|INVALID,
           "reasons": [...], "slot": 슬롯레코드|None}

    validation_context(Sprint 4 Commit 5-1, PM 최종 정책): "slot_generation"(기본값)
    / "reservation_approval" / "simulation" 중 하나. 이 중 "reservation_approval"만
    환자 동일일자 중복 검사(PATIENT_DUPLICATE)를 명시적으로 건너뛴다(Sheets 예약
    승인 시 환자 식별자가 구조적으로 없기 때문). "slot_generation"과 "simulation"은
    둘 다 전체 검사를 수행한다 — simulation도 dry-run 조회일 뿐 환자 중복 여부를
    숨기지 않는다. 그 외 모든 검사(공휴일/Slot상태/의료진/검사실/운영시간/장비/
    정원 등)는 컨텍스트와 무관하게 항상 수행된다.

    알 수 없는 컨텍스트 문자열이 전달되면 _CONTEXT_DISABLED_CHECKS.get()의 기본값
    (빈 집합)에 의해 전체 검사가 수행된다 — Safe Default: 정의되지 않은 컨텍스트는
    검증이 완화되지 않은, 이미 검증된 가장 안전한 동작(slot_generation과 동일한
    전체 검사)으로 처리된다.
    """
    data_dir = _dir(data_dir)
    disabled_checks = _CONTEXT_DISABLED_CHECKS.get(validation_context, frozenset())

    def result(verdict: str, reason: str, slot: dict | None = None):
        return {"verdict": verdict, "reasons": [reason], "slot": slot}

    # 날짜 형식 / Slot 존재
    if not DATE_RE.match(str(requested_date)):
        return result("INVALID", f"날짜 형식 오류: {requested_date}")
    slot = _find(loader.load_entity("Slot", data_dir), slot_id)
    if slot is None:
        return result("INVALID", f"존재하지 않는 Slot: {slot_id}")
    if slot.get("date") != requested_date:
        return result("INVALID", f"Slot 날짜 불일치: 요청 {requested_date} / Slot {slot.get('date')}", slot)
    if slot.get("programRestriction") and program_id and slot["programRestriction"] != program_id:
        return result("INVALID", f"프로그램 제한 슬롯: {slot['programRestriction']} 전용", slot)

    # 공휴일 / 병원 휴진일
    schedules = loader.load_entity("Schedule", data_dir)
    for sch in schedules:
        if sch.get("date") == requested_date and sch.get("type") == "HOLIDAY" and sch.get("status") == "BLOCKED":
            return result("BLOCKED", f"휴진일: {sch.get('note') or requested_date}", slot)

    # Slot 자체 상태
    if slot.get("status") == "BLOCKED":
        return result("BLOCKED", f"차단된 Slot: {slot.get('blockReason') or slot_id}", slot)
    if slot.get("status") == "HOLD":
        return result("HOLD", f"보류 중 Slot: {slot.get('holdReason') or slot_id}", slot)

    # 동일 환자 동일일자 중복예약 (Sprint 4 Commit 5-1: validation_context로 건너뛸 수 있음)
    if "PATIENT_DUPLICATE" not in disabled_checks:
        for r in loader.load_entity("Reservation", data_dir):
            if (r.get("patientId") == patient_id
                    and r.get("reservationDate") == requested_date
                    and r.get("status") in ACTIVE_STATUSES
                    and r.get("id") != exclude_reservation_id):
                return result("DUPLICATED", f"동일 환자 동일일자 예약 존재: {r['id']} ({r['status']})", slot)

    # 자원 검증: 당일 BLOCKED 처리된 자원 목록
    blocked_refs = {sch.get("refId") for sch in schedules
                    if sch.get("date") == requested_date and sch.get("status") == "BLOCKED"}
    wd = _weekday(requested_date)

    # 담당의 / 간호사 근무 가능 여부
    doctors = [d for d in loader.load_entity("Doctor", data_dir)
               if d.get("status") == "ACTIVE" and wd in d.get("workDays", []) and d["id"] not in blocked_refs]
    if not doctors:
        return result("BLOCKED", f"{requested_date}({wd}) 근무 가능 의사 없음", slot)
    nurses = [n for n in loader.load_entity("Nurse", data_dir)
              if n.get("status") == "ACTIVE" and wd in n.get("workDays", []) and n["id"] not in blocked_refs]
    if not nurses:
        return result("BLOCKED", f"{requested_date}({wd}) 근무 가능 간호사 없음", slot)

    # 검사실 운영 여부 + 운영시간
    room = _find(loader.load_entity("Room", data_dir), slot.get("roomId"))
    if room is None or room.get("status") != "ACTIVE" or room.get("id") in blocked_refs:
        return result("BLOCKED", f"검사실 운영 불가: {slot.get('roomId')}", slot)
    if not (OPERATING_START <= str(slot.get("time")) <= OPERATING_END):
        return result("BLOCKED", f"운영시간({OPERATING_START}~{OPERATING_END}) 외 Slot: {slot.get('time')}", slot)

    # 해당 검사실 장비 사용 가능 여부
    for eq in loader.load_entity("Equipment", data_dir):
        if eq.get("roomId") == room["id"] and (eq.get("status") != "ACTIVE" or eq["id"] in blocked_refs):
            return result("BLOCKED", f"장비 사용 불가: {eq.get('name')} ({eq.get('status')})", slot)

    # 정원
    if slot.get("status") == "FULL" or int(slot.get("reservedCount", 0)) >= int(slot.get("capacity", 0)):
        return result("FULL", f"정원 마감: {slot.get('reservedCount')}/{slot.get('capacity')}", slot)
    if slot.get("status") == "WAITING":
        return result("WAITING", "대기예약 접수 중인 Slot", slot)
    if slot.get("status") == "DUPLICATED":
        return result("DUPLICATED", "중복 감지 상태 Slot (직원 확인 필요)", slot)
    if slot.get("status") == "AVAILABLE":
        return {"verdict": "AVAILABLE", "reasons": ["예약 가능"], "slot": slot}
    return result("INVALID", f"알 수 없는 Slot 상태: {slot.get('status')}", slot)


# ── 4. 예약 신청 ──────────────────────────────────────────

def create_reservation_request(
    patient_id: str,
    program_id: str,
    requested_date: str,
    requested_time: str,
    slot_id: str,
    channel: str,
    requested_by: str,
    data_dir: Path | str | None = None,
    allow_waiting: bool = False,
    memo: str | None = None,
) -> dict[str, Any]:
    """예약 신청. 성공 시 PENDING_APPROVAL 예약 생성 + Slot HOLD.

    반환: {"success", "verdict", "reservation", "reasons", "alternatives"}
    """
    data_dir = _dir(data_dir)
    _check_requester(requested_by, data_dir)

    def fail(verdict: str, reasons: list[str]):
        return {
            "success": False, "verdict": verdict, "reservation": None, "reasons": reasons,
            "alternatives": recommend_alternative_slots(
                requested_date, requested_time, program_id,
                data_dir=data_dir, exclude_slot_ids={slot_id}),
        }

    # 환자 / 프로그램 존재 확인
    if _find(loader.load_entity("Patient", data_dir), patient_id) is None:
        return fail("INVALID", [f"존재하지 않는 환자: {patient_id}"])
    if _find(loader.load_entity("Program", data_dir), program_id) is None:
        return fail("INVALID", [f"존재하지 않는 프로그램: {program_id}"])

    v = validate_slot(slot_id, patient_id, requested_date, data_dir, program_id)

    if v["verdict"] == "DUPLICATED":
        audit.append_audit(data_dir, "DUPLICATED_REJECTED", "Reservation", None, requested_by,
                           after={"patientId": patient_id, "requestedDate": requested_date, "slotId": slot_id},
                           channel=channel, note="; ".join(v["reasons"]))
        return fail("DUPLICATED", v["reasons"])

    waiting_mode = v["verdict"] == "FULL" and allow_waiting
    if v["verdict"] != "AVAILABLE" and not waiting_mode:
        return fail(v["verdict"], v["reasons"])

    # 예약번호 채번: YYYYMMDD-0001 (당일 순번, 기존 id와 충돌 방지)
    res_doc = read_doc(data_dir / "reservations.json")
    ymd = today_ymd()
    seq = next_seq(res_doc["records"], rf"(?:RSV-)?{ymd}-(\d{{4}})")
    reservation_no = f"{ymd}-{seq:04d}"

    status = "WAITING" if waiting_mode else "PENDING_APPROVAL"
    rec: dict[str, Any] = {
        "id": f"RSV-{reservation_no}",
        "reservationNo": reservation_no,
        "patientId": patient_id,
        "programId": program_id,
        "businessId": None,
        "reservationDate": requested_date,
        "slotId": slot_id,
        "wishTime": requested_time,
        "status": status,
        "optionalTestIds": [],
        "sleepEndoscopy": False,
        "channel": channel,
        "requestedAt": now_iso(),
        "requestedBy": requested_by,
        "approvedBy": None,
        "approvedAt": None,
        "changeHistory": [],
        "cancelReason": None,
        "memo": memo,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    res_doc["records"].append(rec)
    write_doc(data_dir / "reservations.json", res_doc)

    if waiting_mode:
        slot = _update_slot(data_dir, slot_id, {
            "status": "WAITING",
            "waitingCount": int(v["slot"].get("waitingCount", 0)) + 1,
        })
        audit.append_audit(data_dir, "RESERVATION_REQUESTED", "Reservation", rec["id"], requested_by,
                           after={"status": status, "slotId": slot_id}, channel=channel,
                           note="정원 마감 → 대기예약 접수")
        return {"success": True, "verdict": "WAITING", "reservation": rec,
                "reasons": ["정원 마감으로 대기예약 접수"], "alternatives": []}

    _update_slot(data_dir, slot_id, {"status": "HOLD", "holdReason": f"예약 승인 대기 ({rec['id']})"})
    audit.append_audit(data_dir, "RESERVATION_REQUESTED", "Reservation", rec["id"], requested_by,
                       after={"status": status, "patientId": patient_id, "slotId": slot_id},
                       channel=channel)
    audit.append_audit(data_dir, "SLOT_HELD", "Slot", slot_id, requested_by,
                       before={"status": "AVAILABLE"}, after={"status": "HOLD"},
                       note=f"{rec['id']} 승인 대기")
    return {"success": True, "verdict": "AVAILABLE", "reservation": rec, "reasons": ["신청 완료 (직원 승인 대기)"], "alternatives": []}


# ── 5. 직원 승인 ──────────────────────────────────────────

def approve_reservation(reservation_id: str, approver_user_id: str,
                        data_dir: Path | str | None = None) -> dict[str, Any]:
    """직원 승인: PENDING_APPROVAL → CONFIRMED, Slot 점유 확정."""
    data_dir = _dir(data_dir)
    if not _has_permission(approver_user_id, "reservation:approve", data_dir):
        raise EnginePermissionError(f"승인 권한 없음: {approver_user_id} (reservation:approve 필요)")

    doc = read_doc(data_dir / "reservations.json")
    rec = _find(doc["records"], reservation_id)
    if rec is None:
        raise NotFoundError(f"예약 없음: {reservation_id}")
    _assert_transition(rec, "CONFIRMED", approver_user_id, data_dir)

    before_status = rec["status"]
    rec.update({"status": "CONFIRMED", "approvedBy": approver_user_id,
                "approvedAt": now_iso(), "updatedAt": now_iso()})
    write_doc(data_dir / "reservations.json", doc)

    # Slot 점유 확정: 정원 도달 시 FULL, 미달 시 AVAILABLE 복귀 (정원 기반 구현)
    slot_doc = read_doc(data_dir / "slots.json")
    slot = _find(slot_doc["records"], rec.get("slotId"))
    if slot is not None:
        slot["reservedCount"] = int(slot.get("reservedCount", 0)) + 1
        full = int(slot["reservedCount"]) >= int(slot.get("capacity", 0))
        slot["status"] = "FULL" if full else "AVAILABLE"
        slot.pop("holdReason", None)
        slot["updatedAt"] = now_iso()
        write_doc(data_dir / "slots.json", slot_doc)
        if full:
            audit.append_audit(data_dir, "SLOT_FULL", "Slot", slot["id"], approver_user_id,
                               after={"status": "FULL", "reservedCount": slot["reservedCount"]})

    audit.append_audit(data_dir, "RESERVATION_APPROVED", "Reservation", reservation_id, approver_user_id,
                       before={"status": before_status}, after={"status": "CONFIRMED"})

    program = _find(loader.load_entity("Program", data_dir), rec.get("programId"))
    _queue_notification(
        data_dir, rec, "RSV_CONFIRMED",
        f"[천안의료원] {rec.get('reservationDate')} {rec.get('wishTime')} "
        f"{(program or {}).get('name', rec.get('programId'))} 예약이 확정되었습니다.",
    )
    return rec


# ── 6. 예약 취소 ──────────────────────────────────────────

def cancel_reservation(reservation_id: str, actor_user_id: str, reason: str = "",
                       data_dir: Path | str | None = None) -> dict[str, Any]:
    """예약 취소: 취소 가능 상태 확인 → CANCELLED, Slot 복구."""
    data_dir = _dir(data_dir)
    if str(actor_user_id).startswith("USR-") and not _has_permission(actor_user_id, "reservation:cancel", data_dir):
        raise EnginePermissionError(f"취소 권한 없음: {actor_user_id}")

    doc = read_doc(data_dir / "reservations.json")
    rec = _find(doc["records"], reservation_id)
    if rec is None:
        raise NotFoundError(f"예약 없음: {reservation_id}")
    _assert_transition(rec, "CANCELLED", actor_user_id, data_dir)

    before_status = rec["status"]
    rec.update({"status": "CANCELLED", "cancelReason": reason or None, "updatedAt": now_iso()})
    write_doc(data_dir / "reservations.json", doc)

    if rec.get("slotId"):
        _release_slot(data_dir, rec["slotId"], actor_user_id,
                      was_confirmed=(before_status == "CONFIRMED"),
                      note=f"{reservation_id} 취소로 Slot 복구")

    audit.append_audit(data_dir, "RESERVATION_CANCELLED", "Reservation", reservation_id, actor_user_id,
                       before={"status": before_status}, after={"status": "CANCELLED"}, note=reason or None)
    return rec


# ── 예약 거절 ────────────────────────────────────────────

def reject_reservation(reservation_id: str, actor_user_id: str, reason: str = "",
                       data_dir: Path | str | None = None) -> dict[str, Any]:
    """직원 거절: REQUESTED/PENDING_APPROVAL → REJECTED, Slot 복구."""
    data_dir = _dir(data_dir)
    if not _has_permission(actor_user_id, "reservation:approve", data_dir):
        raise EnginePermissionError(f"거절 권한 없음: {actor_user_id} (reservation:approve 필요)")

    doc = read_doc(data_dir / "reservations.json")
    rec = _find(doc["records"], reservation_id)
    if rec is None:
        raise NotFoundError(f"예약 없음: {reservation_id}")
    _assert_transition(rec, "REJECTED", actor_user_id, data_dir)

    before_status = rec["status"]
    rec.update({"status": "REJECTED", "cancelReason": reason or None, "updatedAt": now_iso()})
    write_doc(data_dir / "reservations.json", doc)

    if rec.get("slotId"):
        _release_slot(data_dir, rec["slotId"], actor_user_id, was_confirmed=False,
                      note=f"{reservation_id} 거절로 Slot 복구")

    audit.append_audit(data_dir, "RESERVATION_REJECTED", "Reservation", reservation_id, actor_user_id,
                       before={"status": before_status}, after={"status": "REJECTED"}, note=reason or None)
    return rec


# ── 예약 변경 (CONFIRMED → CHANGED → PENDING_APPROVAL) ───

def change_reservation(reservation_id: str, new_slot_id: str, new_date: str, new_time: str,
                       actor_user_id: str, reason: str = "",
                       data_dir: Path | str | None = None) -> dict[str, Any]:
    """확정 예약 변경. 새 Slot 검증 통과 시에만 진행하며 재승인 대기로 전환."""
    data_dir = _dir(data_dir)
    if str(actor_user_id).startswith("USR-") and not _has_permission(actor_user_id, "reservation:change", data_dir):
        raise EnginePermissionError(f"변경 권한 없음: {actor_user_id}")

    doc = read_doc(data_dir / "reservations.json")
    rec = _find(doc["records"], reservation_id)
    if rec is None:
        raise NotFoundError(f"예약 없음: {reservation_id}")
    _assert_transition(rec, "CHANGED", actor_user_id, data_dir)

    v = validate_slot(new_slot_id, rec["patientId"], new_date, data_dir,
                      rec.get("programId"), exclude_reservation_id=reservation_id)
    if v["verdict"] != "AVAILABLE":
        return {"success": False, "verdict": v["verdict"], "reservation": rec, "reasons": v["reasons"],
                "alternatives": recommend_alternative_slots(new_date, new_time, rec.get("programId"),
                                                            data_dir=data_dir, exclude_slot_ids={new_slot_id})}

    old = {"slotId": rec.get("slotId"), "reservationDate": rec.get("reservationDate"), "wishTime": rec.get("wishTime")}
    if old["slotId"]:
        _release_slot(data_dir, old["slotId"], actor_user_id, was_confirmed=True,
                      note=f"{reservation_id} 변경으로 기존 Slot 복구")

    rec.setdefault("changeHistory", []).append({
        "changedAt": now_iso(), "changedBy": actor_user_id,
        "before": old, "after": {"slotId": new_slot_id, "reservationDate": new_date, "wishTime": new_time},
        "reason": reason or None,
    })
    rec.update({"slotId": new_slot_id, "reservationDate": new_date, "wishTime": new_time,
                "status": "PENDING_APPROVAL", "approvedBy": None, "approvedAt": None, "updatedAt": now_iso()})
    write_doc(data_dir / "reservations.json", doc)

    _update_slot(data_dir, new_slot_id, {"status": "HOLD", "holdReason": f"예약 변경 재승인 대기 ({reservation_id})"})
    audit.append_audit(data_dir, "RESERVATION_CHANGED", "Reservation", reservation_id, actor_user_id,
                       before=old, after={"slotId": new_slot_id, "reservationDate": new_date, "wishTime": new_time},
                       note="변경 후 재승인 대기(PENDING_APPROVAL) 전환")
    audit.append_audit(data_dir, "SLOT_HELD", "Slot", new_slot_id, actor_user_id,
                       before={"status": "AVAILABLE"}, after={"status": "HOLD"},
                       note=f"{reservation_id} 변경 재승인 대기")
    return {"success": True, "verdict": "AVAILABLE", "reservation": rec,
            "reasons": ["변경 완료 (재승인 대기)"], "alternatives": []}


# ── 노쇼 / 완료 처리 ─────────────────────────────────────

def mark_no_show(reservation_id: str, actor_user_id: str,
                 data_dir: Path | str | None = None) -> dict[str, Any]:
    """노쇼 처리: CONFIRMED 상태에서만 가능."""
    data_dir = _dir(data_dir)
    doc = read_doc(data_dir / "reservations.json")
    rec = _find(doc["records"], reservation_id)
    if rec is None:
        raise NotFoundError(f"예약 없음: {reservation_id}")
    _assert_transition(rec, "NO_SHOW", actor_user_id, data_dir)
    before_status = rec["status"]
    rec.update({"status": "NO_SHOW", "noShowAt": now_iso(), "updatedAt": now_iso()})
    write_doc(data_dir / "reservations.json", doc)
    audit.append_audit(data_dir, "RESERVATION_NO_SHOW", "Reservation", reservation_id, actor_user_id,
                       before={"status": before_status}, after={"status": "NO_SHOW"})
    return rec


def release_hold(slot_id: str, actor_user_id: str,
                 data_dir: Path | str | None = None) -> dict[str, Any]:
    """HOLD Slot 수동 해제 (slot:manage 권한). Sprint D 추가."""
    data_dir = _dir(data_dir)
    if not _has_permission(actor_user_id, "slot:manage", data_dir):
        raise EnginePermissionError(f"Slot 관리 권한 없음: {actor_user_id} (slot:manage 필요)")
    slot = _find(loader.load_entity("Slot", data_dir), slot_id)
    if slot is None:
        raise NotFoundError(f"Slot 없음: {slot_id}")
    if slot.get("status") != "HOLD":
        raise EngineError(f"HOLD 상태가 아님: {slot_id} ({slot.get('status')})")
    _release_slot(data_dir, slot_id, actor_user_id, was_confirmed=False, note="HOLD 수동 해제")
    return _find(loader.load_entity("Slot", data_dir), slot_id)


def complete_reservation(reservation_id: str, actor_user_id: str,
                         data_dir: Path | str | None = None) -> dict[str, Any]:
    """검진 완료 처리: CONFIRMED → COMPLETED."""
    data_dir = _dir(data_dir)
    doc = read_doc(data_dir / "reservations.json")
    rec = _find(doc["records"], reservation_id)
    if rec is None:
        raise NotFoundError(f"예약 없음: {reservation_id}")
    _assert_transition(rec, "COMPLETED", actor_user_id, data_dir)
    before_status = rec["status"]
    rec.update({"status": "COMPLETED", "updatedAt": now_iso()})
    write_doc(data_dir / "reservations.json", doc)
    audit.append_audit(data_dir, "RESERVATION_COMPLETED", "Reservation", reservation_id, actor_user_id,
                       before={"status": before_status}, after={"status": "COMPLETED"})
    return rec
