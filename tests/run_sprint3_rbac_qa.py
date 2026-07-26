# -*- coding: utf-8 -*-
"""
CSHSP Sprint 3 — Commit 1(RBAC) 테스트 러너

대상: src/api/routes_admin_portal.py의 _has_permission()/_build_require_permission()
및 이를 적용한 4개 기존 엔드포인트(dashboard/reservations/reservations detail/statistics).

역할별 실제 권한(roles.json, 구조 확인 근거)에 따른 접근 가능/거부 매트릭스를
명시적으로 검증한다 — Sprint 1~2에서는 권한 검사가 전혀 없어 어떤 ACTIVE 사용자도
전체 기능에 접근 가능했던 보안 공백을 이번 Commit이 메운다.

실제 존재하는 테스트 사용자(기존 data/ 근거, PII 아닌 구조 정보):
  USR-0001=ROLE-DIRECTOR, USR-0002=ROLE-STAFF, USR-0003=ROLE-CRM, USR-9000=ROLE-AI-AGENT

GAS 호출부는 monkeypatch — 실네트워크 없음. 샌드박스 데이터 사용.
결과: tests/sprint3_rbac_test_result.csv
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

SANDBOX = Path(__file__).parent / "sandbox_sprint3_rbac" / "data"
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


# ── 1. _has_permission() 단위 테스트 ──
_ADMIN_ROLE = {"id": "ROLE-ADMIN", "permissions": ["*"]}
_STAFF_ROLE = {"id": "ROLE-STAFF", "permissions": ["reservation:view", "dashboard:view"]}
_NO_ROLE = {"id": "ROLE-NONE", "permissions": []}


def _fake_loader_role(role_dict):
    return [role_dict]


# _has_permission은 loader.load_entity("Role", data_dir)를 호출하므로 loader를 monkeypatch
_orig_load_entity = rap.loader.load_entity


def _with_role(role_dict):
    rap.loader.load_entity = lambda entity, data_dir: (_fake_loader_role(role_dict) if entity == "Role" else _orig_load_entity(entity, data_dir))


_with_role(_ADMIN_ROLE)
check("와일드카드(*) 권한은 모든 요구권한 통과",
      rap._has_permission({"roleId": "ROLE-ADMIN"}, SANDBOX, "anything:goes"))

_with_role(_STAFF_ROLE)
check("보유 권한 중 하나라도 일치하면 통과(OR)",
      rap._has_permission({"roleId": "ROLE-STAFF"}, SANDBOX, "statistics:view", "reservation:view"))
check("요구 권한을 하나도 보유하지 않으면 거부",
      not rap._has_permission({"roleId": "ROLE-STAFF"}, SANDBOX, "audit:view"))

_with_role(_NO_ROLE)
check("권한 없는 역할은 거부", not rap._has_permission({"roleId": "ROLE-NONE"}, SANDBOX, "dashboard:view"))

rap.loader.load_entity = _orig_load_entity  # 원복 — 이후 통합 테스트는 실제 roles.json 사용


# ── 2. 역할별 접근 매트릭스(실제 roles.json 기준, 통합 테스트) ──
client = TestClient(create_app(SANDBOX, include_agents=False))
sheets.list_reservations = lambda **kw: []
sheets.get_summary = lambda **kw: {"date": "2026-07-26", "total": 0, "byStatus": {}}

DIRECTOR = {"X-User-Id": "USR-0001"}
STAFF = {"X-User-Id": "USR-0002"}
CRM_USER = {"X-User-Id": "USR-0003"}
AI_AGENT = {"X-User-Id": "USR-9000"}

# DIRECTOR: dashboard:view, statistics:view, reservation:view, audit:view 보유
check("DIRECTOR → Dashboard 200(dashboard:view 보유)",
      client.get("/api/admin/dashboard", headers=DIRECTOR).status_code == 200)
check("DIRECTOR → Statistics 200(statistics:view 보유)",
      client.get("/api/admin/statistics", headers=DIRECTOR).status_code == 200)
check("DIRECTOR → 예약조회 200(reservation:view 보유)",
      client.get("/api/admin-portal/reservations", headers=DIRECTOR).status_code == 200)

# STAFF: reservation:view, dashboard:view 보유 / statistics:view 없음
check("STAFF → Dashboard 200(dashboard:view 보유)",
      client.get("/api/admin/dashboard", headers=STAFF).status_code == 200)
check("STAFF → 예약조회 200(reservation:view 보유)",
      client.get("/api/admin-portal/reservations", headers=STAFF).status_code == 200)
check("STAFF → Statistics 403(statistics:view 미보유 — Sprint1/2의 보안 공백을 이번 Commit이 메움)",
      client.get("/api/admin/statistics", headers=STAFF).status_code == 403)

# ROLE-CRM: reservation:view 보유 / dashboard:view, statistics:view 없음
check("CRM 역할 → 예약조회 200(reservation:view 보유)",
      client.get("/api/admin-portal/reservations", headers=CRM_USER).status_code == 200)
check("CRM 역할 → Dashboard 403(dashboard:view 미보유)",
      client.get("/api/admin/dashboard", headers=CRM_USER).status_code == 403)
check("CRM 역할 → Statistics 403(statistics:view 미보유)",
      client.get("/api/admin/statistics", headers=CRM_USER).status_code == 403)

# ROLE-AI-AGENT: reservation:request만 보유(reservation:view 아님) → Portal 전체 403
check("AI-AGENT → Dashboard 403(dashboard:view 미보유)",
      client.get("/api/admin/dashboard", headers=AI_AGENT).status_code == 403)
check("AI-AGENT → 예약조회 403(reservation:view 미보유, reservation:request와는 다른 문자열)",
      client.get("/api/admin-portal/reservations", headers=AI_AGENT).status_code == 403)
check("AI-AGENT → Statistics 403(statistics:view 미보유)",
      client.get("/api/admin/statistics", headers=AI_AGENT).status_code == 403)

# 인증 자체 실패는 여전히 401(권한 검사보다 먼저 — Authentication → Role Check 순서 확인)
check("헤더 없음 → 401(Role Check 이전에 인증 단계에서 차단)",
      client.get("/api/admin/dashboard").status_code == 401)
check("무효 사용자 → 401", client.get("/api/admin/dashboard", headers={"X-User-Id": "USR-XXXX"}).status_code == 401)

# health는 의도적으로 인증/권한 모두 없음(PII 미포함 연결상태 확인용) — 회귀 확인
check("health는 여전히 인증 없이 접근 가능(의도된 설계, 회귀 아님)",
      client.get("/api/admin-portal/health").status_code == 200)


# ── 3. Portal UI 403 처리 정적 구조 확인 ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("throwIfForbidden 헬퍼 함수 정의됨", "function throwIfForbidden(" in _PORTAL_HTML)
check("throwIfForbidden이 403 상태코드 처리", "r.status === 403" in _PORTAL_HTML)
# 최소 4곳(Dashboard/예약조회/예약상세/통계, Sprint 3 Commit 1 기준)에는 반드시
# 연결되어 있어야 한다. 이후 Commit(예: Commit 2 상담관리)이 fetch 지점을 추가할
# 수 있으므로 정확히 4가 아니라 "최소 4"로 검사한다(과도하게 엄격한 고정값 회피).
check("Dashboard/예약조회/예약상세/통계 최소 4곳 403 처리 연결",
      _PORTAL_HTML.count("var forbidden = throwIfForbidden(r);") >= 4,
      str(_PORTAL_HTML.count("var forbidden = throwIfForbidden(r);")))


out = Path(__file__).parent / "sprint3_rbac_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
