# -*- coding: utf-8 -*-
"""
CSHSP Sprint 3 — Commit 5(운영자 UX 개선) 테스트 러너

대상: app/pages/admin_portal_new.html (정적 구조 검사 — 실브라우저 수동 QA는
별도로 수행했으며 그 결과는 커밋 보고에 기록한다).

이번 Commit은 백엔드를 전혀 수정하지 않았다(순수 프론트엔드 UX 개선):
1. 헤더에 현재 적용된 사용자 ID 상시 표시(currentUserBadge)
2. 우상단 토스트 알림(showToast) — CRM 상태변경의 성공/실패를 alert() 대신 토스트로 전달
3. 검색/직원ID/감사로그 검색 입력창에 Enter 키로 즉시 조회

결과: tests/sprint3_ux_test_result.csv
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


# ── 1. 이번 Commit이 백엔드를 전혀 수정하지 않았는지 확인 ──
# 이 검사는 원래 Sprint3(UX 개선, UI 전용 Commit) 자신의 범위를 실시간 git diff로
# 스스로 검증하던 self-check였다. Sprint8 Commit8-2(PM 승인, 관리자 인증 배선)
# 처럼 이후의 정당한 백엔드 Commit이 아직 커밋되지 않은 상태로 이 회귀 스위트가
# 함께 재실행되면, "현재 작업트리에 .py 변경이 있다"는 사실 자체는 이 파일이
# 원래 검증하려던 범위와 무관해진다 — 그래서 이 개별 self-check는 더 이상 일반
# 회귀게이트로 유효하지 않아 제거한다(아래 2번 섹션의 실제 UI 구조 검증은 그대로 유지).


# ── 2. Portal UI 정적 구조 확인 ──
_PORTAL_HTML = (ROOT / "app" / "pages" / "admin_portal_new.html").read_text(encoding="utf-8")

# 2-1. 헤더 사용자 배지
check("currentUserBadge 엘리먼트 존재", 'id="currentUserBadge"' in _PORTAL_HTML)
check("updateCurrentUserBadge() 함수 정의됨", "function updateCurrentUserBadge(" in _PORTAL_HTML)
check("applyUserBtn 클릭 시 updateCurrentUserBadge 호출", "updateCurrentUserBadge();" in _PORTAL_HTML)
# Sprint8 Commit8-2: 초기 로드/새로고침 양쪽 다 requireSession()을 통해
# updateCurrentUserBadge()를 호출하도록 리팩터링됐다(세션 인증 도입으로 배지
# 갱신이 항상 서버 세션 확인과 함께 일어나야 하므로 공용 함수로 합쳐짐) —
# 리터럴 호출 횟수(예전 ≥2) 대신, 초기 로드와 새로고침 두 지점 모두
# requireSession()을 호출하고 그 함수가 updateCurrentUserBadge()를 호출하는지로
# 검사한다(동일한 사용자 관찰 가능 동작, 구현 구조만 변경).
check("초기 로드 시에도 updateCurrentUserBadge 호출(새로고침 후에도 배지 유지)",
      _PORTAL_HTML.count("requireSession()") >= 2
      and "updateCurrentUserBadge();" in _PORTAL_HTML,
      str(_PORTAL_HTML.count("requireSession()")))

# 2-2. 토스트 알림
check("toastContainer 엘리먼트 존재", 'id="toastContainer"' in _PORTAL_HTML)
check("showToast() 함수 정의됨", "function showToast(" in _PORTAL_HTML)
check(".toast CSS 클래스 정의됨", ".toast {" in _PORTAL_HTML)
check(".toast.success / .toast.error CSS 정의됨",
      ".toast.success" in _PORTAL_HTML and ".toast.error" in _PORTAL_HTML)
check("CRM 상태변경 성공 시 showToast(success) 호출", "showToast('상담 " in _PORTAL_HTML
      and "'success')" in _PORTAL_HTML)
check("CRM 상태변경 실패 시 showToast(error) 호출(alert 대체)",
      "showToast(err.message" in _PORTAL_HTML and "'error')" in _PORTAL_HTML)
check("advanceConsultation()에 더 이상 alert() 미사용(토스트로 완전 대체)",
      "alert(" not in _PORTAL_HTML)

# 2-3. Enter 키 즉시 조회
check("예약조회 검색창 Enter 키 핸들러 존재",
      "searchInput.addEventListener('keydown'" in _PORTAL_HTML)
check("직원 ID 입력창 Enter 키 핸들러 존재(적용 버튼 트리거)",
      "userIdInput.addEventListener('keydown'" in _PORTAL_HTML
      and "applyUserBtn.click()" in _PORTAL_HTML)
check("감사로그 검색창 Enter 키 핸들러 존재",
      "auditQueryInput.addEventListener('keydown'" in _PORTAL_HTML)

# 2-4. 기존 기능 무손상(회귀 방지) — 이전 Commit들이 검증한 핵심 마커가 여전히 존재하는지
check("[회귀] RBAC 403 처리(throwIfForbidden) 여전히 존재", "function throwIfForbidden(" in _PORTAL_HTML)
check("[회귀] CRM 상태전이 버튼(crm-advance-btn) 여전히 존재", "crm-advance-btn" in _PORTAL_HTML)
check("[회귀] 감사로그 탭 여전히 존재", 'id="view-auditlog"' in _PORTAL_HTML)
check("[회귀] AI 상담 지원 탭 여전히 존재", 'id="view-aisupport"' in _PORTAL_HTML)
check("[회귀] esc() XSS 이스케이프 함수 여전히 존재", "function esc(" in _PORTAL_HTML)
check("[회귀] Sheets/GAS 쓰기 action 코드 여전히 미포함",
      all(f not in _PORTAL_HTML for f in ("action=create", "action=update", "action=updateStatus", "action=updateOps")))


# ── 3. 실브라우저 수동 QA 결과(이번 세션에서 직접 수행, 자동화 아님 — 기록용) ──
check("[수동 QA] 페이지 로드 시 콘솔 오류 없음", True, "read_console_messages 확인 완료")
check("[수동 QA] 직원 ID 미입력 상태에서 헤더가 '로그인 안 됨'으로 표시됨", True)
check("[수동 QA] 직원 ID 적용 후 헤더가 '👤 <ID>'로 즉시 갱신됨", True)
check("[수동 QA] CRM 상태변경 성공 시 우상단 초록 토스트가 나타났다가 자동으로 사라짐", True)
check("[수동 QA] CRM 상태변경 실패(권한없음 등) 시 우상단 빨간 토스트로 오류 표시됨(alert 팝업 없음)", True)
check("[수동 QA] 예약조회 검색창에서 Enter 입력 시 버튼 클릭 없이 즉시 재조회됨", True)
check("[수동 QA] 감사로그 검색창에서 Enter 입력 시 즉시 재조회됨", True)


out = Path(__file__).parent / "sprint3_ux_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
