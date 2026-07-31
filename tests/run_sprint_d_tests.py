# -*- coding: utf-8 -*-
"""
CSHSP Sprint D 테스트 러너 — API Layer
FastAPI TestClient로 REST API를 검증한다. (샌드박스 사본 사용, 원본 data/ 불변)
결과: tests/sprint_d_test_result.csv
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
sys.path.insert(0, str(ROOT / "src" / "reservation"))
sys.path.insert(0, str(ROOT / "src" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint_d" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

client = TestClient(create_app(SANDBOX))
STAFF = {"X-User-Id": "USR-0002"}
AI = {"X-User-Id": "USR-9000"}
DIRECTOR = {"X-User-Id": "USR-0001"}

# Sprint8 Commit8-2c STEP2: 승인/취소(상태변경)는 Mock이 차단된다. 이 파일은
# client(Mock)를 조회·생성 등 다른 목적에 계속 광범위하게 쓰므로, 상태변경
# 호출 전용의 별도 세션 client만 새로 만든다(메인 client에 세션 로그인을
# 하면 이후 다른 Mock 기반 호출들이 전부 그 세션 신원으로 바뀌어버린다).
from _step2_session_helper import ensure_session  # noqa: E402
client_staff = TestClient(create_app(SANDBOX))
STAFF_CSRF = ensure_session(
    client_staff, SANDBOX, user_id="USR-0002", role_id="ROLE-STAFF",
    display_name="QA STAFF", login_id="qa_step2_d_staff",
)
client_ai = TestClient(create_app(SANDBOX))
AI_CSRF = ensure_session(
    client_ai, SANDBOX, user_id="USR-9000", role_id="ROLE-AI-AGENT",
    display_name="QA AI", login_id="qa_step2_d_ai",
)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# ── 1. 기본 / 인증 ──
r = client.get("/api/health")
check("GET /api/health", r.status_code == 200 and r.json()["entities"]["Reservation"] == 5,
      f"entities={sum(r.json()['entities'].values())}건")
check("인증 없음 → 401", client.get("/api/reservations").status_code == 401)
check("무효 사용자 → 401", client.get("/api/reservations", headers={"X-User-Id": "USR-XXXX"}).status_code == 401)

# ── 2. Reservation API 조회 ──
r = client.get("/api/reservations", headers=STAFF)
check("GET /api/reservations (직원)", r.status_code == 200 and r.json()["count"] == 5)
row = r.json()["records"][0]
check("목록 개인정보 마스킹", "****" in row["patientBirthMasked"] and "****" in row["patientPhoneMasked"],
      f"{row['patientBirthMasked']} / {row['patientPhoneMasked']}")
check("상태 필터", client.get("/api/reservations?status=WAITING", headers=STAFF).json()["count"] == 1)
check("검색(전화 뒷4자리)", client.get("/api/reservations?query=0002", headers=STAFF).json()["count"] >= 1)
check("GET /api/reservations/pending", client.get("/api/reservations/pending", headers=STAFF).json()["count"] == 1)

r = client.get("/api/reservations/RSV-20260702-0002", headers=STAFF)
d = r.json()
check("GET 상세 + allowedNext", r.status_code == 200
      and d["allowedNext"] == ["CANCELLED", "CONFIRMED", "REJECTED"]
      and d["patient"]["phone"] == "010-0000-0002", "직원=전체 표시")
check("AI 상세조회 차단 (reservation:view 없음) → 403",
      client.get("/api/reservations/RSV-20260702-0002", headers=AI).status_code == 403)
r = client.get("/api/reservations/RSV-20260702-0002", headers={"X-User-Id": "USR-0003"})  # 콜센터 ROLE-CRM
check("상세 개인정보 역할 마스킹 (CRM)", r.json()["patient"]["phone"] == "010-****-0002",
      r.json()["patient"]["phone"])

# ── 3. Slot API ──
r = client.post("/api/slots/generate", headers=STAFF,
                json={"startDate": "2026-07-21", "endDate": "2026-07-22", "capacity": 6})
check("POST /api/slots/generate (직원)", r.status_code == 201 and r.json()["created"] == 20, f"{r.json()['created']}개")
check("Slot 생성 권한 차단 (AI)", client.post("/api/slots/generate", headers=AI,
      json={"startDate": "2026-07-23", "endDate": "2026-07-23"}).status_code == 403)
check("GET /api/slots + 날짜 필터",
      client.get("/api/slots?from=2026-07-21&to=2026-07-22", headers=STAFF).json()["count"] == 20)
r = client.get("/api/slots/recommend?date=2026-07-08&time=09:00&programId=PRG-BASIC", headers=STAFF)
check("GET /api/slots/recommend (≤5)", 0 < len(r.json()["records"]) <= 5, f"{len(r.json()['records'])}개")

# ── 4. 예약 신청 → 승인 → 취소 파이프라인 (엔진 경유) ──
body = {"patientId": "PT-2026-0003", "programId": "PRG-BASIC", "requestedDate": "2026-07-21",
        "requestedTime": "09:00", "slotId": "SLOT-20260721-0900-A", "channel": "AI_ASSISTANT"}
r = client.post("/api/reservations", headers=AI, json=body)
RID = r.json().get("reservation", {}).get("id", "")
check("POST /api/reservations (AI 신청)", r.status_code == 201
      and r.json()["reservation"]["status"] == "PENDING_APPROVAL", RID)
slot = client.get("/api/slots?status=HOLD", headers=STAFF).json()
check("신청 후 Slot HOLD", any(s["id"] == "SLOT-20260721-0900-A" for s in slot["records"]))

check("AI 승인 차단 → 403", client_ai.post(f"/api/reservations/{RID}/approve", headers=AI_CSRF).status_code == 403)
r = client_staff.post(f"/api/reservations/{RID}/approve", headers=STAFF_CSRF)
check("직원 승인 → CONFIRMED", r.status_code == 200 and r.json()["reservation"]["status"] == "CONFIRMED")

r = client_staff.post(f"/api/reservations/{RID}/cancel", headers=STAFF_CSRF, json={"reason": "QA"})
check("취소 → CANCELLED", r.status_code == 200 and r.json()["reservation"]["status"] == "CANCELLED")
check("취소건 재승인 → 409", client_staff.post(f"/api/reservations/{RID}/approve", headers=STAFF_CSRF).status_code == 409)

# ── 5. 검증 실패 응답 (422 + 대체 슬롯) ──
dup = client.post("/api/reservations", headers=AI, json={**body, "patientId": "PT-2026-0001",
                  "requestedDate": "2026-07-08", "slotId": "SLOT-20260708-0830-A"})
det = dup.json()["detail"]
check("중복예약 → 422 + verdict", dup.status_code == 422 and det["verdict"] == "DUPLICATED")
full = client.post("/api/reservations", headers=AI, json={**body, "patientId": "PT-2026-0004",
                   "requestedDate": "2026-07-08", "requestedTime": "09:00", "slotId": "SLOT-20260708-0900-A"})
check("FULL Slot → 422 + 대체 ≤5", full.status_code == 422
      and full.json()["detail"]["verdict"] == "FULL" and 0 < len(full.json()["detail"]["alternatives"]) <= 5)

# ── 6. HOLD 해제 ──
r = client.post("/api/slots/SLOT-20260715-1000-A/release-hold", headers=STAFF)
check("HOLD 해제 (직원)", r.status_code == 200 and r.json()["slot"]["status"] == "AVAILABLE")
check("HOLD 해제 권한 차단 (AI)",
      client.post("/api/slots/SLOT-20260708-0830-A/release-hold", headers=AI).status_code == 403)

# ── 7. Admin / Dashboard / Audit API ──
check("GET /api/admin/schedules?tab=holiday",
      client.get("/api/admin/schedules?tab=holiday", headers=STAFF).json()["count"] == 1)
check("GET /api/admin/users (민감필드 제외)",
      all("email" not in u for u in client.get("/api/admin/users", headers=STAFF).json()["records"]))
k = client.get("/api/dashboard/kpi", headers=DIRECTOR).json()
check("GET /api/dashboard/kpi (병원장)", k["pending"] == 1 and k["confirmed"] == 1 and "slotUtilization" in k,
      json.dumps({x: k[x] for x in ("pending", "confirmed", "cancelled", "slotUtilization", "onlineRatio")}))
r = client.get("/api/audit-logs?action=RESERVATION_APPROVED", headers=DIRECTOR)
check("GET /api/audit-logs 필터 (audit:view)", r.status_code == 200 and r.json()["count"] >= 2)
check("감사로그 대상 검색", client.get(f"/api/audit-logs?query={RID}", headers=STAFF).json()["count"] >= 3)

# ── 8. 동시성 보호: 병렬 신청 8건 → 예약번호 유일성 ──
def _create(i):
    pid = "PT-2026-0003" if i < 4 else "PT-2026-0004"
    date = f"2026-07-2{(i % 4) + 1}"  # 21~24 중 21,22는 생성됨 → 21/22만 사용
    date = "2026-07-21" if i % 2 == 0 else "2026-07-22"
    t = ["08:00", "08:30", "10:00", "10:30"][i % 4]
    return client.post("/api/reservations", headers=STAFF, json={
        "patientId": pid, "programId": "PRG-BASIC", "requestedDate": date,
        "requestedTime": t, "slotId": f"SLOT-{date.replace('-', '')}-{t.replace(':', '')}-A",
        "channel": "PHONE"})

with ThreadPoolExecutor(max_workers=8) as ex:
    responses = list(ex.map(_create, range(8)))
created = [r.json()["reservation"] for r in responses if r.status_code == 201]
nos = [c["reservationNo"] for c in created]
check("동시 신청 처리 (스레드 8)", len(created) >= 2, f"성공 {len(created)}건 (중복차단 등 제외)")
check("예약번호 채번 충돌 없음 (Lock)", len(nos) == len(set(nos)), f"{sorted(nos)}")
try:
    json.loads((SANDBOX / "reservations.json").read_text(encoding="utf-8"))
    check("동시 쓰기 후 JSON 무결성", True)
except json.JSONDecodeError as e:
    check("동시 쓰기 후 JSON 무결성", False, str(e))

# ── 9. 최종 무결성 (Sprint A Validator) + 원본 보호 ──
res = validator.validate_all(loader.load_all(SANDBOX))
check("전체 데이터 무결성", len(res["errors"]) == 0, f"오류 {len(res['errors'])}건, 경고 {len(res['warnings'])}건")
for e in res["errors"][:5]:
    print(f"    [오류] {e}")
check("원본 data/ 미변경", len(loader.load_entity("Reservation", ROOT / "data")) == 5)
r = client.get("/api/admin/validate", headers=STAFF)
check("GET /api/admin/validate", r.status_code == 200 and r.json()["pass"] is True)

# ── 저장 ──
out = Path(__file__).parent / "sprint_d_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, x, _ in results if x == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
