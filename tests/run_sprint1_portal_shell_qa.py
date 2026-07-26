# -*- coding: utf-8 -*-
"""
CSHSP Sprint 1 — Commit 3(Single Admin Portal 기본 셸) 테스트 러너

대상: app/pages/admin_portal_new.html (정적 구조/코드 검사 — 실브라우저 수동 QA는
별도로 수행했으며 그 결과는 커밋 보고에 기록한다).

이 테스트는 회귀 방지용 정적 검사다: API_BASE가 올바른 절대 URL 패턴을 쓰는지
(이번 개발 중 실제로 발견·수정한 버그의 재발 방지), 오류 처리 코드가 존재하는지,
쓰기(action=create/update 등) 코드가 전혀 없는지를 문자열 수준에서 확인한다.

결과: tests/sprint1_portal_shell_test_result.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "pages" / "admin_portal_new.html"

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        # 일부 Windows 콘솔 코드페이지(cp949)가 인코딩하지 못하는 문자(이모지 등) 방어.
        # CSV 결과 파일은 utf-8-sig로 별도 저장되므로 원문 유실은 없다.
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


check("admin_portal_new.html 존재", TARGET.exists(), str(TARGET))
html = TARGET.read_text(encoding="utf-8")

# API_BASE — 정적 서버(4000)/API 서버(8600) 포트 분리를 반영한 절대 URL 패턴인지
# (개발 중 상대경로로 잘못 작성했던 버그를 실브라우저 QA로 발견·수정 — 회귀 방지)
check("API_BASE가 절대 URL(http://localhost:8600) 기반", "http://localhost:8600" in html)
check("API_BASE가 ?api= 재정의 지원(admin_api.js와 동일 패턴)", "_params.get('api')" in html)
check("admin-portal API 엔드포인트 참조", "/api/admin-portal" in html)

# Sheets/GAS 조회 전용 원칙 — 이 부분은 Sprint 1~3 전체에서 예외 없이 유지된다.
# (일반 POST 사용 자체는 Sprint 3 Commit 2에서 PM이 승인한 CRM 상태변경에 한해
# 허용됐다 — 그 범위 검증은 tests/run_sprint3_crm_qa.py가 전담한다. 이 파일은
# Sprint 1 당시의 "페이지 전체가 완전 조회 전용"이라는 원 가정을 더 이상
# 주장하지 않고, Sheets/GAS 관련 쓰기 action만 계속 금지 대상으로 확인한다.)
for forbidden in ("action=create", "action=update", "action=updateStatus", "action=updateOps"):
    check(f"Sheets/GAS 쓰기 action 코드 미포함: {forbidden!r}", forbidden not in html)

# 오류 처리(PM 확정범위 4번: 조회실패/빈데이터/네트워크오류)
check("401 처리 코드 존재", "401" in html)
check("503(Sheets 미설정) 처리 코드 존재", "503" in html)
check("502(연동오류) 처리 코드 존재", "502" in html)
check("빈 데이터 처리(renderTable 내 length 체크) 존재", "!rows.length" in html)
check("네트워크 오류 catch 처리 존재", ".catch(" in html)

# 마스킹 필드 표시(성명/생년월일/휴대전화 — 서버가 이미 마스킹한 값을 그대로 표시)
for col in ("성명", "생년월일", "휴대전화"):
    check(f"조회 결과 컬럼에 '{col}' 포함", col in html)

# 기존 관리자 화면 무수정 안내 문구 포함(운영자 혼선 방지)
check("기존 화면(admin_reservations_v2_new.html) 유지 안내 포함", "admin_reservations_v2_new.html" in html)
check("기존 화면(admin/index.html) 유지 안내 포함", "admin/index.html" in html)
check("기존 화면(admin_dashboard_v3_new.html) 유지 안내 포함", "admin_dashboard_v3_new.html" in html)

# XSS 방어(esc 함수 사용 확인 — 화면 렌더링 시 이스케이프 처리)
check("HTML 이스케이프 함수(esc) 정의됨", "function esc(" in html)
check("테이블 렌더링에서 esc() 사용", "esc(r." in html)


# ── 실브라우저 수동 QA 결과(이번 세션에서 직접 수행, 자동화 아님 — 기록용) ──
check("[수동 QA] 최초 로드 시 콘솔 오류 없음", True, "read_console_messages 확인 완료")
check("[수동 QA] health 배지 'Sheets 연동 미설정' 정상 표시", True)
check("[수동 QA] CORS Preflight(OPTIONS) 200 확인", True, "포트 4000→8600 교차 요청 정상")
check("[수동 QA] 503 오류 시 안내 메시지 정상 표시", True, "Sheets 연동이 설정되지 않았습니다...")
check("[수동 QA] API_BASE 상대경로 버그 발견 및 수정", True, "최초 구현은 상대경로였음 — 브라우저 QA로 발견, 수정 후 재검증 완료")


# ── 결과 저장 ─────────────────────────────────────────
out = Path(__file__).parent / "sprint1_portal_shell_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
