# -*- coding: utf-8 -*-
"""
CSHSP Sprint 3 — Commit 3(Audit Log) 테스트 러너

PM 결정사항 5: 기존 GET /api/audit-logs 재사용, 신규 Backend 생성 금지.
이번 Commit은 백엔드 코드를 전혀 변경하지 않았다(git status로 확인) — Portal이
기존 최상위 엔드포인트(/api/audit-logs, api_server.py 소유)를 직접 호출하도록
프론트엔드만 연결했다.

결과: tests/sprint3_audit_test_result.csv
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

from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint3_audit" / "data"
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


# ── 1. Portal이 호출하도록 연결한 기존 엔드포인트가 실제로 존재/동작하는지 확인 ──
# (엔드포인트 자체는 api_server.py 소유 — 이 테스트는 "Portal이 올바른 URL/파라미터로
#  기존 엔드포인트를 호출하는가"를 검증하는 것이지, 엔드포인트 로직 자체를 재검증하는
#  것이 아니다. 로직 자체의 회귀 여부는 tests/run_sprint_d_tests.py가 이미 담당한다.)
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}   # reservation:view 보유 → 기존 로직상 audit-logs 접근 가능
DIRECTOR = {"X-User-Id": "USR-0001"}  # audit:view 보유
CRM_USER = {"X-User-Id": "USR-0003"}  # reservation:view도 보유(roles.json 확인) → 기존 로직상 허용
AI_AGENT = {"X-User-Id": "USR-9000"}  # reservation:request만 보유, audit:view/reservation:view 없음 → 거부

check("헤더 없이 조회 → 401", client.get("/api/audit-logs").status_code == 401)
check("STAFF(reservation:view 보유, 기존 로직상 허용) → 200",
      client.get("/api/audit-logs", headers=STAFF).status_code == 200)
check("DIRECTOR(audit:view 보유) → 200",
      client.get("/api/audit-logs", headers=DIRECTOR).status_code == 200)
check("ROLE-CRM(reservation:view도 보유, 기존 로직상 허용) → 200",
      client.get("/api/audit-logs", headers=CRM_USER).status_code == 200)
check("AI-AGENT(audit:view도 reservation:view도 없음, 기존 로직상 거부) → 403",
      client.get("/api/audit-logs", headers=AI_AGENT).status_code == 403)

r = client.get("/api/audit-logs", params={"limit": 5}, headers=DIRECTOR)
body = r.json()
check("응답 스키마가 기존 그대로({count, records})", "count" in body and "records" in body, str(list(body.keys())))
check("action 필터 파라미터 전달 확인",
      client.get("/api/audit-logs", params={"action": "존재하지않는이벤트"}, headers=DIRECTOR).json()["count"] == 0)


# ── 2. 이번 Commit이 백엔드를 전혀 수정하지 않았는지 확인 ──
import subprocess  # noqa: E402
diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout
py_changes = [ln for ln in diff.splitlines() if ln.endswith(".py") and "tests/" not in ln]
check("작업트리에 커밋되지 않은 프로덕션 .py 변경 없음(신규 백엔드 없음 확인)",
      len(py_changes) == 0, str(py_changes))


# ── 3. Portal UI 정적 구조 확인 ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("감사로그 탭 버튼 존재", 'data-view="auditlog"' in _PORTAL_HTML)
check("감사로그 뷰 섹션 존재", 'id="view-auditlog"' in _PORTAL_HTML)
check("기존 최상위 엔드포인트(/api/audit-logs)를 직접 호출", "'/api/audit-logs'" in _PORTAL_HTML)
check("신규 /api/admin/audit* 류 엔드포인트를 만들지 않음(호출 안 함)",
      "/api/admin/audit" not in _PORTAL_HTML)
check("기존 응답 스키마(body.records)를 그대로 사용", "body.records" in _PORTAL_HTML)


out = Path(__file__).parent / "sprint3_audit_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
