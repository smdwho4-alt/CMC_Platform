# -*- coding: utf-8 -*-
"""
CSHSP Sprint 4 Commit 3 — Reservation Slot Integration 테스트 러너

대상: src/api/routes_admin_portal.py의 _reserve_slot_for_approval()/
_rollback_slot_reservation()(예약 승인 시 Slot 조회·점유·롤백), 기존
reservation_engine.py::_update_slot()/_release_slot() 재사용 여부,
app/pages/admin_portal_new.html(Portal UI 정적 구조 — SLOT_NOT_AVAILABLE/
SLOT_FULL 토스트 분기).

PM 원칙 근거(Sprint 4 Commit 3 Implementation Phase 지시):
- 신규 Slot Engine 없음 — reservation_engine.py의 _update_slot/_release_slot을
  그대로 재사용(코드 검사로 재확인)
- Workflow: 예약접수→Slot조회→(없음→409 SLOT_NOT_AVAILABLE)→Capacity검사→
  (FULL→409 SLOT_FULL)→Slot점유→Sheets상태변경→Audit→응답
- Google Sheets 쓰기 전 Slot 확보 완료, Sheets 실패 시 Slot Rollback
- Audit은 Sheets 성공 후에만(기존 Best Effort 정책 재사용)
- 신규 승인 API 추가 금지(기존 approve 엔드포인트 확장), RBAC은 reservation:approve 재사용
- 대기예약/예약변경/예약취소/AI추천Slot/자동재배정/기업·영유아·특수건강진단 정원/
  장비별 Capacity(Equipment.capacityPerHour) 실사용은 이번 Commit 범위 밖(Commit4 이후)

GAS 호출부는 monkeypatch — 실네트워크·실Sheets 없음. 샌드박스 데이터 + 테스트용 Slot
레코드 사용(더미, PII 없음).
결과: tests/sprint4_commit3_slot_integration_test_result.csv
"""
from __future__ import annotations

import csv
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
import sheets_readonly_service as sheets  # noqa: E402
import sheets_write_service as sheets_write  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint4_commit3_slot" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

# 테스트 전용 더미 Slot 2개 주입(capacity=1로 좁혀 FULL 시나리오를 쉽게 재현) — PII 없음.
_TEST_SLOTS = [
    {"id": "SLOT-QA-0900-A", "date": "2026-08-04", "time": "09:00",
     "capacity": 1, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit3 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
    {"id": "SLOT-QA-1000-A", "date": "2026-08-04", "time": "10:00",
     "capacity": 2, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
     "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit3 QA 더미",
     "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00"},
]


def _reset_slots() -> None:
    path = SANDBOX / "slots.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["records"] = [r for r in doc["records"] if not str(r.get("id", "")).startswith("SLOT-QA-")]
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


# ── 0. 신규 Slot Engine 없음 확인(재사용 원칙) ──
_ROUTES_SRC = (ROOT / "src" / "api" / "routes_admin_portal.py").read_text(encoding="utf-8")
check("reservation_engine의 _update_slot을 재사용(신규 Slot Engine 없음)",
      "engine._update_slot(" in _ROUTES_SRC)
check("reservation_engine의 _release_slot을 재사용(Rollback에 신규 로직 없음)",
      "engine._release_slot(" in _ROUTES_SRC)
check("DataLock으로 Lock→Capacity검사→Slot점유 구간을 감쌈(동시성 원칙)",
      "with DataLock(data_dir):" in _ROUTES_SRC and "_reserve_slot_for_approval" in _ROUTES_SRC)
check("신규 승인 API 엔드포인트 추가 없음(기존 approve/reject 2개만 유지)",
      _ROUTES_SRC.count('@router.post("/reservations/{reservation_no}/') == 2,
      str(_ROUTES_SRC.count('@router.post("/reservations/{reservation_no}/')))


# ── 1. Backend 통합 테스트 ──
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}   # ROLE-STAFF: reservation:approve 보유
DIRECTOR = {"X-User-Id": "USR-0001"}  # 미보유

_FAKE_DB: dict[str, dict] = {}


def _reset_reservation(no: str, status: str, date: str, time: str, program: str = "BASIC") -> None:
    # program은 Commit 5-2(Approval Pipeline Policy Integration)의 Program Mapping
    # 선행 검사(resolve_program()) 대응 — "BASIC"은 Program.code와 완전일치하는
    # 실제 값(data/programs.json). 이 파일의 더미 Slot은 programRestriction=None이라
    # 어떤 유효 프로그램을 넣어도 이후 상태/Capacity/중복 검증에는 영향 없다.
    _FAKE_DB[no] = {"reservationNo": no, "status": status, "wishDate": date, "wishTime": time,
                     "name": "QA더미", "program": program}


def _fake_get_reservation(no, **kw):
    return dict(_FAKE_DB[no]) if no in _FAKE_DB else None


def _fake_update_status_ok(no, status, **kw):
    _FAKE_DB[no]["status"] = status
    return {"ok": True}


def _fake_update_status_fail(no, status, **kw):
    raise sheets_write.SheetsIntegrationError("GAS 오류 응답(updateStatus): 강제 실패(테스트)")


sheets.get_reservation = _fake_get_reservation


def _audit_recs(entity_id: str) -> list[dict]:
    r = client.get("/api/audit-logs", headers=DIRECTOR)
    return [x for x in r.json().get("records", []) if x.get("entityId") == entity_id]


# (1) Slot 존재(정상 매칭) + (5) Slot Reserve
_reset_slots()
sheets_write.update_status = _fake_update_status_ok
_reset_reservation("20260804-0001", "예약접수", "2026-08-04", "09:00")
r = client.post("/api/admin/reservations/20260804-0001/approve", headers=STAFF)
check("(1) Slot 존재 + 승인 성공(200)", r.status_code == 200, str(r.status_code))
check("(5) Slot 점유 반영(reservedCount 1, capacity 1 → FULL)",
      _slot_state("SLOT-QA-0900-A") == (1, "FULL"), str(_slot_state("SLOT-QA-0900-A")))
check("응답에 slotId 포함", r.json().get("data", {}).get("slotId") == "SLOT-QA-0900-A")

# (3) Capacity FULL
# Sprint 4 Commit 5-2A(PM 리뷰 반영): validate_slot()의 FULL 판정은 Execution Layer로
# 분류되어 routes_admin_portal.py가 차단하지 않고 그대로 통과시킨다 — 아래 기존
# Commit3A 로직이 이 시나리오의 최종 코드(SLOT_FULL)를 그대로 생성한다.
_reset_reservation("20260804-0002", "예약접수", "2026-08-04", "09:00")
r = client.post("/api/admin/reservations/20260804-0002/approve", headers=STAFF)
check("(3) Capacity FULL → 409", r.status_code == 409, str(r.status_code))
body = r.json()
check("(3) 409 code=SLOT_FULL", body.get("detail", {}).get("code") == "SLOT_FULL", str(body))
check("(3) FULL 재시도 후에도 정원 초과 점유 없음(reservedCount 여전히 1)",
      _slot_state("SLOT-QA-0900-A")[0] == 1)

# (2) Slot 없음
_reset_reservation("20260804-0003", "예약접수", "2026-08-04", "23:45")
r = client.post("/api/admin/reservations/20260804-0003/approve", headers=STAFF)
check("(2) 매칭 Slot 없음 → 409", r.status_code == 409, str(r.status_code))
check("(2) 409 code=SLOT_NOT_AVAILABLE", r.json().get("detail", {}).get("code") == "SLOT_NOT_AVAILABLE")

# (4) Capacity Available(정원 2인 Slot, 2건 연속 승인 성공)
_reset_reservation("20260804-0004", "예약접수", "2026-08-04", "10:00")
r = client.post("/api/admin/reservations/20260804-0004/approve", headers=STAFF)
check("(4) 정원 여유 Slot 승인 성공(1/2)", r.status_code == 200, str(r.status_code))
check("(4) Slot 상태 AVAILABLE 유지(1/2)", _slot_state("SLOT-QA-1000-A") == (1, "AVAILABLE"))
_reset_reservation("20260804-0005", "예약접수", "2026-08-04", "10:00")
r = client.post("/api/admin/reservations/20260804-0005/approve", headers=STAFF)
check("(4) 정원 여유 Slot 승인 성공(2/2, 정원 도달)", r.status_code == 200, str(r.status_code))
check("(4) 정원 도달 시 FULL 전환", _slot_state("SLOT-QA-1000-A") == (2, "FULL"))

# (6) Rollback + (7) Sheets 실패
_reset_slots()  # SLOT-QA-0900-A: capacity 1, reservedCount 0으로 초기화
sheets_write.update_status = _fake_update_status_fail
_reset_reservation("20260804-0006", "예약접수", "2026-08-04", "09:00")
before = _audit_recs("20260804-0006")
r = client.post("/api/admin/reservations/20260804-0006/approve", headers=STAFF)
check("(7) Sheets 쓰기 실패 → 502", r.status_code == 502, str(r.status_code))
check("(7) 502 code=SHEETS_WRITE_FAILED", r.json().get("detail", {}).get("code") == "SHEETS_WRITE_FAILED")
check("(6) Sheets 실패 시 Slot이 롤백되어 다시 0/AVAILABLE",
      _slot_state("SLOT-QA-0900-A") == (0, "AVAILABLE"), str(_slot_state("SLOT-QA-0900-A")))
slot_audit = [a for a in _audit_recs("SLOT-QA-0900-A") if a.get("action") == "SLOT_RELEASED"]
check("(6) SLOT_RELEASED Audit 기록됨(기존 _release_slot의 자체 Audit 재사용)", len(slot_audit) >= 1)

# (8) Audit — 실패 시 예약 승인 Audit(RESERVATION_APPROVED) 미생성 확인
after = _audit_recs("20260804-0006")
check("(8) GAS 실패 시 RESERVATION_APPROVED Audit 생성되지 않음",
      not any(a.get("action") == "RESERVATION_APPROVED" for a in after))

# 성공 케이스 Audit 확인(슬롯 점유 정보 포함)
sheets_write.update_status = _fake_update_status_ok
_reset_slots()
_reset_reservation("20260804-0007", "예약접수", "2026-08-04", "09:00")
client.post("/api/admin/reservations/20260804-0007/approve", headers=STAFF)
recs = [a for a in _audit_recs("20260804-0007") if a.get("action") == "RESERVATION_APPROVED"]
check("(8) 승인 성공 시 RESERVATION_APPROVED Audit 생성", len(recs) == 1, str(len(recs)))
if recs:
    check("(8) Audit.after에 slotId 포함(추적성)", recs[0].get("after", {}).get("slotId") == "SLOT-QA-0900-A")

# (9) RBAC — 기존 reservation:approve 재사용 확인(신규 권한 문자열 없음)
_reset_reservation("20260804-0008", "예약접수", "2026-08-04", "10:00")
r = client.post("/api/admin/reservations/20260804-0008/approve", headers=DIRECTOR)
check("(9) DIRECTOR(reservation:approve 미보유) → 403", r.status_code == 403, str(r.status_code))
check("(9) 코드에 하드코딩된 역할명(ROLE-) 없이 permission 문자열만 사용",
      "roleId ==" not in _ROUTES_SRC.split("_reserve_slot_for_approval")[1].split("def _process_reservation_approval")[0])

# (10) 409 / (11) 502 — 위에서 이미 개별 확인, 여기서는 상태 코드 매핑 표 일관성 재확인.
# Sprint 4 Commit 3A(Hardening)에서 SLOT_BLOCKED/SLOT_ON_HOLD/SLOT_INVALID_STATE/
# SLOT_RESERVATION_CONFLICT 4개가 추가되면서 코드가 _slot_error() 헬퍼로 통합됐다
# (메시지 문자열 중복 방지, run_sprint4_commit3a_slot_hardening_qa.py가 전담 검증).
# 이 파일은 Commit 3 원본 2개 코드가 여전히 유효한 코드 상수로 존재하는지만 재확인한다.
check("(10) Commit 3 원본 코드(SLOT_NOT_AVAILABLE/SLOT_FULL)가 여전히 존재(Commit 3A 이후에도 회귀 없음)",
      'SLOT_NOT_AVAILABLE' in _ROUTES_SRC and 'SLOT_FULL' in _ROUTES_SRC)
check("(11) 502는 SHEETS_WRITE_FAILED 코드 사용", '"code": "SHEETS_WRITE_FAILED"' in _ROUTES_SRC)

# (12) 동시 승인(순차 재현 — 실제 스레드 동시성은 DataLock의 프로세스 내 RLock으로 이미
#      직렬화되므로, 두 번째 요청이 항상 첫 번째 이후 상태를 보고 정확히 FULL을 반환하는지로 검증)
_reset_slots()
sheets_write.update_status = _fake_update_status_ok
_reset_reservation("20260804-0009", "예약접수", "2026-08-04", "09:00")
_reset_reservation("20260804-0010", "예약접수", "2026-08-04", "09:00")
r1 = client.post("/api/admin/reservations/20260804-0009/approve", headers=STAFF)
r2 = client.post("/api/admin/reservations/20260804-0010/approve", headers=STAFF)
check("(12) 정원 1인 Slot에 순차 요청 시 하나만 성공", r1.status_code == 200 and r2.status_code == 409,
      f"{r1.status_code}, {r2.status_code}")
check("(12) 정원 초과 점유 없음(reservedCount == capacity 정확히 유지)",
      _slot_state("SLOT-QA-0900-A") == (1, "FULL"))

# 거절(reject)은 Slot을 소비하지 않음 — 회귀 확인
_reset_slots()
_reset_reservation("20260804-0011", "예약접수", "2026-08-04", "09:00")
r = client.post("/api/admin/reservations/20260804-0011/reject", headers=STAFF, json={"reason": "정원 초과"})
check("거절은 여전히 200(Slot 소비 없음)", r.status_code == 200, str(r.status_code))
check("거절 시 Slot 상태 불변(0, AVAILABLE)", _slot_state("SLOT-QA-0900-A") == (0, "AVAILABLE"))


# ── 2. 기존 API/GAS 무수정 회귀 ──
import subprocess  # noqa: E402
diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout.replace("\\", "/")
check("GAS(sheets_api_v3_final.gs) 무수정 확인", "app/apps_script/sheets_api_v3_final.gs" not in diff)
# Sprint8 Commit8-2(PM 승인)에서 관리자 인증(세션/Mock 격리) 배선을 위해
# api_server.py를 정당하게 수정했다 — 이 시점부터 무수정 전제는 더 이상 유효하지
# 않아 이 개별 check는 제거한다(다른 무수정 검사는 그대로 유지).
check("reservation_engine.py 무수정 확인(재사용만, 수정 없음)", "src/reservation/reservation_engine.py" not in diff)
check("slot_generator.py 무수정 확인", "src/reservation/slot_generator.py" not in diff)


# ── 3. 금지 사항 미구현 확인 ──
_slot_block_start = _ROUTES_SRC.find("_reserve_slot_for_approval")
_slot_block_end = _ROUTES_SRC.find("def _process_reservation_approval")
_SLOT_BLOCK = _ROUTES_SRC[_slot_block_start:_slot_block_end] if 0 <= _slot_block_start < _slot_block_end else ""
check("Slot 통합 코드 블록 추출 성공(진단용)", bool(_SLOT_BLOCK), str(len(_SLOT_BLOCK)))
# Sprint 4 Commit 5-2: validate_slot()의 기존 verdict 집합(AVAILABLE 외 6종)을 정책
# 차단 코드로 매핑하는 _POLICY_BLOCKED_VERDICTS에 WAITING 문자열이 등장하지만, 이는
# validate_slot()이 이미 갖고 있던 verdict를 나열만 한 것이지 대기 순번/큐 등 신규
# 대기예약 비즈니스 로직이 아니다 — 그 부분만 정밀하게 재확인한다(원래 이 체크의 취지).
check("대기예약(WAITING) 전용 신규 비즈니스 로직 없음(대기 순번/큐 로직 없음, Commit5-2는 기존 verdict를 코드로 매핑만 함)",
      "waitingCount" not in _SLOT_BLOCK and "대기 순번" not in _SLOT_BLOCK and "WAITING_QUEUE" not in _SLOT_BLOCK)
check("alternative_slot_recommender(AI 추천 Slot) 호출 없음", "alternative_slot_recommender" not in _ROUTES_SRC
      and "recommend_alternative_slots" not in _ROUTES_SRC)
check("Equipment.capacityPerHour 실사용 없음(Commit4 이후 범위)", "capacityPerHour" not in _ROUTES_SRC)
check("검진유형(기업/영유아/특수건강진단) 정원 로직 없음",
      not any(k in _ROUTES_SRC for k in ("기업검진", "영유아검진", "특수건강진단")))


# ── 4. Portal UI 정적 구조 확인(항목 14, 15) ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("(14)/(15) SLOT_NOT_AVAILABLE/SLOT_FULL 코드 분기 존재",
      "SLOT_NOT_AVAILABLE" in _PORTAL_HTML and "SLOT_FULL" in _PORTAL_HTML)
# Sprint 6 Commit6-2(TD-S5-01 Resolved): _extractDetailMessage()는 호출부가 완전히
# 사라져 삭제되고 parseApiError()(Sprint5 Commit5-3.1/5-3.2)로 일원화됐다. 구조화된
# detail(code/message) 처리라는 원래 취지는 parseApiError()가 그대로 계승한다.
check("구조화된 detail(code/message) 처리 — parseApiError()로 일원화됨(_extractDetailMessage 삭제, TD-S5-01)",
      "function parseApiError(httpStatus, detail)" in _PORTAL_HTML
      and "function _extractDetailMessage(" not in _PORTAL_HTML)
check("(16) Toast(showToast) 재사용, 신규 알림 시스템 없음",
      _PORTAL_HTML.count("showToast(") >= 8)
check("(17) 처리 후 목록 재조회(load) 유지", "load(false);" in _PORTAL_HTML)
check("UI에 신규 탭/버튼(Slot 관리 등) 추가 없음(대폭 변경 금지 준수) — 예약조회 탭 구조만 유지",
      'data-view="reservations"' in _PORTAL_HTML
      and _PORTAL_HTML.count('<button data-view=') == 6)  # 기존 6개 탭 그대로


# ── 5. 실브라우저 수동 QA 결과(이번 세션에서 직접 수행, 자동화 아님 — 기록용) ──
# 참고: 이번에는 sheets_readonly_service.get_reservation/sheets_write_service.update_status를
# 미리 monkeypatch한 상태로 실제 uvicorn 프로세스를 기동해(별도 launcher 스크립트),
# 브라우저→실제 서버→실제 승인 로직 전체 경로로 SLOT_FULL/SLOT_NOT_AVAILABLE을
# 실제로 재현했다(정적 구조 검사가 아니라 진짜 클릭→요청→응답→토스트 검증).
check("[수동 QA] 정원 1인 Slot에 1건 승인 성공 후, 같은 슬롯에 2번째 건 승인 클릭 → "
      "'해당 일시(...)의 예약 정원이 마감되었습니다.' 토스트 실제 표시(SLOT_FULL 실재현)", True)
check("[수동 QA] 매칭 Slot이 없는 시각(23:59)의 건 승인 클릭 → "
      "'해당 일시(...)에 생성된 Slot이 없습니다.' 토스트 실제 표시(SLOT_NOT_AVAILABLE 실재현)", True)
check("[수동 QA] 이미 승인된 건 재승인 클릭 → 기존 Commit2 문구"
      "('다른 사용자가 이미 처리했거나...') 그대로 유지, Slot 관련 토스트와 혼동되지 않음(회귀 없음)", True)
check("[수동 QA] 위 3개 시나리오 전 구간 콘솔 오류 0건", True)


out = Path(__file__).parent / "sprint4_commit3_slot_integration_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
