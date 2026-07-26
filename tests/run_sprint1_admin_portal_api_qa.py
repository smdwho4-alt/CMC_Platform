# -*- coding: utf-8 -*-
"""
CSHSP Sprint 1 — Commit 2(관리자 조회 API) 테스트 러너

대상: src/api/routes_admin_portal.py (신규) + src/api/api_server.py의 신규 라우터 등록분.
FastAPI TestClient로 검증하되, Sheets/GAS 호출부(sheets_readonly_service)는 모듈 레벨로
Monkeypatch하여 실제 네트워크 호출이 전혀 발생하지 않도록 한다.
(샌드박스 사본 사용 — 원본 data/ 불변. Google Sheets/Apps Script 무호출.)

결과: tests/sprint1_admin_portal_api_test_result.csv
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "api"))
sys.path.insert(0, str(ROOT / "src" / "services"))

from fastapi.testclient import TestClient  # noqa: E402

import sheets_readonly_service as sheets  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint1_admin_portal" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# include_agents=False: Sprint 1은 AI/에이전트 범위 밖 — 불필요한 의존성(Claude 등) 배제
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}

_FAKE_RESERVATION = {
    "reservationNo": "20260726-0001", "name": "홍길동", "birth": "1980-05-05",
    "phone": "010-1234-5678", "program": "SMART", "wishDate": "2026-08-01",
    "wishTime": "09:00", "status": "PENDING_APPROVAL", "note": "",
}

# ── 1. 인증 ──────────────────────────────────────────
check("헤더 없이 목록 조회 → 401",
      client.get("/api/admin-portal/reservations").status_code == 401)
check("무효 사용자 → 401",
      client.get("/api/admin-portal/reservations", headers={"X-User-Id": "USR-XXXX"}).status_code == 401)

# ── 2. 정상 조회 (Sheets 호출부 Monkeypatch) ──────────
sheets.list_reservations = lambda **kw: [dict(_FAKE_RESERVATION)]
sheets.get_reservation = lambda reservation_no, **kw: (
    dict(_FAKE_RESERVATION) if reservation_no == "20260726-0001" else None
)
sheets.ping = lambda **kw: {"ok": True}

r = client.get("/api/admin-portal/reservations", headers=STAFF)
check("정상 사용자 목록 조회 → 200", r.status_code == 200, str(r.status_code))
body = r.json()
check("목록 응답에 마스킹된 이름 포함", body["data"][0].get("name") == "홍○○", body["data"][0].get("name"))
check("목록 응답에 마스킹된 생년월일 포함", body["data"][0].get("birth") == "1980-**-**")
check("목록 응답에 마스킹된 휴대전화 포함", body["data"][0].get("phone") == "010-****-5678")
check("목록 응답에 원본 phone 값 미노출", "010-1234-5678" not in str(body))
check("목록 응답 count 필드", body.get("count") == 1)

r2 = client.get("/api/admin-portal/reservations/20260726-0001", headers=STAFF)
check("정상 사용자 단건 조회 → 200", r2.status_code == 200, str(r2.status_code))
check("단건 조회 마스킹 적용", r2.json()["data"].get("name") == "홍○○")

r3 = client.get("/api/admin-portal/reservations/NOT-EXIST", headers=STAFF)
check("존재하지 않는 예약번호 → 404", r3.status_code == 404, str(r3.status_code))

r4 = client.get("/api/admin-portal/health")
check("health 엔드포인트 인증 없이 접근 가능", r4.status_code == 200, str(r4.status_code))
check("health 정상 연결 응답", r4.json().get("sheetsIntegration") == "connected")

# ── 3. 오류 처리(§4 확정범위: 조회실패/네트워크오류 기본 처리) ──
def _raise_not_configured(*args, **kw):
    raise sheets.SheetsIntegrationNotConfigured("환경변수 미설정(테스트)")


def _raise_integration_error(*args, **kw):
    raise sheets.SheetsIntegrationError("GAS 호출 실패(테스트)")


sheets.list_reservations = _raise_not_configured
r5 = client.get("/api/admin-portal/reservations", headers=STAFF)
check("Sheets 미설정 시 목록조회 → 503", r5.status_code == 503, str(r5.status_code))

sheets.list_reservations = _raise_integration_error
r6 = client.get("/api/admin-portal/reservations", headers=STAFF)
check("GAS 연동 오류 시 목록조회 → 502", r6.status_code == 502, str(r6.status_code))

sheets.get_reservation = _raise_integration_error
r7 = client.get("/api/admin-portal/reservations/ANY", headers=STAFF)
check("GAS 연동 오류 시 단건조회 → 502", r7.status_code == 502, str(r7.status_code))

sheets.ping = _raise_not_configured
r8 = client.get("/api/admin-portal/health")
check("health: Sheets 미설정 시에도 200 + not_configured 표시(오류 UX)",
      r8.status_code == 200 and r8.json().get("sheetsIntegration") == "not_configured")

# 빈 목록(정상 상황) — 오류가 아니라 count=0으로 처리되어야 함
sheets.list_reservations = lambda **kw: []
r9 = client.get("/api/admin-portal/reservations", headers=STAFF)
check("빈 데이터는 오류가 아니라 count=0으로 정상 응답",
      r9.status_code == 200 and r9.json().get("count") == 0, str(r9.json()))

# ── 4. 기존 기능 회귀 확인(신규 라우터가 기존 엔드포인트에 영향 없는지) ──
check("기존 /api/health 정상 동작(무영향)", client.get("/api/health").status_code == 200)
check("기존 /api/reservations 인증 필요 그대로 유지(무영향)",
      client.get("/api/reservations").status_code == 401)


# ── 결과 저장 ─────────────────────────────────────────
out = Path(__file__).parent / "sprint1_admin_portal_api_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
