# Release Report — v1.0.0-pilot

**릴리스일**: 2026-07-12
**프로젝트**: CSHSP (CMC Health Screening Platform) — 천안의료원 건강검진센터 AI 예약 컨시어지

---

## 1. Commit / Tag

| 항목 | 값 |
|---|---|
| **Tag** | `v1.0.0-pilot` (annotated, origin push 완료) |
| **Tag 대상 Commit** | `b390fa1` docs: v1.0.0-pilot 릴리스 문서 갱신 |
| 포함 주요 커밋 | `3288382` feat(DEV-003) · `353b72f` fix(HotFix#1 복원) · `b390fa1` docs |
| 원격 | https://github.com/smdwho4-alt/CMC_Platform (main, 태그 포함 push 완료) |

## 2. 포함 기능 (v0.9.0-pilot 이후)

- **DEV-003 — 관리자 예약관리 Google Sheets Live 연동** (`3288382`)
  - `admin_reservations_v2_new.html` 신규 (원본 화면 무수정) — 조회·상태변경·메모저장 Live 모드
  - GAS `_actionUpdateStatus`/`_actionUpdate` LockService 보강
  - 어댑터 503 오류 메시지 전달 결함 수정
- GAS 웹앱 URL 연동·운영 모드 전환 (Task #43, `65682ac`)
- 운영 버전 업데이트 — 리플렛 기준 (Task #44, `dc6bcb9`)
- **STEP1.5 DateFix 실배포** — GAS Version 5 "새 버전" 재배포 (사용자 수행), v0.9.0의 Pilot Ready 차단 Known Issue 해소

## 3. HotFix

| HotFix | 커밋 | 내용 |
|---|---|---|
| HotFix #1 | `b5bb240` | Dashboard 전체 0 표시 수정 (30일 필터 제거 + 누적 집계) |
| Critical HotFix | `cc5803f` | FUSE 파일 잘림 복구 + 배포 404 파일(app/data) 추가 |
| **HotFix #1 유실분 복원** | `353b72f` | cc5803f 복구 과정에서 `dashboard_sheets_service_new.js`가 HotFix#1 이전으로 회귀 → 커밋된 HTML(2-인자 `statusCounts`)과 정합하도록 복원. **신규 기능 아님, HEAD/HTML 정합성 복구 목적.** 검증: DEV-003 60/60 PASS |

추가로 이번 점검에서 `app/data/` 3파일의 삭제 스테이징(배포 404 재발 위험)을 발견해 취소함 — 커밋 이력에는 영향 없음.

## 4. Known Limitations (Follow-up 3건)

| # | 항목 | 위험도 | 계획 |
|---|---|---|---|
| 1 | `reservation_v2_new.html` 실브라우저 QA 미완 | 낮음 (파일 무수정 확인) | Pilot 초기 병행 수행 |
| 2 | LockService 실동시성(503) 미검증 | 중간 (Pilot 동시접속 낮아 제한적) | Pilot 중 검증 |
| 3 | `CMC_CONFIG.load()` 모드전환 롤백 미작동 | 중간 (기존 결함) | 별도 세션 진행 중 (task_a8cf5790) |

**정식 운영 전환 전 필수 (Pilot 범위 밖)**: 관리자 인증(로그인), HTTPS, 더미 데이터/계정 정리(Date 손상 셀 포함), 실키 스모크 테스트.

## 5. Release Checklist 결과

| # | 항목 | 결과 |
|---|---|---|
| 1 | GAS 재배포 ("새 버전") | ✅ Version 5 완료 |
| 2 | Live 응답시간 (NFR 3초) | ✅ 1.765초 |
| 3 | 작업트리 정리 (app/data 삭제 취소, HotFix 복원 커밋) | ✅ 완료 |
| 4 | DEV-003 + 복원 커밋 origin push | ✅ 완료 |
| 5 | CHANGELOG.md 갱신 | ✅ 완료 (`b390fa1`) |
| 6 | PROJECT_STATUS.md 갱신 | ✅ 완료 (`b390fa1`) |
| 7 | v1.0.0-pilot 태그 생성·push | ✅ 완료 |
| 8 | 실브라우저 QA / 실동시성 / CONFIG 롤백 | 🔲 Follow-up 3건으로 이월 (§4) |

참고: 로컬 작업트리에 LF/CRLF 왕복(순변경 0)인 파일 6종과 테스트 결과 CSV 1종이 남아있으나 HEAD와 실질 차이가 없어 릴리스에 영향 없음 (사용자 지시로 원복 보류).

## 6. Pilot 운영 준비 상태

**판정: 🟢 Pilot 운영 가능 (조건부 Pilot Ready)**

- 차단 이슈(STEP1.5 DateFix 미배포)는 해소됨. DEV-003 Live 검증 5개 시나리오 전부 PASS, 응답속도 NFR 충족.
- 테스트 현황: 자동화 148/148 + DEV-003 60/60 + DateFix 회귀 150건 FAIL 0 + 금지응답 35/35 + 백업·복구 9/9.
- 잔여 Follow-up 3건은 Pilot 차단 요인이 아니며, Pilot 운영과 병행 해소한다.
- 운영 절차: Sprint H 산출물(일일 체크리스트, Stop Criteria, 장애 대응 P1/P2/P3) 적용.

## 7. 관련 문서

- [PILOT_CHECK_20260712_new.md](PILOT_CHECK_20260712_new.md) — 릴리스 전 전체 점검
- [DASHBOARD_SERVICE_검토보고_20260712_new.md](DASHBOARD_SERVICE_검토보고_20260712_new.md) — HotFix 복원 커밋 검토
- [CHANGELOG.md](CHANGELOG.md) · [PROJECT_STATUS.md](PROJECT_STATUS.md) · [ROADMAP.md](ROADMAP.md)
