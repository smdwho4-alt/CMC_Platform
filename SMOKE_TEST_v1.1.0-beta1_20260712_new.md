# Smoke Test 결과 — Pilot v3 전환 (v1.1.0-beta1)

- 일시: 2026-07-12 18:20~18:27 (실브라우저, Pilot 실환경 127.0.0.1:4000)
- 대상: `app/pages/reservation_v3_new.html` (Rule 기반 선택검사) + Google Sheets LIVE 저장
- 승인: PM (DEV-004 APPROVED, Pilot v3 전환 승인 조건 이행)

## 결과: 10/10 PASS → Pilot 운영 시작 조건 충족

| # | 항목 | 결과 | 근거 |
|---|---|---|---|
| 1 | Program 선택 | PASS | 6개 카드 렌더링(BASIC/SMART/VIP/PREMIUM/YOUNG/온김에검진), 선택·전환 정상 |
| 2 | BASIC 표시 | PASS | A 0/2(12항목)·B 0/2(14항목) |
| 3 | SMART 표시 | PASS | A 0/5(13항목)·B 0/2(14항목) |
| 4 | VIP 표시 | PASS | A 0/5(15항목)·B 0/1(8항목)·C 0/3(13항목) |
| 5 | PREMIUM 표시 | PASS | A 0/5(15항목)·B 0/2(9항목)·C 0/3(13항목) |
| 6 | 그룹별 선택 개수 제한 | PASS | PREMIUM B(2개 제한) 3번째 클릭 차단, 2/2 유지 + 경고 메시지 표시 |
| 7 | 성별 제한 | PASS | 남성 선택 시 인유두종바이러스 검사 자동 해제·비활성 |
| 8 | 프로그램 가격 표시 | PASS | PREMIUM 남성 1,300,000원 (성별 미선택 시 남/여 병기) |
| 9 | 예약 저장 | PASS | 제출 → 성공 화면, 서버 채번 예약번호 `20260712-0001` |
| 10 | Google Sheets 저장 | PASS | Apps Script `action=get&no=20260712-0001` 조회로 실기록 확인 — 이름·프로그램·상태(예약접수)·선택검사 10건(그룹 표기 포함) 일치 |

## 이행 확인 (PM 승인 조건)

1. Git Commit — `d57ea4b`(릴리스 문서) / `93a189a`(Operation Toolkit v1.0.2) / `ce6cce2`(DEV-004)
2. Git Tag — **v1.1.0-beta1** (annotated)
3. Toolkit 설정 v3 전환 — `tools/settings_new.ps1` ReservationUrl → `reservation_v3_new.html` (pilot-check 예약 페이지 HTTP 200 확인)
4. Rollback 유지 — v1/v2 페이지 파일 보존, settings 주석에 롤백 URL 명기(설정 1줄 복원으로 즉시 복귀)
5. VIP B그룹 MRA(뇌/목) 단일 항목 정책 — 구현 일치 확인(Rule 단일 항목, 변경 불필요)

## 후속 조치 필요

- **테스트 예약 정리**: Sheets `종합검진_예약대장`의 `20260712-0001` (이름 `스모크테스트_v3전환`, 사업장 `내부테스트(삭제요망)`) — 운영 데이터가 아니므로 담당자가 취소/삭제 처리 요망
- pilot-check의 Apps Script URL 항목이 간헐적 timeout WARN 표시 가능(콜드스타트) — 직후 Sheets ping PASS면 정상
- DEV-005(AI Recommendation Engine)는 Pilot 안정화 후 착수 (Badge·추천사유 영역 확보 완료 상태)
