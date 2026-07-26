# -*- coding: utf-8 -*-
"""
CSHSP Sprint 2 — Commit 2(예약조회: 검색/정렬/페이지) 테스트 러너

대상: src/services/sheets_readonly_service.list_reservations()의 search/sort_by/sort_dir
     확장, src/api/routes_admin_portal.py의 /api/admin-portal/reservations 파라미터 확장.
GAS 호출부는 monkeypatch — 실네트워크 호출 없음. 샌드박스 데이터 사용.

핵심 검증: 신규 파라미터를 전달하지 않으면 Sprint 1과 완전히 동일한 응답(PM 결정사항 4
"기본 Response Schema 불변, 신규 파라미터는 Optional")인지.

결과: tests/sprint2_reservation_search_test_result.csv
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

SANDBOX = Path(__file__).parent / "sandbox_sprint2_reservation_search" / "data"
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


_RAW = [
    {"reservationNo": "20260701-0001", "name": "홍길동", "birth": "1980-05-05",
     "phone": "010-1111-1111", "program": "SMART", "wishDate": "2026-08-05",
     "wishTime": "09:00", "status": "PENDING_APPROVAL", "note": "", "createdAt": "2026-07-01 10:00:00"},
    {"reservationNo": "20260702-0001", "name": "김철수", "birth": "1975-03-03",
     "phone": "010-2222-2222", "program": "BASIC", "wishDate": "2026-08-01",
     "wishTime": "10:00", "status": "CONFIRMED", "note": "", "createdAt": "2026-07-02 10:00:00"},
    {"reservationNo": "20260703-0001", "name": "박영희", "birth": "1990-01-01",
     "phone": "010-3333-3333", "program": "VIP", "wishDate": "2026-08-10",
     "wishTime": "11:00", "status": "PENDING_APPROVAL", "note": "", "createdAt": "2026-07-03 10:00:00"},
]


class _FakeSession:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params or {}))
        return self

    def raise_for_status(self): pass

    def json(self): return {"ok": True, "count": len(self._data), "data": self._data}


_ENV_KEY = sheets.GAS_WEBAPP_URL_ENV
_saved_env = os.environ.get(_ENV_KEY)
os.environ[_ENV_KEY] = "https://example.invalid/fake-gas-endpoint-not-called"

# ── 1. sheets_readonly_service.list_reservations() 검색/정렬 단위 테스트 ──
r1 = sheets.list_reservations(search="김철수", session=_FakeSession(list(_RAW)))
check("search: 이름으로 검색", len(r1) == 1 and r1[0]["reservationNo"] == "20260702-0001", str(len(r1)))

r2 = sheets.list_reservations(search="SMART", session=_FakeSession(list(_RAW)))
check("search: 프로그램으로 검색(대소문자 무관)", len(r2) == 1 and r2[0]["name"] == "홍길동")

r3 = sheets.list_reservations(search="0000", session=_FakeSession(list(_RAW)))
check("search: 매칭 없음 → 빈 리스트", r3 == [])

r4 = sheets.list_reservations(sort_by="reservationNo", sort_dir="asc", session=_FakeSession(list(_RAW)))
check("sort: 예약번호 오름차순", [x["reservationNo"] for x in r4] ==
      ["20260701-0001", "20260702-0001", "20260703-0001"])

r5 = sheets.list_reservations(sort_by="createdAt", sort_dir="desc", session=_FakeSession(list(_RAW)))
check("sort: 접수일 내림차순", r5[0]["reservationNo"] == "20260703-0001")

r6 = sheets.list_reservations(sort_by="invalid_field_xyz", session=_FakeSession(list(_RAW)))
check("sort: 허용되지 않은 정렬키는 무시(원본 순서 유지)",
      [x["reservationNo"] for x in r6] == [x["reservationNo"] for x in _RAW])

r7 = sheets.list_reservations(session=_FakeSession(list(_RAW)))
check("파라미터 미지정 시 원본 순서 그대로(Sprint 1과 동일 동작)",
      [x["reservationNo"] for x in r7] == [x["reservationNo"] for x in _RAW])

if _saved_env is None:
    os.environ.pop(_ENV_KEY, None)
else:
    os.environ[_ENV_KEY] = _saved_env


# ── 2. GET /api/admin-portal/reservations 통합 테스트(파라미터 확장 + 하위호환) ──
# _call_gas만 fake하고 list_reservations()는 실제 구현을 그대로 실행시켜야
# 라우터가 전달한 search/sortBy가 실제로 반영되는지 검증할 수 있다
# (list_reservations() 자체를 통째로 대체하면 그 안의 검색/정렬 로직이 실행되지 않음).
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}
sheets._call_gas = lambda action, params=None, session=None: {"ok": True, "data": list(_RAW)}

r_default = client.get("/api/admin-portal/reservations", headers=STAFF)
check("파라미터 없이 호출 → 200", r_default.status_code == 200)
body_default = r_default.json()
check("기본 응답에 page/pageSize/totalCount 없음(Sprint 1과 동일 스키마 유지)",
      "page" not in body_default and "pageSize" not in body_default and "totalCount" not in body_default,
      str(list(body_default.keys())))
check("기본 응답 count = 전체 건수(페이지네이션 미적용 시)", body_default["count"] == 3)

r_page = client.get("/api/admin-portal/reservations?pageSize=2&page=0", headers=STAFF)
body_page = r_page.json()
check("pageSize 지정 시 count가 페이지 크기로 제한", body_page["count"] == 2, str(body_page["count"]))
check("pageSize 지정 시 totalCount는 전체 건수", body_page.get("totalCount") == 3)
check("pageSize 지정 시 page/pageSize 필드 포함(Optional 추가)",
      body_page.get("page") == 0 and body_page.get("pageSize") == 2)

r_page2 = client.get("/api/admin-portal/reservations?pageSize=2&page=1", headers=STAFF)
check("2페이지 조회 시 잔여 1건", r_page2.json()["count"] == 1)

r_search = client.get("/api/admin-portal/reservations", params={"search": "박영희"}, headers=STAFF)
check("search 파라미터 라우터 전달 확인", r_search.json()["count"] == 1, str(r_search.json()))

r_sort = client.get("/api/admin-portal/reservations?sortBy=reservationNo&sortDir=asc", headers=STAFF)
check("sortBy/sortDir 파라미터 라우터 전달 확인",
      r_sort.json()["data"][0]["reservationNo"] == "20260701-0001")

# 마스킹은 여전히 적용되는지(신규 파라미터가 마스킹 로직에 영향 없어야 함)
check("검색/정렬 결과에도 PII 마스킹 유지", r_search.json()["data"][0]["name"] == "박○○")


out = Path(__file__).parent / "sprint2_reservation_search_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
