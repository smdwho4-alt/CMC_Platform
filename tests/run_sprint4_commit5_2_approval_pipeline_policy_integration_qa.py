# -*- coding: utf-8 -*-
"""
CSHSP Sprint 4 Commit 5-2 — Approval Pipeline Policy Integration 테스트 러너

대상: src/api/routes_admin_portal.py::_reserve_slot_for_approval()에 새로 삽입된
Program Mapping(engine.resolve_program()) → Validation Context
(validation_context="reservation_approval") → validate_slot() → Policy Verdict
매핑 블록. 기존 Commit2/3/3A 로직(Slot 상태검사/Capacity/Duplicate/Reserve/
Rollback/Compensation/Audit)은 무수정이며 이 새 블록 다음에 그대로 실행된다.

PM 공식 Pipeline(Sprint4 Commit5-2 PM APPROVED 메시지 §3) 근거:
DataLock → 최신 Slot 조회 → Program Mapping → Validation Context → validate_slot()
→ Policy Verdict → 기존 Slot 상태검사 → Capacity → Duplicate → Reserve → Unlock
→ Sheets Write → Audit

검증 대상:
- Program Mapping 성공(code/name) / 실패(422 RESERVATION_PROGRAM_UNMAPPED)
- validate_slot() 예외(500 SLOT_POLICY_VALIDATION_FAILED) / Unknown Verdict(500, 동일 코드)
- 422/409/500 전부 Slot 미점유, Sheets 미호출, Audit 미기록(Server Log만 허용)
- Commit3A 코드(SLOT_FULL 등)는 삭제되지 않고 여전히 소스에 존재(§10 유지 요구)

PM 리뷰 반영(Sprint4 Commit5-2A, Policy Layer / Execution Layer Separation):
validate_slot()은 Policy Layer(휴진일/의사·간호사 근무/검사실/장비/운영시간/프로그램
제한)만 담당하고 Execution Layer(Slot 자체 status/Capacity/중복점유 — Commit3A가 이미
소유)를 대체하지 않는다. validate_slot()의 FULL/HOLD/WAITING/DUPLICATED 판정, 그리고
BLOCKED/INVALID 중 Slot 자체 status나 미확정 상태값이 원인인 경우는 routes 레이어에서
차단하지 않고 기존 Commit3A 로직에 위임한다(그 결과 SLOT_FULL/SLOT_BLOCKED/SLOT_ON_HOLD
등 기존 코드가 그대로 최종 응답이 된다). 반대로 BLOCKED가 휴진일/의사·간호사/검사실/
장비/운영시간이 원인이거나 INVALID가 프로그램 제한 불일치가 원인인 경우(Commit3A가
전혀 모르는 영역)는 여전히 409 RESERVATION_POLICY_BLOCKED로 여기서 직접 차단한다 —
(5b)가 이 구분이 실제로 동작함을 검증한다(Slot은 AVAILABLE/정원 여유이지만 근무 의사/
간호사가 없는 날짜라 Execution Layer만으로는 걸러지지 않는 시나리오).

GAS 호출부는 monkeypatch — 실네트워크·실Sheets 없음. 샌드박스 데이터 + 테스트용 Slot
레코드 사용(더미, PII 없음). 테스트 대상 날짜(2026-08-04, 화요일)는 실제 doctors.json/
nurses.json 근무일(DOC-0001/DOC-0003, NUR-0001/NUR-0002)과 일치하도록 사전 확인했다
(휴진일 schedules.json에도 해당 없음).
결과: tests/sprint4_commit5_2_approval_pipeline_policy_integration_test_result.csv
"""
from __future__ import annotations

import csv
import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "api"))
sys.path.insert(0, str(ROOT / "src" / "services"))
sys.path.insert(0, str(ROOT / "src" / "reservation"))

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import reservation_engine as engine  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402
import sheets_write_service as sheets_write  # noqa: E402
from api_server import create_app  # noqa: E402
from _step2_session_helper import ensure_session  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint4_commit5_2_policy" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

_TEST_DATE = "2026-08-04"  # 화요일 — DOC-0001/DOC-0003, NUR-0001/NUR-0002 근무일
_TEST_SLOTS = [
    {"id": "SLOT-C52-0900-A", "date": _TEST_DATE, "time": "09:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit5-2 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1000-A", "date": _TEST_DATE, "time": "10:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit5-2 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1100-A", "date": _TEST_DATE, "time": "11:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit5-2 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1200-A", "date": _TEST_DATE, "time": "12:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit5-2 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1300-A", "date": _TEST_DATE, "time": "13:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "BLOCKED",
     "roomId": "ROOM-0001", "programRestriction": None, "blockReason": "QA 강제 BLOCKED",
     "note": "Sprint4 Commit5-2 QA 더미(정책 차단 시나리오 전용)",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1400-A", "date": _TEST_DATE, "time": "14:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit5-2 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1500-A", "date": _TEST_DATE, "time": "15:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit5-2 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-1600-A", "date": _TEST_DATE, "time": "16:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": "PRG-VIP",
     "note": "Sprint4 Commit5-2 QA 더미(정의된 INVALID verdict 전용 — 프로그램 제한 불일치)",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-C52-SAT-A", "date": "2026-08-01", "time": "09:00",
     "capacity": 3, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None,
     "note": "Sprint4 Commit5-2A QA 더미(토요일, 근무 의사/간호사 없음 — 진짜 Policy Layer 차단 전용)",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
]


def _reset_slots() -> None:
    path = SANDBOX / "slots.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["records"] = [r for r in doc["records"] if not str(r.get("id", "")).startswith("SLOT-C52-")]
    doc["records"].extend(json.loads(json.dumps(_TEST_SLOTS)))  # deep copy
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _slot_state(slot_id: str) -> tuple[int, str]:
    s = next(s for s in loader.load_entity("Slot", SANDBOX) if s["id"] == slot_id)
    return s["reservedCount"], s["status"]


results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


_ROUTES_SRC = (ROOT / "src" / "api" / "routes_admin_portal.py").read_text(encoding="utf-8")

# ── 0. 공식 Pipeline 정적 확인 ──
check("Program Mapping이 resolve_program()을 재사용(신규 Repository 없음)",
      "engine.resolve_program(" in _ROUTES_SRC)
check("Validation Context가 validation_context=\"reservation_approval\"로 연동됨",
      'validation_context="reservation_approval"' in _ROUTES_SRC)
check("validate_slot()이 그대로 재사용됨(신규 Policy Engine 없음)",
      "engine.validate_slot(" in _ROUTES_SRC)
check("_reserve_slot_for_approval() 안에 DataLock 진입이 정확히 1곳(구조 변경 없음)",
      _ROUTES_SRC[_ROUTES_SRC.find("def _reserve_slot_for_approval"):
                  _ROUTES_SRC.find("def _rollback_slot_reservation")].count("with DataLock(data_dir):") == 1)
check("Commit3A 코드(SLOT_FULL/SLOT_BLOCKED/SLOT_ON_HOLD/SLOT_NOT_AVAILABLE/SLOT_INVALID_STATE/"
      "SLOT_RESERVATION_CONFLICT)가 삭제되지 않고 그대로 존재(PM §10 유지 요구)",
      all(code in _ROUTES_SRC for code in (
          "SLOT_FULL", "SLOT_BLOCKED", "SLOT_ON_HOLD", "SLOT_NOT_AVAILABLE",
          "SLOT_INVALID_STATE", "SLOT_RESERVATION_CONFLICT")))
check("engine._update_slot()/engine._release_slot() 재사용 유지(Reserve/Rollback 무수정)",
      "engine._update_slot(" in _ROUTES_SRC and "engine._release_slot(" in _ROUTES_SRC)
# "reason_code"라는 단어 자체는 이번 Commit의 코드 주석(범위 밖임을 설명하는 문구)에
# 등장하지만, 실제 응답 필드로는 구현하지 않았다 — JSON 키 형태("reason_code":)로만
# 정확히 검사해 주석과 혼동하지 않는다.
check("응답 바디에 reason_code 필드가 실제로 구현되지 않음(이번 Commit 범위 아님, 주석과 구분해 정확 검사)",
      '"reason_code":' not in _ROUTES_SRC)
check("신규 승인 API 엔드포인트 추가 없음(기존 approve/reject 2개만 유지)",
      _ROUTES_SRC.count('@router.post("/reservations/{reservation_no}/') == 2)


# ── 1. Backend 통합 테스트 ──
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}  # ROLE-STAFF: reservation:approve 보유(GET 등 Mock 허용 대상 조회에 계속 사용)
# Sprint8 Commit8-2c STEP2: 승인(approve)은 상태변경 API라 Mock이 차단된다(CSRF
# 유무 무관, PM 승인사항). 실제 세션 로그인으로 전환해 정상 CSRF Token을 발급받는다.
STAFF_CSRF = ensure_session(
    client, SANDBOX, user_id="USR-0002", role_id="ROLE-STAFF",
    display_name="QA STAFF", login_id="qa_step2_c52_staff",
)

_FAKE_DB: dict[str, dict] = {}
_UPDATE_STATUS_CALLS: list[str] = []


def _reset_reservation(no: str, time: str, program: str, status: str = "예약접수") -> None:
    _FAKE_DB[no] = {"reservationNo": no, "status": status, "name": "QA더미",
                     "wishDate": _TEST_DATE, "wishTime": time, "program": program}


def _fake_get_reservation(no, **kw):
    return dict(_FAKE_DB[no]) if no in _FAKE_DB else None


def _fake_update_status_ok(no, status, **kw):
    _UPDATE_STATUS_CALLS.append(no)
    _FAKE_DB[no]["status"] = status
    return {"ok": True}


sheets.get_reservation = _fake_get_reservation
sheets_write.update_status = _fake_update_status_ok


def _audit_recs(entity_id: str) -> list[dict]:
    r = client.get("/api/audit-logs", headers=STAFF)
    return [x for x in r.json().get("records", []) if x.get("entityId") == entity_id]


def _approve(no: str):
    return client.post(f"/api/admin/reservations/{no}/approve", headers=STAFF_CSRF)


# (1) Program Mapping 성공 — Program.code 완전일치("SMART") → 정상 승인(200)
_reset_slots()
_reset_reservation("20260804-P001", "09:00", "SMART")
r = _approve("20260804-P001")
check("(1) Program.code 완전일치(SMART) → 정상 승인 200", r.status_code == 200, str(r.status_code))
check("(1) Slot 점유 반영(reservedCount 1)", _slot_state("SLOT-C52-0900-A")[0] == 1)
check("(1) Sheets update_status 호출됨", "20260804-P001" in _UPDATE_STATUS_CALLS)
recs = [a for a in _audit_recs("20260804-P001") if a.get("action") == "RESERVATION_APPROVED"]
check("(1) RESERVATION_APPROVED Audit 기록됨", len(recs) == 1)

# (2) Program Mapping 성공 — Program.name 완전일치("온김에검진", Health Check 핵심 사례)
_reset_reservation("20260804-P002", "10:00", "온김에검진")
r = _approve("20260804-P002")
check("(2) Program.name 완전일치(온김에검진, Health Check 반영) → 정상 승인 200",
      r.status_code == 200, str(r.status_code))
check("(2) Slot 점유 반영(reservedCount 1)", _slot_state("SLOT-C52-1000-A")[0] == 1)

# (3) Program Mapping 실패 — 존재하지 않는 프로그램 문자열 → 422
before_reserved = _slot_state("SLOT-C52-1100-A")[0]
_reset_reservation("20260804-P003", "11:00", "존재하지않는프로그램")
_stderr = io.StringIO()
with contextlib.redirect_stderr(_stderr):
    r = _approve("20260804-P003")
check("(3) Program Mapping 실패(미매핑 문자열) → 422", r.status_code == 422, str(r.status_code))
check("(3) 422 code=RESERVATION_PROGRAM_UNMAPPED",
      r.json().get("detail", {}).get("code") == "RESERVATION_PROGRAM_UNMAPPED", str(r.json()))
check("(3) Slot 미점유(reservedCount 불변)", _slot_state("SLOT-C52-1100-A")[0] == before_reserved)
check("(3) Sheets update_status 미호출", "20260804-P003" not in _UPDATE_STATUS_CALLS)
check("(3) RESERVATION_APPROVED Audit 미기록",
      not any(a.get("action") == "RESERVATION_APPROVED" for a in _audit_recs("20260804-P003")))
_log = _stderr.getvalue()
check("(3) Server Log에 RESERVATION_PROGRAM_UNMAPPED 기록됨", "RESERVATION_PROGRAM_UNMAPPED" in _log, _log.strip())
check("(3) Server Log에 reservation_no/slot_id/program 필드 포함",
      "reservation_no=20260804-P003" in _log and "slot_id=" in _log and "program=" in _log)
check("(3) Server Log에 PII(이름/전화번호 등) 미포함(QA더미라는 이름 필드 자체가 로그에 없음)",
      "QA더미" not in _log)

# (4) Program 필드 자체가 빈 값(GAS 응답에 program 컬럼이 비어 있는 극단적 경우) → 422
_reset_reservation("20260804-P004", "12:00", "")
r = _approve("20260804-P004")
check("(4) program 빈 값 → 422 RESERVATION_PROGRAM_UNMAPPED",
      r.status_code == 422 and r.json().get("detail", {}).get("code") == "RESERVATION_PROGRAM_UNMAPPED",
      str(r.json()))

# (5) Slot 자체 status=="BLOCKED"(Execution Layer) → Commit5-2A: validate_slot()이
# BLOCKED를 반환하지만 Slot 자체 status가 BLOCKED이므로 여기서 차단하지 않고 기존
# Commit3A 로직에 위임한다 — 최종 코드는 SLOT_BLOCKED(RESERVATION_POLICY_BLOCKED 아님).
_reset_reservation("20260804-P005", "13:00", "BASIC")
r = _approve("20260804-P005")
check("(5) BLOCKED Slot 승인 시도 → 409 SLOT_BLOCKED(Execution Layer, Commit3A가 최종 코드 생성)",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "SLOT_BLOCKED",
      str(r.json()))
check("(5) Slot 미점유(reservedCount 0 유지)", _slot_state("SLOT-C52-1300-A")[0] == 0)
check("(5) Sheets update_status 미호출", "20260804-P005" not in _UPDATE_STATUS_CALLS)
check("(5) RESERVATION_APPROVED Audit 미기록",
      not any(a.get("action") == "RESERVATION_APPROVED" for a in _audit_recs("20260804-P005")))

# (5b) 진짜 Policy Layer 차단(Commit5-2A 핵심 검증) — Slot 자체는 AVAILABLE이고 정원도
# 남아 있어 Commit3A의 Execution Layer 검사만으로는 통과되지만, 근무 가능 의사/간호사가
# 없는 날짜(토요일)라서 validate_slot()의 Policy Layer 검사(BLOCKED, Slot status는
# AVAILABLE)가 이를 잡아야 한다. 여기서 차단하지 않으면 정책 위반 승인이 나가는 실제
# 버그가 된다는 것을 재현·검증한다.
_reset_reservation("20260804-P005B", "09:00", "BASIC")
_FAKE_DB["20260804-P005B"]["wishDate"] = "2026-08-01"  # 토요일 — 근무 의사/간호사 없음(사전 확인)
r = _approve("20260804-P005B")
check("(5b) 근무 의사/간호사 없는 날짜(Slot은 AVAILABLE) → 409 RESERVATION_POLICY_BLOCKED(Policy Layer)",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "RESERVATION_POLICY_BLOCKED",
      str(r.json()))
check("(5b) Sheets update_status 미호출(정책 위반 승인이 나가지 않음)",
      "20260804-P005B" not in _UPDATE_STATUS_CALLS)
check("(5b) RESERVATION_APPROVED Audit 미기록",
      not any(a.get("action") == "RESERVATION_APPROVED" for a in _audit_recs("20260804-P005B")))
check("(5b) Slot 미점유(reservedCount 0 유지, Execution Layer에 도달조차 안 함)",
      _slot_state("SLOT-C52-SAT-A")[0] == 0)

# (6) validate_slot() 예외 발생 → 500 SLOT_POLICY_VALIDATION_FAILED
_real_validate_slot = engine.validate_slot


def _raise_validate_slot(*a, **kw):
    raise RuntimeError("QA 강제 예외(validate_slot 내부 오류 시뮬레이션)")


engine.validate_slot = _raise_validate_slot
_reset_reservation("20260804-P006", "14:00", "BASIC")
_stderr2 = io.StringIO()
with contextlib.redirect_stderr(_stderr2):
    r = _approve("20260804-P006")
engine.validate_slot = _real_validate_slot
check("(6) validate_slot() 예외 → 500", r.status_code == 500, str(r.status_code))
check("(6) 500 code=SLOT_POLICY_VALIDATION_FAILED",
      r.json().get("detail", {}).get("code") == "SLOT_POLICY_VALIDATION_FAILED", str(r.json()))
check("(6) Slot 미점유(reservedCount 0 유지)", _slot_state("SLOT-C52-1400-A")[0] == 0)
check("(6) Sheets update_status 미호출", "20260804-P006" not in _UPDATE_STATUS_CALLS)
check("(6) RESERVATION_APPROVED Audit 미기록",
      not any(a.get("action") == "RESERVATION_APPROVED" for a in _audit_recs("20260804-P006")))
check("(6) Server Log에 SLOT_POLICY_VALIDATION_FAILED 기록됨(예외 경로)",
      "SLOT_POLICY_VALIDATION_FAILED" in _stderr2.getvalue())

# (7) Unknown Verdict(validate_slot()이 정의되지 않은 값을 반환) → 500 SLOT_POLICY_VALIDATION_FAILED
def _unknown_verdict_validate_slot(*a, **kw):
    return {"verdict": "SOMETHING_UNDEFINED", "reasons": ["QA 강제 Unknown Verdict"], "slot": None}


engine.validate_slot = _unknown_verdict_validate_slot
_reset_reservation("20260804-P007", "15:00", "BASIC")
_stderr3 = io.StringIO()
with contextlib.redirect_stderr(_stderr3):
    r = _approve("20260804-P007")
engine.validate_slot = _real_validate_slot
check("(7) Unknown Verdict(정의되지 않은 값) → 500", r.status_code == 500, str(r.status_code))
check("(7) 500 code=SLOT_POLICY_VALIDATION_FAILED",
      r.json().get("detail", {}).get("code") == "SLOT_POLICY_VALIDATION_FAILED", str(r.json()))
check("(7) Slot 미점유(reservedCount 0 유지)", _slot_state("SLOT-C52-1500-A")[0] == 0)
check("(7) Sheets update_status 미호출", "20260804-P007" not in _UPDATE_STATUS_CALLS)
check("(7) Server Log에 POLICY_UNKNOWN_VERDICT 기록됨", "POLICY_UNKNOWN_VERDICT" in _stderr3.getvalue())

# (8) Unknown Verdict — 반환값이 dict가 아니거나 verdict 키 자체가 없는 경우도 500 처리
def _malformed_validate_slot(*a, **kw):
    return None


engine.validate_slot = _malformed_validate_slot
_reset_reservation("20260804-P008", "09:00", "BASIC")  # SLOT-C52-0900-A(이미 P001로 1건 점유, 여유 있음)
r = _approve("20260804-P008")
engine.validate_slot = _real_validate_slot
check("(8) validate_slot() 반환값이 None(구조 이상) → 500 SLOT_POLICY_VALIDATION_FAILED",
      r.status_code == 500 and r.json().get("detail", {}).get("code") == "SLOT_POLICY_VALIDATION_FAILED",
      str(r.json()))

# (9) 정의된 INVALID(프로그램 제한 Slot 불일치)는 500이 아니라 409로 처리되어야 한다
#     (PM §8: "정의된 INVALID는 500이 아니다. 반드시 409이다"). SLOT-C52-1600-A는
#     programRestriction="PRG-VIP"인데 예약은 program="BASIC"(→PRG-BASIC)이므로
#     validate_slot()이 명시적으로 INVALID를 반환하는 실제 경로를 그대로 재현한다
#     (날짜 형식 오류는 이 Pipeline에서 애초에 도달 불가 — Slot 조회가 동일 wishDate
#     문자열로 먼저 매칭에 성공해야 validate_slot()까지 도달하므로 자체 모순).
_reset_reservation("20260804-P009", "16:00", "BASIC")
r = _approve("20260804-P009")
check("(9) 정의된 INVALID(프로그램 제한 Slot 불일치) → 409(500 아님)", r.status_code == 409, str(r.status_code))
check("(9) 409 code=RESERVATION_POLICY_BLOCKED",
      r.json().get("detail", {}).get("code") == "RESERVATION_POLICY_BLOCKED", str(r.json()))
check("(9) Slot 미점유(reservedCount 0 유지)", _slot_state("SLOT-C52-1600-A")[0] == 0)

# (10) 정상 성공 경로 회귀 — 기존 Commit2/3/3A 응답 필드(slotId 등)가 그대로 유지되는지
_reset_reservation("20260804-P010", "09:00", "BASIC")  # SLOT-C52-0900-A(P001로 1건 점유, 여유 있음)
r = _approve("20260804-P010")
check("(10) 정상 승인 성공 시 slotId 응답 필드 유지(기존 응답 구조 무수정)",
      r.status_code == 200 and r.json().get("data", {}).get("slotId") == "SLOT-C52-0900-A", str(r.json()))

results_summary_total = len(results)

# ── 결과 저장 ──
out = Path(__file__).parent / "sprint4_commit5_2_approval_pipeline_policy_integration_test_result.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트", "결과", "상세"])
    w.writerows(results)

total = len(results)
passed = sum(1 for _, r, _ in results if r == "PASS")
summary = f"TOTAL={total} PASS={passed} FAIL={total - passed}"
try:
    print(summary)
except UnicodeEncodeError:
    print(summary.encode("ascii", "backslashreplace").decode("ascii"))

if passed != total:
    sys.exit(1)
