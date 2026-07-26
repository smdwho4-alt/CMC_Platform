# -*- coding: utf-8 -*-
"""
CSHSP Sprint 2 — Commit 1(Dashboard) 테스트 러너

대상: src/services/sheets_readonly_service.py의 get_summary() 신규 함수,
     src/api/routes_admin_portal.py의 create_admin_namespace_router()/GET /api/admin/dashboard.
GAS 호출부는 모듈 레벨 monkeypatch로 대체 — 실네트워크 호출 없음.
샌드박스 데이터 사용 — 원본 data/ 불변.

결과: tests/sprint2_dashboard_test_result.csv
"""
from __future__ import annotations

import csv
import os
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

SANDBOX = Path(__file__).parent / "sandbox_sprint2_dashboard" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    try:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")
    except UnicodeEncodeError:
        pass  # Windows 콘솔 코드페이지 제약 — CSV 결과에는 원문 그대로 저장됨


client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}

_SUMMARY = {"date": "2026-07-26", "total": 3, "byStatus": {"PENDING_APPROVAL": 2, "CONFIRMED": 1},
            "byRoom": {}, "byPayment": {}, "byDoctor": {}, "totalEstimatedCost": 0}
_RECENT = [
    {"reservationNo": f"2026072{i}-000{i}", "name": "홍길동", "birth": "1980-05-05",
     "phone": "010-1234-5678", "program": "SMART", "wishDate": "2026-08-01",
     "wishTime": "09:00", "status": "PENDING_APPROVAL", "note": ""}
    for i in range(1, 8)  # 7건 — 최근 5건만 잘리는지 확인
]

# ── 1. sheets_readonly_service.get_summary() 단위 테스트 ──
check("summary 액션이 _READONLY_ACTIONS에 등록됨(쓰기 아님)", "summary" in sheets._READONLY_ACTIONS)


class _FakeResponse:
    def __init__(self, payload, ok=True):
        self._payload, self._ok = payload, ok

    def raise_for_status(self): pass

    def json(self): return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params or {}))
        return _FakeResponse(self._payload)


_ENV_KEY = sheets.GAS_WEBAPP_URL_ENV
_saved_env = os.environ.get(_ENV_KEY)
os.environ[_ENV_KEY] = "https://example.invalid/fake-gas-endpoint-not-called"

fake = _FakeSession({"ok": True, "data": dict(_SUMMARY)})
real_summary = sheets.get_summary(session=fake)
check("get_summary 정상 파싱", real_summary.get("total") == 3, str(real_summary))
check("get_summary action=summary 전달", fake.calls[0][1].get("action") == "summary")
check("get_summary date 미지정 시 파라미터 생략(GAS 기본값=오늘 위임)", "date" not in fake.calls[0][1])

fake2 = _FakeSession({"ok": True, "data": dict(_SUMMARY)})
sheets.get_summary(date="2026-07-20", session=fake2)
check("get_summary date 지정 시 전달", fake2.calls[0][1].get("date") == "2026-07-20")

if _saved_env is None:
    os.environ.pop(_ENV_KEY, None)
else:
    os.environ[_ENV_KEY] = _saved_env


# ── 2. GET /api/admin/dashboard 통합 테스트 ──
check("헤더 없이 조회 → 401", client.get("/api/admin/dashboard").status_code == 401)

sheets.get_summary = lambda **kw: dict(_SUMMARY)
sheets.list_reservations = lambda **kw: [dict(r) for r in _RECENT]
sheets.ping = lambda **kw: {"ok": True}

r = client.get("/api/admin/dashboard", headers=STAFF)
check("정상 조회 → 200", r.status_code == 200, str(r.status_code))
body = r.json()
check("system.fastapi = ok", body["system"]["fastapi"] == "ok")
check("system.sheetsIntegration = connected", body["system"]["sheetsIntegration"] == "connected")
check("summary.total 반영", body["summary"]["total"] == 3)
check("summaryError 없음(정상 시)", body["summaryError"] is None)
check("recentReservations 최근 5건만 반환(전체 7건 중)", len(body["recentReservations"]) == 5,
      str(len(body["recentReservations"])))
check("recentReservations 마스킹 적용", body["recentReservations"][0]["name"] == "홍○○")
check("recentReservations 원본 phone 미노출", "010-1234-5678" not in str(body))

# ── 3. 부분 실패 처리(요구사항: 위젯 하나가 실패해도 전체 200) ──
sheets.get_summary = lambda **kw: (_ for _ in ()).throw(sheets.SheetsIntegrationError("summary 실패(테스트)"))
sheets.list_reservations = lambda **kw: [dict(r) for r in _RECENT]
r2 = client.get("/api/admin/dashboard", headers=STAFF)
check("summary만 실패해도 200 응답", r2.status_code == 200, str(r2.status_code))
body2 = r2.json()
check("summaryError 채워짐, recentReservations는 정상", body2["summaryError"] is not None and len(body2["recentReservations"]) == 5)

sheets.get_summary = lambda **kw: dict(_SUMMARY)
sheets.list_reservations = lambda **kw: (_ for _ in ()).throw(sheets.SheetsIntegrationNotConfigured("미설정(테스트)"))
r3 = client.get("/api/admin/dashboard", headers=STAFF)
check("recent만 실패해도 200 응답", r3.status_code == 200, str(r3.status_code))
body3 = r3.json()
check("recentReservationsError 채워짐, summary는 정상", body3["recentReservationsError"] is not None and body3["summary"]["total"] == 3)

sheets.get_summary = lambda **kw: (_ for _ in ()).throw(sheets.SheetsIntegrationNotConfigured("미설정(테스트)"))
sheets.list_reservations = lambda **kw: (_ for _ in ()).throw(sheets.SheetsIntegrationNotConfigured("미설정(테스트)"))
sheets.ping = lambda **kw: (_ for _ in ()).throw(sheets.SheetsIntegrationNotConfigured("미설정(테스트)"))
r4 = client.get("/api/admin/dashboard", headers=STAFF)
check("전체 미설정 상태에서도 200 응답(오류 정보 포함)", r4.status_code == 200, str(r4.status_code))
body4 = r4.json()
check("system.sheetsIntegration = not_configured", body4["system"]["sheetsIntegration"] == "not_configured")

# ── 4. 기존 기능 회귀 확인(Namespace 공유 지점 특히 주의) ──
check("기존 /api/health 정상 동작(무영향)", client.get("/api/health").status_code == 200)
check("기존 /api/admin-portal/health 정상 동작(무영향)", client.get("/api/admin-portal/health").status_code == 200)
check("기존 /api/admin/schedules 정상 동작(같은 /api/admin Namespace, 충돌 없음)",
      client.get("/api/admin/schedules", headers=STAFF).status_code in (200,))
check("기존 /api/admin/users 정상 동작(충돌 없음)",
      client.get("/api/admin/users", headers=STAFF).status_code in (200,))
check("기존 /api/reservations 인증 필요 그대로 유지(무영향)",
      client.get("/api/reservations").status_code == 401)


out = Path(__file__).parent / "sprint2_dashboard_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
