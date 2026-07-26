# -*- coding: utf-8 -*-
"""
CSHSP Sprint 2 — Commit 3(예약상세) 테스트 러너

PM 결정사항 3: Sprint 1 기존 엔드포인트(GET /api/admin-portal/reservations/{no})를
100% 재사용하며 신규 백엔드 Endpoint를 만들지 않는다. 따라서 이번 Commit은 백엔드
코드 변경이 없고, 프론트엔드(admin_portal_new.html)의 정적 구조만 검사한다.

결과: tests/sprint2_reservation_detail_test_result.csv
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
    try:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")
    except UnicodeEncodeError:
        pass


html = TARGET.read_text(encoding="utf-8")

check("모달 마크업(detailModal) 존재", 'id="detailModal"' in html)
check("모달 닫기 버튼 존재", 'id="detailCloseBtn"' in html)
check("모달 본문 컨테이너 존재", 'id="detailBody"' in html)

# 신규 백엔드 없음 — 기존 Sprint 1 엔드포인트 경로만 재사용하는지(다른 경로 새로 만들지 않았는지)
check("openDetail이 기존 /reservations/{no} 엔드포인트만 호출",
      "PORTAL_BASE + '/reservations/' + encodeURIComponent(reservationNo)" in html)
check("신규 엔드포인트 경로(/api/admin/reservation-detail 등) 미생성", "/reservation-detail" not in html)
check("PUT/DELETE 등 쓰기 메서드 코드 없음", "method: 'PUT'" not in html and "method: 'DELETE'" not in html)
check("상세 응답 저장/수정 관련 코드 없음(save/update 호출)", "saveDetail" not in html and "updateDetail" not in html)

# 조회 전용/에러 처리
for code in ("401", "404", "503", "502"):
    check(f"상세 조회 {code} 처리 코드 존재", html.count(code) >= 1)

# 행 클릭 → 상세 열기 위임 존재(Dashboard 최근예약 + 예약조회 테이블 공용)
check("행 클릭 이벤트 위임(tr[data-no]) 존재", "tr[data-no]" in html)
check("예약조회 결과 테이블에 data-no 속성 부여", 'class="clickable" data-no=' in html)
check("Dashboard 최근예약 테이블에도 data-no 속성 부여(재사용)",
      html.count('class="clickable" data-no=') >= 2, str(html.count('class="clickable" data-no=')))

# ESC/오버레이 클릭으로 닫기(UX 기본 처리)
check("ESC 키로 모달 닫기 처리 존재", "e.key === 'Escape'" in html)
check("오버레이 바깥 클릭으로 모달 닫기 처리 존재", "e.target === detailModal" in html)

# XSS 방어 — 상세 렌더링도 esc() 사용
check("상세 필드 렌더링에도 esc() 사용", "esc(d[f[0]]" in html)


out = Path(__file__).parent / "sprint2_reservation_detail_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nTotal {len(results)} / PASS {len(results) - fails} / FAIL {fails}")
print(f"Result saved: {out}")
sys.exit(1 if fails else 0)
