# -*- coding: utf-8 -*-
"""
CSHSP Sprint 3 — Commit 2(CRM 통합) 테스트 러너

대상: src/api/routes_admin_portal.py의 CRM 관련 헬퍼(_crm_masking_tier,
_mask_name_by_tier, _patient_name_map) + GET /api/admin/consultations +
POST /api/admin/consultations/{id}/status.

PM 승인 범위 검증 핵심:
- CRM 생성/삭제 엔드포인트가 없음(기존 crm.json 재사용만)
- 상태 전이는 OPEN→IN_PROGRESS→CLOSED 순차만 허용(역행/건너뛰기 거부)
- summary는 원문 그대로, patientName만 역할별 3단계 마스킹

샌드박스 데이터 사용(원본 data/crm.json 불변) — 실제 존재하는 기존 픽스처
(CRM-0001 CLOSED/CRM-0002 OPEN/CRM-0003 IN_PROGRESS)를 그대로 활용한다.

결과: tests/sprint3_crm_test_result.csv
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

import routes_admin_portal as rap  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint3_crm" / "data"
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


# ── 1. 마스킹 티어 단위 테스트 ──
check("ROLE-ADMIN → admin 티어", rap._crm_masking_tier({"roleId": "ROLE-ADMIN"}) == "admin")
check("ROLE-DIRECTOR → supervisor 티어", rap._crm_masking_tier({"roleId": "ROLE-DIRECTOR"}) == "supervisor")
check("ROLE-STAFF → operator 티어(기본값)", rap._crm_masking_tier({"roleId": "ROLE-STAFF"}) == "operator")
check("ROLE-CRM → operator 티어(기본값)", rap._crm_masking_tier({"roleId": "ROLE-CRM"}) == "operator")
check("알 수 없는 역할 → operator(안전한 기본값)", rap._crm_masking_tier({"roleId": "ROLE-UNKNOWN"}) == "operator")

check("admin 티어는 원문 노출", rap._mask_name_by_tier("홍길동", "admin") == "홍길동")
check("supervisor 티어는 전체이름 노출", rap._mask_name_by_tier("홍길동", "supervisor") == "홍길동")
check("operator 티어는 마스킹(홍○○)", rap._mask_name_by_tier("홍길동", "operator") == "홍○○")
check("이름 없으면 그대로(None) 반환", rap._mask_name_by_tier(None, "operator") is None)

names = rap._patient_name_map(SANDBOX)
check("_patient_name_map 정상 로드", isinstance(names, dict) and len(names) > 0, f"{len(names)}건")
check("PT-2026-0001 이름 매핑 존재", "PT-2026-0001" in names)


# ── 2. GET /api/admin/consultations 접근 매트릭스 ──
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}
DIRECTOR = {"X-User-Id": "USR-0001"}
CRM_USER = {"X-User-Id": "USR-0003"}

check("헤더 없이 조회 → 401", client.get("/api/admin/consultations").status_code == 401)
check("STAFF(crm:manage/log/audit:view 없음) → 403",
      client.get("/api/admin/consultations", headers=STAFF).status_code == 403)

r_crm = client.get("/api/admin/consultations", headers=CRM_USER)
check("ROLE-CRM(crm:manage 보유) → 200", r_crm.status_code == 200, str(r_crm.status_code))
body_crm = r_crm.json()
check("전체 3건 조회(기존 픽스처)", body_crm["count"] == 3, str(body_crm["count"]))
check("ROLE-CRM은 operator 티어 → 이름 마스킹", body_crm.get("maskingTier") == "operator")
_crm0001 = next(r for r in body_crm["data"] if r["id"] == "CRM-0001")
check("operator 티어 patientName 마스킹 형태(첫글자+○)",
      _crm0001["patientName"] and _crm0001["patientName"][1:].count("○") == len(_crm0001["patientName"]) - 1,
      str(_crm0001["patientName"]))
check("summary는 원문 그대로 노출(마스킹 없음, PM 결정사항 4)",
      isinstance(_crm0001["summary"], str) and "○" not in _crm0001["summary"], str(_crm0001["summary"]))

r_dir = client.get("/api/admin/consultations", headers=DIRECTOR)
check("DIRECTOR(audit:view 보유) → 200", r_dir.status_code == 200)
body_dir = r_dir.json()
check("DIRECTOR는 supervisor 티어 → 이름 마스킹 없음", body_dir.get("maskingTier") == "supervisor")
_dir_crm0001 = next(r for r in body_dir["data"] if r["id"] == "CRM-0001")
check("supervisor 티어 patientName에 마스킹 문자(○) 없음",
      "○" not in (_dir_crm0001["patientName"] or ""), str(_dir_crm0001["patientName"]))

check("status 필터(OPEN)", len(client.get("/api/admin/consultations", params={"status": "OPEN"}, headers=CRM_USER).json()["data"]) == 1)
check("channel 필터(AI_CHAT)", len(client.get("/api/admin/consultations", params={"channel": "AI_CHAT"}, headers=CRM_USER).json()["data"]) == 1)


# ── 3. POST /api/admin/consultations/{id}/status — 상태전이 검증 ──
check("STAFF(crm:manage 없음) → 상태변경 403",
      client.post("/api/admin/consultations/CRM-0002/status", json={"status": "IN_PROGRESS"}, headers=STAFF).status_code == 403)
check("DIRECTOR(crm:manage 없음, 조회는 되지만 관리는 불가) → 상태변경 403",
      client.post("/api/admin/consultations/CRM-0002/status", json={"status": "IN_PROGRESS"}, headers=DIRECTOR).status_code == 403)

check("허용되지 않은 상태값(DELETED) → 400",
      client.post("/api/admin/consultations/CRM-0002/status", json={"status": "DELETED"}, headers=CRM_USER).status_code == 400)
check("존재하지 않는 상담 ID → 404",
      client.post("/api/admin/consultations/CRM-9999/status", json={"status": "IN_PROGRESS"}, headers=CRM_USER).status_code == 404)
check("역행 전이(IN_PROGRESS→OPEN) 거부 → 409",
      client.post("/api/admin/consultations/CRM-0003/status", json={"status": "OPEN"}, headers=CRM_USER).status_code == 409)
check("건너뛰기 전이(OPEN→CLOSED, IN_PROGRESS 생략) 거부 → 409",
      client.post("/api/admin/consultations/CRM-0002/status", json={"status": "CLOSED"}, headers=CRM_USER).status_code == 409)
check("종결 상태(CLOSED)에서 추가 전이 거부 → 409",
      client.post("/api/admin/consultations/CRM-0001/status", json={"status": "CLOSED"}, headers=CRM_USER).status_code == 409)
check("유효하지 않은 handledBy → 400",
      client.post("/api/admin/consultations/CRM-0002/status", json={"status": "IN_PROGRESS", "handledBy": "USR-XXXX"}, headers=CRM_USER).status_code == 400)

r_ok = client.post("/api/admin/consultations/CRM-0002/status",
                    json={"status": "IN_PROGRESS", "handledBy": "USR-0003"}, headers=CRM_USER)
check("정상 순차 전이(OPEN→IN_PROGRESS) → 200", r_ok.status_code == 200, str(r_ok.status_code))
check("응답에 변경된 status 반영", r_ok.json()["data"]["status"] == "IN_PROGRESS")
check("응답에 handledBy 반영", r_ok.json()["data"]["handledBy"] == "USR-0003")

# 실제 파일에 반영됐는지(쓰기 검증) — 샌드박스 파일만 확인, 운영 data/ 무관
with open(SANDBOX / "crm.json", encoding="utf-8") as f:
    persisted = json.load(f)
_persisted_rec = next(r for r in persisted["records"] if r["id"] == "CRM-0002")
check("샌드박스 crm.json에 실제로 저장됨", _persisted_rec["status"] == "IN_PROGRESS", str(_persisted_rec["status"]))

# 연쇄 전이: IN_PROGRESS → CLOSED도 정상 동작해야 함
r_ok2 = client.post("/api/admin/consultations/CRM-0002/status", json={"status": "CLOSED"}, headers=CRM_USER)
check("연쇄 전이(IN_PROGRESS→CLOSED) → 200", r_ok2.status_code == 200)


# ── 4. 생성/삭제 엔드포인트 부재 확인(PM 결정사항 2 금지 목록) ──
check("DELETE 메서드로 상담 삭제 시도 → 405(라우트 자체 없음)",
      client.delete("/api/admin/consultations/CRM-0001", headers=CRM_USER).status_code in (404, 405))
check("루트 POST(신규 생성) 라우트 없음 → 405",
      client.post("/api/admin/consultations", json={}, headers=CRM_USER).status_code in (404, 405))


# ── 5. 기존 기능 회귀 확인 ──
import sheets_readonly_service as sheets  # noqa: E402
sheets.list_reservations = lambda **kw: []
sheets.get_summary = lambda **kw: {"date": "2026-07-26", "total": 0, "byStatus": {}}
check("기존 Dashboard 정상 동작(무영향)", client.get("/api/admin/dashboard", headers=STAFF).status_code == 200)
check("기존 Statistics 정상 동작(무영향, DIRECTOR)", client.get("/api/admin/statistics", headers=DIRECTOR).status_code == 200)
check("기존 예약조회 정상 동작(무영향)", client.get("/api/admin-portal/reservations", headers=STAFF).status_code == 200)


# ── 6. Portal UI 정적 구조 확인 ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("상담관리 탭 버튼 존재", 'data-view="consultations"' in _PORTAL_HTML)
check("상담관리 뷰 섹션 존재", 'id="view-consultations"' in _PORTAL_HTML)
check("상태전이 버튼 로직에 OPEN→IN_PROGRESS 매핑 존재", "OPEN: 'IN_PROGRESS'" in _PORTAL_HTML)
check("상태전이 버튼 로직에 IN_PROGRESS→CLOSED 매핑 존재", "IN_PROGRESS: 'CLOSED'" in _PORTAL_HTML)
check("CLOSED에 대한 다음 상태 매핑 없음(종결 처리)", "CLOSED: '" not in _PORTAL_HTML)
check("상담 생성 UI(신규 등록 폼) 없음", "상담 등록" not in _PORTAL_HTML and "신규 상담" not in _PORTAL_HTML)
check("상담 삭제 UI 없음", "상담 삭제" not in _PORTAL_HTML)
check("advanceConsultation이 POST /consultations/{id}/status만 호출",
      "/consultations/' + encodeURIComponent(id) + '/status'" in _PORTAL_HTML)


out = Path(__file__).parent / "sprint3_crm_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
