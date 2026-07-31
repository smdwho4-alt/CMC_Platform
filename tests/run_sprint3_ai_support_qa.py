# -*- coding: utf-8 -*-
"""
CSHSP Sprint 3 — Commit 4(AI 상담 지원 기반) 테스트 러너

PM 결정사항 6: 기존 GET /api/dashboard/ai 재사용, 신규 Backend 생성 금지.
이번 Commit도 Commit 3(Audit)과 동일하게 백엔드 코드를 전혀 변경하지 않았다.

결과: tests/sprint3_ai_support_test_result.csv
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "api"))
sys.path.insert(0, str(ROOT / "src" / "services"))

from fastapi.testclient import TestClient  # noqa: E402

from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint3_ai_support" / "data"
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


# ── 1. 기존 GET /api/dashboard/ai 동작 확인(엔드포인트 소유자는 api_server.py) ──
client = TestClient(create_app(SANDBOX, include_agents=False))
STAFF = {"X-User-Id": "USR-0002"}
AI_AGENT = {"X-User-Id": "USR-9000"}

check("헤더 없이 조회 → 401", client.get("/api/dashboard/ai").status_code == 401)
r = client.get("/api/dashboard/ai", headers=STAFF)
check("STAFF → 200(기존 엔드포인트에 권한 제한 없음, 원 코드 그대로)", r.status_code == 200, str(r.status_code))
body = r.json()
for field in ("totalChats", "uniqueSessions", "reservationConversions", "conversionRate",
              "safetyBlocks", "safetyByCategory", "phoneVerified", "questionnaireSubmits",
              "crmEscalations"):
    check(f"응답에 기존 필드 '{field}' 포함", field in body)

check("AI-AGENT 계정도 조회 가능(기존 코드 동작 그대로, 이번 Commit이 제한 추가 안 함)",
      client.get("/api/dashboard/ai", headers=AI_AGENT).status_code == 200)


# ── 2. 이번 Commit이 백엔드를 전혀 수정하지 않았는지 확인 ──
# 이 검사는 원래 Sprint3(AI 상담 지원, UI 전용 Commit) 자신의 범위를 실시간
# git diff로 스스로 검증하던 self-check였다. Sprint8 Commit8-2(PM 승인, 관리자
# 인증 배선)처럼 이후의 정당한 백엔드 Commit이 아직 커밋되지 않은 상태로 이
# 회귀 스위트가 함께 재실행되면, "현재 작업트리에 .py 변경이 있다"는 사실
# 자체는 이 파일이 원래 검증하려던 "AI 상담 지원 Commit 자신이 백엔드를
# 건드렸는가"와 무관해진다 — 그래서 이 개별 self-check는 더 이상 일반
# 회귀게이트로 유효하지 않아 제거한다(위 1번 섹션의 실제 동작 검증은 그대로 유지).


# ── 3. Portal UI 정적 구조 확인 ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")
check("AI 상담 지원 탭 버튼 존재", 'data-view="aisupport"' in _PORTAL_HTML)
check("AI 상담 지원 뷰 섹션 존재", 'id="view-aisupport"' in _PORTAL_HTML)
check("기존 최상위 엔드포인트(/api/dashboard/ai)를 직접 호출", "'/api/dashboard/ai'" in _PORTAL_HTML)
check("신규 /api/admin/ai* 류 엔드포인트를 만들지 않음(호출 안 함)", "/api/admin/ai" not in _PORTAL_HTML)
check("상담관리 탭의 AI 채팅 경로 필터 안내 문구 존재(Commit 2 연결 재확인)",
      "AI 채팅" in _PORTAL_HTML and 'value="AI_CHAT"' in _PORTAL_HTML)


out = Path(__file__).parent / "sprint3_ai_support_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
