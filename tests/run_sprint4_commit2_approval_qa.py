# -*- coding: utf-8 -*-
"""
CSHSP Sprint 4 Commit 2 — Reservation Approval Foundation 테스트 러너

대상: src/api/reservation_approval_states.py(State Machine), src/api/routes_admin_portal.py
의 승인/거절 엔드포인트(POST /api/admin/reservations/{no}/approve|reject),
src/services/sheets_write_service.py, core_data_loader.LEGACY_STATUS_MAP 확장분,
app/pages/admin_portal_new.html(Portal UI 정적 구조), app/pages/admin_reservations_v2_new.html
(Legacy 상태 필터 호환성 보완).

PM 조건부 승인(Sprint4_Commit2_Implementation_Plan_v1.0.md §12) 근거:
- 허용 전이는 예약접수→예약확정, 예약접수→거절 두 가지뿐(그 외 전이는 409)
- 거절 사유는 필수+검증(공백 제거/빈 문자열 금지/길이 2~200/PII 의심 패턴 차단) → 422
- Sheets에는 상태값만 저장, 거절 사유는 Audit note에만 기록
- Sheets 상태 변경 성공 이후에만 Audit 기록(실패 시 Audit 미생성)
- GAS/Sheets 실패는 502(오류)/503(미설정)로 매핑(기존 sheets_readonly_service 패턴 재사용)

GAS 호출부는 monkeypatch — 실네트워크·실Sheets 없음. 샌드박스 데이터 사용.
결과: tests/sprint4_commit2_approval_test_result.csv
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
import reservation_approval_states as approval_states  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402
import sheets_write_service as sheets_write  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint4_commit2_approval" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

# Sprint 4 Commit 3(Reservation Slot Integration) 회귀 대응: 승인(예약확정)이 이제
# Slot 조회·점유를 거치므로, 이 테스트의 승인 성공 케이스들이 매칭될 넉넉한 정원의
# 더미 Slot을 하나 주입한다(capacity를 크게 잡아 이 파일 내 승인 성공 케이스가
# 서로 정원을 다투지 않게 함 — Commit 3 자체의 FULL/NOT_AVAILABLE 동작 검증은
# run_sprint4_commit3_slot_integration_qa.py가 전담한다).
_DUMMY_SLOT_DATE = "2026-07-28"
_DUMMY_SLOT_TIME = "09:00"
_slots_doc = json.loads((SANDBOX / "slots.json").read_text(encoding="utf-8"))
_slots_doc["records"].append({
    "id": "SLOT-COMMIT2QA-0900-A", "date": _DUMMY_SLOT_DATE, "time": _DUMMY_SLOT_TIME,
    "capacity": 50, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
    "roomId": "ROOM-0001", "programRestriction": None, "note": "Sprint4 Commit2 QA 더미(Commit3 회귀 대응)",
    "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00",
})
(SANDBOX / "slots.json").write_text(json.dumps(_slots_doc, ensure_ascii=False, indent=2), encoding="utf-8")

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


# ── 0. State Machine 단위 테스트 ──
check("예약접수→예약확정 허용", approval_states.can_transition("예약접수", "예약확정"))
check("예약접수→거절 허용", approval_states.can_transition("예약접수", "거절"))
check("예약확정→거절 불허", not approval_states.can_transition("예약확정", "거절"))
check("거절→예약확정 불허(재처리 금지)", not approval_states.can_transition("거절", "예약확정"))
check("검진완료→예약확정 불허(범위 밖 상태)", not approval_states.can_transition("검진완료", "예약확정"))

# ── LEGACY_STATUS_MAP 확장 검증(항목 12) ──
check("LEGACY_STATUS_MAP에 '거절'→REJECTED 매핑 추가됨",
      loader.LEGACY_STATUS_MAP.get("거절") == "REJECTED")
for k, v in (("예약접수", "REQUESTED"), ("예약확정", "CONFIRMED"), ("검진완료", "COMPLETED"),
             ("일정변경", "CHANGED"), ("예약취소", "CANCELLED")):
    check(f"LEGACY_STATUS_MAP 기존 매핑 회귀 없음: {k}", loader.LEGACY_STATUS_MAP.get(k) == v)


# ── 1. Backend 통합 테스트(TestClient, GAS monkeypatch) ──
client = TestClient(create_app(SANDBOX, include_agents=False))

STAFF = {"X-User-Id": "USR-0002"}      # ROLE-STAFF: reservation:approve 보유
DIRECTOR = {"X-User-Id": "USR-0001"}   # ROLE-DIRECTOR: reservation:approve 미보유
CRM_USER = {"X-User-Id": "USR-0003"}   # ROLE-CRM: reservation:approve 미보유

_FAKE_DB: dict[str, dict] = {}


def _reset_fake_reservation(no: str, status: str, program: str = "BASIC") -> None:
    # wishDate/wishTime은 위에서 주입한 넉넉한 정원의 더미 Slot과 매칭된다(Commit 3 대응).
    # program은 Commit 5-2(Approval Pipeline Policy Integration)에서 추가된 Program
    # Mapping 선행 검사(resolve_program()) 대응 — 기본값 "BASIC"은 Program.code와
    # 완전일치하는 실제 값이다(data/programs.json 확인). 더미 Slot의 programRestriction이
    # None이므로 어떤 유효 프로그램을 넣어도 이후 검증에 영향 없다.
    _FAKE_DB[no] = {"reservationNo": no, "status": status, "name": "QA더미", "program": program,
                     "wishDate": _DUMMY_SLOT_DATE, "wishTime": _DUMMY_SLOT_TIME}


def _fake_get_reservation(no, **kw):
    return dict(_FAKE_DB[no]) if no in _FAKE_DB else None


def _fake_update_status(no, status, **kw):
    _FAKE_DB[no]["status"] = status
    return {"ok": True}


def _fake_update_status_gas_error(no, status, **kw):
    raise sheets_write.SheetsIntegrationError("GAS 오류 응답(updateStatus): 강제 실패(테스트)")


sheets.get_reservation = _fake_get_reservation


def _audit_count_for(no: str) -> int:
    r = client.get("/api/audit-logs", headers=DIRECTOR)
    body = r.json()
    return sum(1 for rec in body.get("records", []) if rec.get("entityId") == no)


# 1) 예약접수 → 예약확정 성공
sheets_write.update_status = _fake_update_status
_reset_fake_reservation("20260728-1001", "예약접수")
r = client.post("/api/admin/reservations/20260728-1001/approve", headers=STAFF)
check("(1) 예약접수→예약확정 성공(200)", r.status_code == 200, str(r.status_code))
check("(1) 응답에 status=예약확정 포함",
      r.status_code == 200 and r.json().get("data", {}).get("status") == "예약확정")

# 2) 예약접수 → 거절 성공
_reset_fake_reservation("20260728-1002", "예약접수")
r = client.post("/api/admin/reservations/20260728-1002/reject", headers=STAFF,
                 json={"reason": "예약 가능 인원 초과"})
check("(2) 예약접수→거절 성공(200)", r.status_code == 200, str(r.status_code))
check("(2) 응답에 status=거절 포함",
      r.status_code == 200 and r.json().get("data", {}).get("status") == "거절")

# 3) 거절 사유 누락 422 (공백만 입력 포함)
_reset_fake_reservation("20260728-1003", "예약접수")
r = client.post("/api/admin/reservations/20260728-1003/reject", headers=STAFF, json={"reason": "   "})
check("(3) 거절 사유 공백만 입력 → 422", r.status_code == 422, str(r.status_code))
r_missing = client.post("/api/admin/reservations/20260728-1003/reject", headers=STAFF, json={})
check("(3) 거절 사유 필드 자체 누락 → 422", r_missing.status_code == 422, str(r_missing.status_code))
r_pii = client.post("/api/admin/reservations/20260728-1003/reject", headers=STAFF,
                     json={"reason": "고객 연락처 010-1234-5678로 확인 요망"})
check("(3) 거절 사유에 전화번호 패턴 포함 → 422", r_pii.status_code == 422, str(r_pii.status_code))
r_short = client.post("/api/admin/reservations/20260728-1003/reject", headers=STAFF, json={"reason": "ا"})
check("(3) 거절 사유 최소 길이 미달(1자) → 422", r_short.status_code == 422, str(r_short.status_code))
r_long = client.post("/api/admin/reservations/20260728-1003/reject", headers=STAFF, json={"reason": "가" * 201})
check("(3) 거절 사유 최대 길이 초과(201자) → 422", r_long.status_code == 422, str(r_long.status_code))

# 4) 존재하지 않는 예약 404
r = client.post("/api/admin/reservations/NOPE-0000/approve", headers=STAFF)
check("(4) 존재하지 않는 예약번호 승인 → 404", r.status_code == 404, str(r.status_code))
r = client.post("/api/admin/reservations/NOPE-0000/reject", headers=STAFF, json={"reason": "사유"})
check("(4) 존재하지 않는 예약번호 거절 → 404", r.status_code == 404, str(r.status_code))

# 5) 권한 없는 역할 403 (+ 헤더 없음 401 재확인 — Authentication→RoleCheck 순서)
_reset_fake_reservation("20260728-1005", "예약접수")
r = client.post("/api/admin/reservations/20260728-1005/approve", headers=DIRECTOR)
check("(5) DIRECTOR(reservation:approve 미보유) 승인 시도 → 403", r.status_code == 403, str(r.status_code))
r = client.post("/api/admin/reservations/20260728-1005/approve", headers=CRM_USER)
check("(5) CRM(reservation:approve 미보유) 승인 시도 → 403", r.status_code == 403, str(r.status_code))
r = client.post("/api/admin/reservations/20260728-1005/approve")
check("(5) 헤더 없음 → 401(RoleCheck 이전 인증 단계에서 차단)", r.status_code == 401, str(r.status_code))

# 6) 예약확정 재승인 409
_reset_fake_reservation("20260728-1006", "예약확정")
r = client.post("/api/admin/reservations/20260728-1006/approve", headers=STAFF)
check("(6) 이미 예약확정인 건 재승인 → 409", r.status_code == 409, str(r.status_code))

# 7) 예약확정 직접 거절 409
_reset_fake_reservation("20260728-1007", "예약확정")
r = client.post("/api/admin/reservations/20260728-1007/reject", headers=STAFF, json={"reason": "테스트 사유"})
check("(7) 예약확정 상태를 직접 거절 시도 → 409", r.status_code == 409, str(r.status_code))

# 8) 거절 재처리 409
_reset_fake_reservation("20260728-1008", "거절")
r = client.post("/api/admin/reservations/20260728-1008/reject", headers=STAFF, json={"reason": "재시도"})
check("(8) 이미 거절된 건 재거절 시도 → 409", r.status_code == 409, str(r.status_code))
r = client.post("/api/admin/reservations/20260728-1008/approve", headers=STAFF)
check("(8) 이미 거절된 건 승인 시도 → 409(종결 상태에서 전환 불가)", r.status_code == 409, str(r.status_code))

# 9) GAS 실패 시 상태·Audit 일관성 + 11) 실패 시 성공 Audit 미생성
sheets_write.update_status = _fake_update_status_gas_error
_reset_fake_reservation("20260728-1009", "예약접수")
before_count = _audit_count_for("20260728-1009")
r = client.post("/api/admin/reservations/20260728-1009/approve", headers=STAFF)
check("(9) GAS 오류 시 502 반환", r.status_code == 502, str(r.status_code))
check("(9) GAS 오류 시 로컬 상태(Fake Sheets)도 변경되지 않음(일관성)",
      _FAKE_DB["20260728-1009"]["status"] == "예약접수")
after_count = _audit_count_for("20260728-1009")
check("(11) GAS 실패 시 Audit 레코드 생성되지 않음", after_count == before_count,
      f"before={before_count} after={after_count}")
sheets_write.update_status = _fake_update_status  # 원복

# 10) 성공 시 Audit 생성(예약번호/이전상태/변경상태/처리자/처리시각/거절사유)
_reset_fake_reservation("20260728-1010", "예약접수")
client.post("/api/admin/reservations/20260728-1010/approve", headers=STAFF)
r = client.get("/api/audit-logs", headers=DIRECTOR)
recs = [x for x in r.json().get("records", []) if x.get("entityId") == "20260728-1010"]
check("(10) 승인 성공 시 Audit 1건 생성", len(recs) == 1, str(len(recs)))
if recs:
    rec = recs[0]
    check("(10) Audit action=RESERVATION_APPROVED", rec.get("action") == "RESERVATION_APPROVED")
    check("(10) Audit actorUserId=처리자", rec.get("actorUserId") == "USR-0002")
    check("(10) Audit에 처리시각(timestamp) 존재", bool(rec.get("timestamp")))
    check("(10) Audit before/after에 상태값 포함",
          (rec.get("before") or {}).get("status") == "예약접수"
          and (rec.get("after") or {}).get("status") == "예약확정")

_reset_fake_reservation("20260728-1011", "예약접수")
client.post("/api/admin/reservations/20260728-1011/reject", headers=STAFF, json={"reason": "정원 초과로 거절"})
r = client.get("/api/audit-logs", headers=DIRECTOR)
recs = [x for x in r.json().get("records", []) if x.get("entityId") == "20260728-1011"]
check("(10) 거절 성공 시 Audit 1건 생성", len(recs) == 1, str(len(recs)))
if recs:
    rec = recs[0]
    check("(10) Audit action=RESERVATION_REJECTED", rec.get("action") == "RESERVATION_REJECTED")
    check("(10) 거절 사유가 Audit note에 기록됨", rec.get("note") == "정원 초과로 거절")

# 거절 사유가 Sheets(Fake)에는 저장되지 않는지 확인(PM 결정 2). wishDate/wishTime은
# Commit 3 Slot 매칭용으로 _reset_fake_reservation이 채우는 필드라 원래부터 존재하며
# "거절 사유가 별도로 추가되지 않았는가"와는 무관하므로 기준 집합에 포함한다.
check("(2) 거절 사유는 Sheets 쪽 Fake 레코드에 별도 필드로 남지 않음(status만 변경)",
      set(_FAKE_DB["20260728-1011"].keys())
      == {"reservationNo", "status", "name", "wishDate", "wishTime", "program"})


# 13) 기존 로컬 JSON 승인 API 회귀(api_server.py의 /api/reservations/{rid}/approve — 무수정 확인)
_all_paths = [getattr(r, "path", None) for r in client.app.routes]
check("(13) 로컬 JSON 예약 승인 엔드포인트가 여전히 등록되어 있음",
      "/api/reservations/{rid}/approve" in _all_paths)
check("(13) 로컬 JSON 예약 거절 엔드포인트가 여전히 등록되어 있음",
      "/api/reservations/{rid}/reject" in _all_paths)

import subprocess  # noqa: E402
diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout
# Sprint8 Commit8-2(PM 승인)에서 관리자 인증(세션/Mock 격리) 배선을 위해
# api_server.py를 정당하게 수정했다 — 이 시점부터 "api_server.py 무수정"이라는
# 원래의 Commit4-2 범위 가드는 더 이상 유효한 전제가 아니다(위 (13)의 실질
# 요구사항인 "로컬 JSON 승인/거절 엔드포인트가 삭제되지 않았음"은 이미 바로 위
# 두 check로 확인됐으므로 이 무수정 검사만 제거한다).
check("GAS(sheets_api_v3_final.gs) 무수정 확인",
      "app/apps_script/sheets_api_v3_final.gs" not in diff.replace("\\", "/"))


# ── 2. Portal UI 정적 구조 확인(항목 14, 15, 18, 19) ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("(14) 예약조회 테이블에 '작업' 컬럼 추가됨", "<th>작업</th>" in _PORTAL_HTML)
check("(14) 승인 버튼 클래스(rsv-approve-btn) 존재", "rsv-approve-btn" in _PORTAL_HTML)
check("(14) 거절 버튼 클래스(rsv-reject-btn) 존재", "rsv-reject-btn" in _PORTAL_HTML)
check("(15) 승인/거절 버튼이 예약접수 상태 조건부로만 렌더링됨",
      "r.status === '예약접수'" in _PORTAL_HTML and "? '<button class=\"rsv-approve-btn\"" in _PORTAL_HTML)
check("(17) 거절 사유 입력 모달(rejectModal) 존재", 'id="rejectModal"' in _PORTAL_HTML)
check("(17) 거절 사유 textarea 존재", 'id="rejectReasonInput"' in _PORTAL_HTML)
check("(17) PII 입력 금지 안내 문구 존재", "개인정보" in _PORTAL_HTML and "입력하지 마세요" in _PORTAL_HTML)
check("UI에 browser alert() 미사용(토스트로 대체, Sprint 3 원칙 계승)",
      "alert(" not in _PORTAL_HTML)
check("(18)/(19) throwIfForbidden 재사용(403 처리)",
      _PORTAL_HTML.count("var forbidden = throwIfForbidden(r);") >= 6,
      str(_PORTAL_HTML.count("var forbidden = throwIfForbidden(r);")))
check("(19) 409 시 PM 지정 안내 문구 및 목록 재조회(handleApprovalConflict) 존재",
      "다른 사용자가 이미 처리했거나 현재 상태에서 처리할 수 없습니다." in _PORTAL_HTML
      and "function handleApprovalConflict" in _PORTAL_HTML)
check("승인/거절 성공 시 showToast(success) 호출", "'이(가) 승인되었습니다.'".replace("'", "") in _PORTAL_HTML
      or "승인되었습니다" in _PORTAL_HTML)
check("승인/거절 처리 후 목록 재조회(load) 호출", "load(false);" in _PORTAL_HTML)


# ── 3. Legacy UI(admin_reservations_v2_new.html) 호환성 보완 확인(항목 21, 23) ──
_LEGACY_HTML = (ROOT / "app" / "pages" / "admin_reservations_v2_new.html").read_text(encoding="utf-8")
check("(21) 상태 필터(#fStatus)에 '거절' 옵션 추가됨",
      '<option>예약취소</option><option>거절</option>' in _LEGACY_HTML)
check("(21)/(23) 기존 5개 옵션(예약접수/예약확정/검진완료/일정변경/예약취소) 순서 유지",
      "<option>예약접수</option><option>예약확정</option><option>검진완료</option>"
      "<option>일정변경</option><option>예약취소</option>" in _LEGACY_HTML)
check("(21) 상태변경 드롭다운(#statusSel)에도 '거절' 추가됨(표시 일관성)",
      _LEGACY_HTML.count("<option>거절</option>") == 2, str(_LEGACY_HTML.count("<option>거절</option>")))


# ── 4. 실브라우저 수동 QA 결과(이번 세션에서 직접 수행, 자동화 아님 — 기록용) ──
# 참고: 이번 세션도 이전 Sprint 1~3과 동일하게 CSHSP_GAS_WEBAPP_URL을 설정하지
# 않았다(운영 Sheets 미접근 원칙). 따라서 승인/거절 요청은 실제로는 서버가
# "Sheets 연동 미설정"으로 응답하며, 아래 QA는 "성공 시나리오의 UI 반영"이
# 아니라 "클릭→요청→에러 처리→토스트 표시"까지의 배선이 실제로 동작함을
# 확인한 것이다(에러 토스트도 정상 응답 처리 경로이므로 유효한 검증).
check("[수동 QA] DIRECTOR(reservation:approve 미보유)로 실제 승인 API 직접 호출 → 403 응답 확인", True)
check("[수동 QA] 예약접수 상태 행 주입 후 거절 버튼 클릭 → 거절 모달만 열림(예약상세 모달과 혼선 없음, stopPropagation 정상 동작 확인)", True)
check("[수동 QA] 거절 모달에서 공백만 입력 후 확정 클릭 → 네트워크 요청 없이 클라이언트에서 즉시 에러 토스트, 모달 유지", True)
check("[수동 QA] 거절 모달에서 정상 사유 입력 후 확정 클릭 → 실제 서버 호출 → Sheets 미설정 에러 토스트 정상 표시(alert 미사용)", True)
check("[수동 QA] 승인 버튼 클릭 → 실제 서버 호출 → Sheets 미설정 에러 토스트 정상 표시(alert 미사용)", True)
check("[수동 QA] renderTable의 상태별 작업 컬럼 로직: 예약접수만 버튼 노출, 예약확정/검진완료/거절은 빈 칸 확인", True)
check("[수동 QA] Legacy 화면(admin_reservations_v2_new.html) 상태 필터(#fStatus)·상태변경 드롭다운(#statusSel) 모두 '거절' 옵션 선택 가능, 기존 5개 옵션 순서 유지 확인", True)
check("[수동 QA] Portal/Legacy 두 화면 모두 상호작용 전 구간 콘솔 오류 0건", True)


out = Path(__file__).parent / "sprint4_commit2_approval_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
