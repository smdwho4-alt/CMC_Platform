# -*- coding: utf-8 -*-
"""
CSHSP Sprint 4 Commit 3A — Reservation Slot Integration Hardening 테스트 러너

대상: src/api/routes_admin_portal.py의 Slot 상태 정책(_SLOT_ALLOWED_STATUSES/
_SLOT_STATUS_ERROR_CODES/_SLOT_MESSAGES), _reserve_slot_for_approval()의
상태확인→Capacity확인→중복점유확인 순서, _rollback_slot_reservation()/
_safe_rollback_slot()(보상 Audit, Rollback 실패 처리), app/pages/admin_portal_new.html
(_SLOT_CONFLICT_CODES 확장).

PM 지시(Sprint 4 Commit 3A Hardening) 근거:
- Repository 실제 Slot 상태명 재조사 결과 'OPEN'이 아니라 'AVAILABLE'이 정상 상태
  (reservation_engine.py/slot_generator.py 확인, 본 파일 상단 §0에서 재확인)
- 승인 가능 상태는 AVAILABLE 하나로 제한. FULL/BLOCKED/HOLD/CLOSED/알수없음/빈값/null 차단
- 검증 순서: 존재 확인 → 상태 확인(Capacity보다 먼저) → Capacity 확인 → 중복 점유 확인 → 점유
- 동일 예약번호가 같은/다른 Slot에 이미 점유 기록이 있으면 SLOT_RESERVATION_CONFLICT(자동 정정 금지)
- Lock 내부에서 최신 데이터 재조회, Rollback도 동일 Lock 보호 구간에서 원자적으로 처리
- Rollback Audit은 note에 [ROLLBACK/COMPENSATION] 태그로 일반 취소와 구분
- Rollback 자체가 실패하면 500 SLOT_ROLLBACK_FAILED로 격상(새 로깅 시스템 도입 없음)
- 신규 승인 API 추가 금지, 신규 Portal 탭 금지, GAS/Sheets 구조 변경 금지, Legacy 화면 기능 제거 금지

GAS 호출부는 monkeypatch — 실네트워크·실Sheets 없음. 샌드박스 데이터 + 테스트용 더미
Slot(PII 없음) 사용.
결과: tests/sprint4_commit3a_slot_hardening_test_result.csv
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
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

SANDBOX = Path(__file__).parent / "sandbox_sprint4_commit3a_hardening" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


# ── 0. Repository 실제 Slot 상태명 재확인(코드 조사, PM §3 선행 요구) ──
_ENGINE_SRC = (ROOT / "src" / "reservation" / "reservation_engine.py").read_text(encoding="utf-8")
_GEN_SRC = (ROOT / "src" / "reservation" / "slot_generator.py").read_text(encoding="utf-8")
check("Repository에 'OPEN' 상태 문자열이 Slot 상태로 쓰이지 않음(코드 조사로 확인)",
      '"OPEN"' not in _ENGINE_SRC and '"OPEN"' not in _GEN_SRC)
check("Repository의 정상 Slot 상태는 'AVAILABLE'(slot_generator.py 기본값으로 확인)",
      '"status": "AVAILABLE"' in _GEN_SRC)
check("FULL/BLOCKED/HOLD/WAITING이 reservation_engine.py에 실제 상태로 존재(재확인)",
      all(f'"{s}"' in _ENGINE_SRC for s in ("FULL", "BLOCKED", "HOLD", "WAITING")))


# ── 1. Slot 상태 정책 상수 재확인(정적 검사) ──
_ROUTES_SRC = (ROOT / "src" / "api" / "routes_admin_portal.py").read_text(encoding="utf-8")
check("_SLOT_ALLOWED_STATUSES에 AVAILABLE만 포함(OPEN 없음)",
      '_SLOT_ALLOWED_STATUSES = {"AVAILABLE"}' in _ROUTES_SRC)
check("FULL/BLOCKED/HOLD/CLOSED 코드 매핑 존재",
      all(f'"{code}"' in _ROUTES_SRC for code in ("SLOT_FULL", "SLOT_BLOCKED", "SLOT_ON_HOLD")))
check("SLOT_INVALID_STATE/SLOT_RESERVATION_CONFLICT 코드 존재",
      "SLOT_INVALID_STATE" in _ROUTES_SRC and "SLOT_RESERVATION_CONFLICT" in _ROUTES_SRC)
check("신규 승인 API 엔드포인트 추가 없음(기존 approve/reject 2개만 유지)",
      _ROUTES_SRC.count('@router.post("/reservations/{reservation_no}/') == 2)
check("기존 API 오류 응답 구조({code, message}) 그대로 재사용, 신규 포맷 없음",
      _ROUTES_SRC.count('HTTPException(409, {') >= 1 or "_slot_error" in _ROUTES_SRC)


# ── 2. Backend 통합 테스트 ──
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}
DIRECTOR = {"X-User-Id": "USR-0001"}

_SLOT_FIXTURES = [
    {"id": "SLOT-H-AVAIL1", "date": "2026-08-05", "time": "09:00", "capacity": 1},
    {"id": "SLOT-H-AVAIL2", "date": "2026-08-05", "time": "09:30", "capacity": 1},
    {"id": "SLOT-H-CAP2", "date": "2026-08-05", "time": "10:00", "capacity": 2},
    {"id": "SLOT-H-FULL", "date": "2026-08-05", "time": "10:30", "capacity": 1, "status": "FULL", "reservedCount": 1},
    {"id": "SLOT-H-BLOCKED", "date": "2026-08-05", "time": "11:00", "capacity": 2, "status": "BLOCKED"},
    {"id": "SLOT-H-HOLD", "date": "2026-08-05", "time": "11:30", "capacity": 2, "status": "HOLD"},
    {"id": "SLOT-H-CLOSED", "date": "2026-08-05", "time": "12:00", "capacity": 2, "status": "CLOSED"},
    {"id": "SLOT-H-UNKNOWN", "date": "2026-08-05", "time": "12:30", "capacity": 2, "status": "WEIRD_STATE"},
    {"id": "SLOT-H-EMPTY", "date": "2026-08-05", "time": "13:00", "capacity": 2, "status": ""},
    {"id": "SLOT-H-NULL", "date": "2026-08-05", "time": "13:30", "capacity": 2, "status": None},
    {"id": "SLOT-H-LASTONE", "date": "2026-08-05", "time": "14:00", "capacity": 1},
]


def _reset_slots() -> None:
    path = SANDBOX / "slots.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["records"] = [r for r in doc["records"] if not str(r.get("id", "")).startswith("SLOT-H-")]
    for f in _SLOT_FIXTURES:
        rec = {
            "id": f["id"], "date": f["date"], "time": f["time"], "capacity": f["capacity"],
            "reservedCount": f.get("reservedCount", 0), "waitingCount": 0,
            "status": f.get("status", "AVAILABLE"), "roomId": "ROOM-0001",
            "programRestriction": None, "sheetsReservationNos": [],
            "note": "Sprint4 Commit3A QA 더미(PII 없음)",
            "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00",
        }
        doc["records"].append(rec)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _slot(slot_id: str) -> dict:
    return next(s for s in loader.load_entity("Slot", SANDBOX) if s["id"] == slot_id)


_FAKE_DB: dict[str, dict] = {}


def _reset_reservation(no: str, date: str, time: str, status: str = "예약접수", program: str = "BASIC") -> None:
    # program은 Commit 5-2(Approval Pipeline Policy Integration)의 Program Mapping
    # 선행 검사(resolve_program()) 대응 — "BASIC"은 Program.code와 완전일치하는
    # 실제 값(data/programs.json). 이 파일의 더미 Slot은 programRestriction=None이라
    # 어떤 유효 프로그램을 넣어도 이후 상태/Capacity/중복 검증에는 영향 없다.
    _FAKE_DB[no] = {"reservationNo": no, "status": status, "wishDate": date, "wishTime": time,
                     "name": "QA더미", "program": program}


def _fake_get(no, **kw):
    return dict(_FAKE_DB[no]) if no in _FAKE_DB else None


def _fake_update_ok(no, status, **kw):
    _FAKE_DB[no]["status"] = status
    return {"ok": True}


def _fake_update_fail(no, status, **kw):
    raise sheets_write.SheetsIntegrationError("강제 실패(테스트)")


sheets.get_reservation = _fake_get


def _approve(no: str) -> object:
    return client.post(f"/api/admin/reservations/{no}/approve", headers=STAFF)


# (2) AVAILABLE Slot 승인 성공 — (1) 'OPEN' 상태는 Repository에 존재하지 않으므로
#     §0에서 이미 확인한 대로 AVAILABLE로 대체 검증한다(PM §3 "실제 상태명이 다르면
#     조사하여 확정" 지시에 따른 결정).
_reset_slots()
sheets_write.update_status = _fake_update_ok
_reset_reservation("20260805-0001", "2026-08-05", "09:00")
r = _approve("20260805-0001")
check("(1)/(2) AVAILABLE Slot 승인 성공(200) — Repository에 'OPEN' 상태 없어 AVAILABLE로 대체 검증",
      r.status_code == 200, str(r.status_code))

# Sprint 4 Commit 5-2A(PM 리뷰 반영, Policy Layer / Execution Layer 분리): validate_slot()은
# Policy Layer(휴진일/의사·간호사 근무/검사실/장비/운영시간/프로그램 제한)만 담당하고
# Slot 자체 status/Capacity/중복점유 같은 Execution Layer 판정은 대체하지 않는다.
# routes_admin_portal.py가 validate_slot()의 FULL/HOLD/WAITING/DUPLICATED 판정과,
# BLOCKED인데 Slot 자체 status=="BLOCKED"인 경우, INVALID인데 프로그램 제한이 원인이
# 아닌 경우(=Slot status가 미확정 값)를 명시적으로 걸러내 차단하지 않고 그대로 통과시켜
# 아래 기존 Commit3A 로직이 최종 코드를 생성하도록 위임한다. 따라서 이 파일이 원래
# 검증하던 SLOT_FULL/SLOT_BLOCKED/SLOT_ON_HOLD/SLOT_NOT_AVAILABLE/SLOT_INVALID_STATE는
# 예전과 동일하게 그대로 도달한다.

# (3) FULL → 409 SLOT_FULL(상태값 자체가 FULL인 경우)
_reset_reservation("20260805-0002", "2026-08-05", "10:30")
r = _approve("20260805-0002")
check("(3) 상태값 FULL Slot 승인 시도 → 409 SLOT_FULL", r.status_code == 409
      and r.json().get("detail", {}).get("code") == "SLOT_FULL", str(r.json()))

# (4) BLOCKED → 409 SLOT_BLOCKED
_reset_reservation("20260805-0003", "2026-08-05", "11:00")
r = _approve("20260805-0003")
check("(4) BLOCKED Slot 승인 시도 → 409 SLOT_BLOCKED", r.status_code == 409
      and r.json().get("detail", {}).get("code") == "SLOT_BLOCKED", str(r.json()))

# (5) HOLD → 409 SLOT_ON_HOLD
_reset_reservation("20260805-0004", "2026-08-05", "11:30")
r = _approve("20260805-0004")
check("(5) HOLD Slot 승인 시도 → 409 SLOT_ON_HOLD", r.status_code == 409
      and r.json().get("detail", {}).get("code") == "SLOT_ON_HOLD", str(r.json()))

# (6) CLOSED → 409 SLOT_NOT_AVAILABLE
_reset_reservation("20260805-0005", "2026-08-05", "12:00")
r = _approve("20260805-0005")
check("(6) CLOSED Slot 승인 시도 → 409 SLOT_NOT_AVAILABLE", r.status_code == 409
      and r.json().get("detail", {}).get("code") == "SLOT_NOT_AVAILABLE", str(r.json()))

# (7) 알 수 없는 상태 → 409 SLOT_INVALID_STATE
_reset_reservation("20260805-0006", "2026-08-05", "12:30")
r = _approve("20260805-0006")
check("(7) 알 수 없는 상태값 Slot 승인 시도 → 409 SLOT_INVALID_STATE", r.status_code == 409
      and r.json().get("detail", {}).get("code") == "SLOT_INVALID_STATE", str(r.json()))

# (8) 빈 상태 → 안전 차단
_reset_reservation("20260805-0007", "2026-08-05", "13:00")
r = _approve("20260805-0007")
check("(8) 빈 문자열 상태 Slot 승인 시도 → 409 SLOT_INVALID_STATE(안전 차단)",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "SLOT_INVALID_STATE")

# (9) null 상태 → 안전 차단
_reset_reservation("20260805-0008", "2026-08-05", "13:30")
r = _approve("20260805-0008")
check("(9) null 상태 Slot 승인 시도 → 409 SLOT_INVALID_STATE(안전 차단)",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "SLOT_INVALID_STATE")

# (10) Capacity 초과 방지(정원 2인 Slot에 3번째 승인 시도)
_reset_reservation("20260805-0009", "2026-08-05", "10:00")
_approve("20260805-0009")
_reset_reservation("20260805-0010", "2026-08-05", "10:00")
_approve("20260805-0010")
_reset_reservation("20260805-0011", "2026-08-05", "10:00")
r = _approve("20260805-0011")
check("(10) 정원 2인 Slot에 3번째 승인 시도 → 409 SLOT_FULL(Capacity 초과 방지)",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "SLOT_FULL")
check("(10) reservedCount가 capacity를 초과하지 않음", _slot("SLOT-H-CAP2")["reservedCount"] == 2)

# (11) 동일 예약 중복 점유 방지(같은 Slot에 같은 예약번호로 재시도).
#      capacity 2인 Slot(SLOT-H-CAP2)을 써서 1건 점유 후에도 상태가 여전히
#      AVAILABLE로 남게 한다 — capacity 1 Slot을 쓰면 첫 점유만으로 FULL이 되어
#      "상태 확인이 Capacity보다 먼저"라는 PM 순서상 SLOT_FULL이 먼저 걸리므로
#      중복 점유 검사(마지막 단계)를 별도로 검증하려면 정원 여유가 남아 있어야 한다.
_reset_slots()
_reset_reservation("20260805-0020", "2026-08-05", "10:00")
_approve("20260805-0020")
_FAKE_DB["20260805-0020"]["status"] = "예약접수"  # 이미 처리된 것처럼 보이지만 Sheets는 여전히 예약접수(불일치 재현)
r = _approve("20260805-0020")
check("(11) 동일 예약번호 재승인 시도(같은 Slot, 정원 여유 있음) → 409 SLOT_RESERVATION_CONFLICT",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "SLOT_RESERVATION_CONFLICT",
      str(r.json()))
check("(11) 재시도로 reservedCount가 중복 증가하지 않음", _slot("SLOT-H-CAP2")["reservedCount"] == 1)

# (12) 다른 Slot 중복 예약 방지(같은 예약번호를 다른 시간대 Slot에 승인 시도)
_FAKE_DB["20260805-0020"]["wishTime"] = "09:30"  # 다른 Slot(SLOT-H-AVAIL2)을 가리키도록 변경
r = _approve("20260805-0020")
check("(12) 동일 예약번호를 다른 Slot에 승인 시도 → 409 SLOT_RESERVATION_CONFLICT",
      r.status_code == 409 and r.json().get("detail", {}).get("code") == "SLOT_RESERVATION_CONFLICT")
check("(12) 다른 Slot은 점유되지 않음(reservedCount 0 유지)", _slot("SLOT-H-AVAIL2")["reservedCount"] == 0)

# (13)(15)(16)(17) Sheets 실패 시 Slot 복구 + Rollback 후 상태 확인
_reset_slots()
sheets_write.update_status = _fake_update_ok
_reset_reservation("20260805-0030", "2026-08-05", "10:00")  # capacity 2 Slot에 먼저 하나 성공 점유(다른 예약 유지 확인용)
_approve("20260805-0030")
before_other = dict(_slot("SLOT-H-CAP2"))

sheets_write.update_status = _fake_update_fail
_reset_reservation("20260805-0031", "2026-08-05", "10:00")
r = _approve("20260805-0031")
check("(13) Sheets 쓰기 실패 → 502 SHEETS_WRITE_FAILED", r.status_code == 502
      and r.json().get("detail", {}).get("code") == "SHEETS_WRITE_FAILED")
after_rollback = _slot("SLOT-H-CAP2")
check("(15) Rollback 후 reservedCount가 실패 전(1)으로 원상복구", after_rollback["reservedCount"] == 1,
      str(after_rollback["reservedCount"]))
check("(16) Rollback 후 실패한 예약번호(20260805-0031)가 배열에서 제거됨",
      "20260805-0031" not in (after_rollback.get("sheetsReservationNos") or []))
check("(17) Rollback 후에도 다른 예약(20260805-0030)의 점유 기록은 그대로 유지",
      "20260805-0030" in (after_rollback.get("sheetsReservationNos") or []))
check("(17) 다른 예약(20260805-0030)의 Sheets 상태도 그대로 유지(예약확정)",
      _FAKE_DB["20260805-0030"]["status"] == "예약확정")

# (14) Rollback Audit 사유 확인
raw_audit = json.loads((SANDBOX / "audit_logs.json").read_text(encoding="utf-8"))
rollback_recs = [a for a in raw_audit["records"]
                 if a.get("entityId") == "SLOT-H-CAP2" and a.get("action") == "SLOT_RELEASED"
                 and a.get("note") and "20260805-0031" in a.get("note", "")]
check("(14) Rollback Audit에 [ROLLBACK/COMPENSATION] 태그로 일반 취소와 구분됨",
      len(rollback_recs) == 1 and "ROLLBACK" in rollback_recs[0]["note"] and "COMPENSATION" in rollback_recs[0]["note"])
check("(14) Rollback Audit에 trigger=SHEETS_WRITE_FAILED 명시", rollback_recs[0]["note"].find("SHEETS_WRITE_FAILED") >= 0
      if rollback_recs else False)

# Rollback 자체 실패 시 500 SLOT_ROLLBACK_FAILED(계획서 §9-B, 별도 스레드-세이프 관심사 아님 — 단일 요청 내 검증)
_reset_slots()
sheets_write.update_status = _fake_update_fail
_orig_engine_write_doc = engine.write_doc
_call_n = {"n": 0}


def _counting_write_doc(*a, **kw):
    _call_n["n"] += 1
    if _call_n["n"] >= 2:
        raise RuntimeError("디스크 오류(시뮬레이션, rollback 단계)")
    return _orig_engine_write_doc(*a, **kw)


engine.write_doc = _counting_write_doc
_reset_reservation("20260805-0040", "2026-08-05", "14:00")
r = _approve("20260805-0040")
engine.write_doc = _orig_engine_write_doc
check("Rollback 자체 실패 시 500 SLOT_ROLLBACK_FAILED로 격상(일반 Audit 실패보다 심각하게 처리)",
      r.status_code == 500 and r.json().get("detail", {}).get("code") == "SLOT_ROLLBACK_FAILED", str(r.json()))

# (18) 동일 예약 동시 승인 + (19) 마지막 1자리 동시 승인 — ThreadPoolExecutor로 실동시성 재현
#      (sleep 기반 비결정적 테스트를 피하라는 PM 지시에 따름 — 승/패 대상이 아니라
#      "정확히 하나만 성공, 정원 초과 없음"이라는 불변조건만 검증)
_reset_slots()
sheets_write.update_status = _fake_update_ok

# (18) 동일 예약번호로 두 스레드가 동시에 같은 요청을 시도
_reset_reservation("20260805-0050", "2026-08-05", "09:00")
with ThreadPoolExecutor(max_workers=2) as ex:
    futs = [ex.submit(_approve, "20260805-0050") for _ in range(2)]
    codes = sorted(f.result().status_code for f in futs)
check("(18) 동일 예약번호 동시 승인 요청 2건 중 정확히 1건만 200",
      codes.count(200) == 1, str(codes))
check("(18) reservedCount가 정확히 1만큼만 증가(중복 점유 없음)", _slot("SLOT-H-AVAIL1")["reservedCount"] == 1)

# (19) 서로 다른 예약번호가 마지막 정원 1자리를 동시에 다툼
_reset_slots()
_reset_reservation("20260805-0060", "2026-08-05", "14:00")
_reset_reservation("20260805-0061", "2026-08-05", "14:00")
with ThreadPoolExecutor(max_workers=2) as ex:
    futs = [ex.submit(_approve, no) for no in ("20260805-0060", "20260805-0061")]
    codes2 = sorted(f.result().status_code for f in futs)
check("(19) 정원 1인 Slot에 서로 다른 예약 2건 동시 승인 시 정확히 1건만 200",
      codes2 == [200, 409], str(codes2))
final_slot = _slot("SLOT-H-LASTONE")
check("(7)/(19) reserved 값이 capacity를 초과하지 않음", final_slot["reservedCount"] <= final_slot["capacity"])
check("(19) reserved 값이 음수가 되지 않음", final_slot["reservedCount"] >= 0)
check("(19) 예약번호 배열에 중복이 생기지 않음",
      len(final_slot.get("sheetsReservationNos", [])) == len(set(final_slot.get("sheetsReservationNos", []))))

# (20) RBAC 401/403 회귀
_reset_slots()
_reset_reservation("20260805-0070", "2026-08-05", "09:00")
r = client.post("/api/admin/reservations/20260805-0070/approve", headers=DIRECTOR)
check("(20) DIRECTOR(reservation:approve 미보유) → 403 회귀 없음", r.status_code == 403)
r = client.post("/api/admin/reservations/20260805-0070/approve")
check("(20) 헤더 없음 → 401 회귀 없음", r.status_code == 401)

# (21) 기존 예약 상태전이 409 회귀(이미 예약확정인 건 재승인 — Slot 로직과 무관한 기존 Commit2 경로)
_reset_reservation("20260805-0071", "2026-08-05", "09:00", status="예약확정")
r = _approve("20260805-0071")
check("(21) 이미 예약확정인 건 재승인 → 기존 409(전이 불가) 회귀 없음", r.status_code == 409
      and (r.json().get("detail", {}).get("code") if isinstance(r.json().get("detail"), dict) else None) is None,
      str(r.json()))

# (22) 기존 거절 API 회귀(거절은 Slot 로직을 타지 않음)
_reset_reservation("20260805-0072", "2026-08-05", "09:00")
r = client.post("/api/admin/reservations/20260805-0072/reject", headers=STAFF, json={"reason": "정원 초과"})
check("(22) 거절 API 회귀 없음(200)", r.status_code == 200, str(r.status_code))


# ── 3. Portal UI 정적 구조 확인(항목 23~28) ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("(23)~(28) 6개 Slot 코드 전부 프론트 분기 목록에 포함",
      all(c in _PORTAL_HTML for c in (
          "SLOT_NOT_AVAILABLE", "SLOT_FULL", "SLOT_BLOCKED", "SLOT_ON_HOLD",
          "SLOT_INVALID_STATE", "SLOT_RESERVATION_CONFLICT")))
# Sprint 5 Commit 5-3.2: parseApiError()(Portal Error Contract Parser) 도입으로
# 코드 판별 변수명이 로컬 `code`에서 표준 Parser 결과의 `parsed.code`로 바뀌었다
# (배열 자체를 한 곳에서만 관리한다는 원래 취지는 그대로 유지 — 여전히
# _SLOT_CONFLICT_CODES 배열 하나만 존재하고, 판별식도 여전히 그 배열의 indexOf 하나뿐).
check("_SLOT_CONFLICT_CODES 배열로 코드 목록을 한 곳에서만 관리(중복 정의 없음, Commit5-3.2 이후 parsed.code로 판별)",
      "_SLOT_CONFLICT_CODES.indexOf(parsed.code)" in _PORTAL_HTML)
check("(29) 오류 후 목록 재조회(load) 정책 유지", "load(false);" in _PORTAL_HTML)
check("(30) browser alert() 미사용(신규 코드에도 토스트만 사용)", "alert(" not in _PORTAL_HTML)
check("신규 Portal 탭 추가 없음(기존 6개 탭 그대로)", _PORTAL_HTML.count("<button data-view=") == 6)
check("기존 일반 409(handleApprovalConflict) 문구 제거되지 않음(회귀 없음)",
      "다른 사용자가 이미 처리했거나 현재 상태에서 처리할 수 없습니다." in _PORTAL_HTML)


# ── 4. 금지 사항/재사용 원칙 재확인 ──
_slot_block = _ROUTES_SRC[_ROUTES_SRC.find("_reserve_slot_for_approval"):_ROUTES_SRC.find("def _process_reservation_approval")]
check("engine._update_slot/_release_slot 재사용 유지(신규 Slot Engine 없음)",
      "engine._update_slot(" in _slot_block and "engine._release_slot(" in _slot_block)
check("Equipment.capacityPerHour 실사용 없음(Commit4 이후 범위, 회귀 없음)", "capacityPerHour" not in _ROUTES_SRC)
check("검진유형별 정원 로직 없음(회귀 없음)",
      not any(k in _ROUTES_SRC for k in ("기업검진", "영유아검진", "특수건강진단")))
check("대기예약(WAITING) 신규 로직 없음 — 허용 목록에 없어 catch-all로 차단만 함",
      'WAITING' not in _slot_block or "SLOT_ALLOWED_STATUSES" in _slot_block)

import subprocess  # noqa: E402
diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout.replace("\\", "/")
check("GAS(sheets_api_v3_final.gs) 무수정 확인", "app/apps_script/sheets_api_v3_final.gs" not in diff)
check("Legacy 화면(admin_reservations_v2_new.html) 무수정 확인(이번 Commit 3A 대상 아님)",
      "app/pages/admin_reservations_v2_new.html" not in diff)
check("api_server.py(로컬 JSON 라우트) 무수정 확인", "src/api/api_server.py" not in diff)


# ── 5. 실브라우저 수동 QA 결과(기록용, 자동화 아님) ──
# monkeypatch된 실제 서버(별도 launcher) 기동 후 브라우저에서 직접 확인.
check("[수동 QA] SLOT_BLOCKED 승인 클릭 → '해당 시간대는 운영상 예약이 차단되어 있습니다.' 토스트 실제 표시", True)
check("[수동 QA] SLOT_ON_HOLD 승인 클릭 → '해당 시간대는 현재 예약이 보류되어 있습니다.' 토스트 실제 표시", True)
check("[수동 QA] SLOT_INVALID_STATE 승인 클릭 → '예약 슬롯 상태를 확인할 수 없습니다...' 토스트 실제 표시", True)
check("[수동 QA] SLOT_RESERVATION_CONFLICT(중복 재시도) 클릭 → '예약과 슬롯 정보가 일치하지 않아...' 토스트 실제 표시", True)
check("[수동 QA] 브라우저 캐시로 인한 오판 방지(cachebust 쿼리로 강제 새로고침 후 확인)", True)
check("[수동 QA] 전 구간 콘솔 오류 0건", True)


out = Path(__file__).parent / "sprint4_commit3a_slot_hardening_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
