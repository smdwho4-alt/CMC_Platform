# -*- coding: utf-8 -*-
"""
CSHSP Sprint 2 — Commit 4(통계) 테스트 러너

대상: src/api/routes_admin_portal.py의 _date_range() 헬퍼 + GET /api/admin/statistics.
PM 결정사항 6 검증 핵심: FastAPI가 원시 예약 데이터를 직접 집계하지 않고, GAS의
기존 summary 액션 결과(mock)를 그대로 합산만 하는지 확인한다.
GAS 호출부는 monkeypatch — 실네트워크 호출 없음. 샌드박스 데이터 사용.

결과: tests/sprint2_statistics_test_result.csv
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

import routes_admin_portal as rap  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint2_statistics" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    try:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")
    except UnicodeEncodeError:
        pass


# ── 1. _date_range() 단위 테스트 ──
check("정상 범위(3일)", rap._date_range("2026-07-01", "2026-07-03") ==
      ["2026-07-01", "2026-07-02", "2026-07-03"])
check("역순 입력 자동 정렬", rap._date_range("2026-07-03", "2026-07-01") ==
      ["2026-07-01", "2026-07-02", "2026-07-03"])
check("동일 날짜(1일)", rap._date_range("2026-07-01", "2026-07-01") == ["2026-07-01"])

try:
    rap._date_range("2026-01-01", "2026-12-31")
    check("최대 기간(31일) 초과 시 ValueError", False, "예외 미발생")
except ValueError as e:
    check("최대 기간(31일) 초과 시 ValueError", True, str(e))

try:
    rap._date_range("2026-13-99", "2026-07-01")
    check("잘못된 날짜 형식 시 ValueError", False, "예외 미발생")
except ValueError:
    check("잘못된 날짜 형식 시 ValueError", True)


# ── 2. GET /api/admin/statistics 통합 테스트 ──
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}

check("헤더 없이 조회 → 401", client.get("/api/admin/statistics").status_code == 401)

_SUMMARY_BY_DATE = {
    "2026-07-01": {"date": "2026-07-01", "total": 2, "byStatus": {"PENDING_APPROVAL": 2}},
    "2026-07-02": {"date": "2026-07-02", "total": 3, "byStatus": {"PENDING_APPROVAL": 1, "CONFIRMED": 2}},
}


def _fake_get_summary(date="", **kw):
    # FastAPI가 원시 데이터를 직접 계산하지 않고, 이 GAS summary(mock) 결과만 가공한다는
    # 것을 증명하기 위해 호출 인자별로 고정된 "GAS 응답"을 그대로 반환한다.
    if date in _SUMMARY_BY_DATE:
        return dict(_SUMMARY_BY_DATE[date])
    return {"date": date or "today", "total": 0, "byStatus": {}}


sheets.get_summary = _fake_get_summary

r1 = client.get("/api/admin/statistics", params={"dateFrom": "2026-07-01", "dateTo": "2026-07-02"}, headers=STAFF)
check("기간 지정 조회 → 200", r1.status_code == 200, str(r1.status_code))
body1 = r1.json()
check("totalReservations = GAS summary 합산(2+3=5)", body1["totalReservations"] == 5, str(body1["totalReservations"]))
check("byStatus 병합(PENDING_APPROVAL 2+1=3)", body1["byStatus"].get("PENDING_APPROVAL") == 3, str(body1["byStatus"]))
check("byStatus 병합(CONFIRMED=2)", body1["byStatus"].get("CONFIRMED") == 2)
check("byDate 2건(일자별 breakdown)", len(body1["byDate"]) == 2, str(body1["byDate"]))
check("dayErrors 없음(정상 시)", body1["dayErrors"] == [])

r2 = client.get("/api/admin/statistics", headers=STAFF)
check("dateFrom/dateTo 미지정 시 오늘 하루만 조회 → 200", r2.status_code == 200)
body2 = r2.json()
check("미지정 시 byDate 1건(오늘)", len(body2["byDate"]) == 1, str(body2["byDate"]))

r3 = client.get("/api/admin/statistics", params={"dateFrom": "2026-01-01", "dateTo": "2026-12-31"}, headers=STAFF)
check("기간 너무 김 → 400", r3.status_code == 400, str(r3.status_code))

r4 = client.get("/api/admin/statistics", params={"dateFrom": "bad-date", "dateTo": "2026-07-01"}, headers=STAFF)
check("잘못된 날짜 형식 → 400", r4.status_code == 400)

# ── 3. 부분 실패(하루만 GAS 오류) — 나머지 날짜는 정상 집계 ──
def _fake_partial_fail(date="", **kw):
    if date == "2026-07-02":
        raise sheets.SheetsIntegrationError("일시 오류(테스트)")
    return dict(_SUMMARY_BY_DATE.get(date, {"date": date, "total": 0, "byStatus": {}}))


sheets.get_summary = _fake_partial_fail
r5 = client.get("/api/admin/statistics", params={"dateFrom": "2026-07-01", "dateTo": "2026-07-02"}, headers=STAFF)
check("하루만 실패해도 200 응답", r5.status_code == 200, str(r5.status_code))
body5 = r5.json()
check("실패한 날짜는 dayErrors에 기록, 나머지는 정상 집계",
      len(body5["dayErrors"]) == 1 and body5["totalReservations"] == 2, str(body5))

# ── 4. 미설정 상태 → 503 ──
sheets.get_summary = lambda **kw: (_ for _ in ()).throw(sheets.SheetsIntegrationNotConfigured("미설정(테스트)"))
r6 = client.get("/api/admin/statistics", headers=STAFF)
check("Sheets 미설정 시 503", r6.status_code == 503, str(r6.status_code))

# ── 5. 기존 기능 회귀 확인 ──
check("기존 /api/admin/dashboard 정상 동작(무영향, Namespace 공유)",
      client.get("/api/admin/dashboard", headers=STAFF).status_code == 200)
check("기존 /api/admin-portal/reservations 정상 동작(무영향)",
      client.get("/api/admin-portal/reservations", headers=STAFF).status_code in (200, 502, 503))
check("기존 /api/admin/schedules 정상 동작(무영향)",
      client.get("/api/admin/schedules", headers=STAFF).status_code == 200)


out = Path(__file__).parent / "sprint2_statistics_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
