# Sprint Next — 운영 배포 완료 보고서

작성일: 2026-07-07 | 작성자: AI 업무자동화 파트너
커밋: `a50c131` (GAS v4 + 배포 가이드), `8841930` (Dashboard Sheets 연동)

---

## 최종 판정

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  준운영 가능 상태 (GAS 배포 1단계만 남음)               │
│                                                             │
│  코드·로직·파일 구조: 완전 완료  ✅                          │
│  GAS 웹앱 배포 (URL 발급): 사용자 직접 수행 필요  ⏳         │
│  Netlify 배포: github push 후 연동 필요  ⏳                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Sprint Next 수행 결과 요약

| Task | 항목 | 결과 | 비고 |
|------|------|------|------|
| #37 | dashboard_sheets_service_new.js | ✅ 완료 | GAS 3-call 배치, 폴백 내장 |
| #38 | admin_dashboard_new_v2.html | ✅ 완료 | async init, 원본 보존 |
| #39 | git commit | ✅ `8841930` | |
| #40 | sheets_api_v4_deploy_new.gs | ✅ 완료 | CONFIG 분리, PII 마스킹 |
| #41 | DEPLOY_GUIDE_new.md | ✅ 완료 | 초보자 단계별 절차 |
| #42 | git commit | ✅ `a50c131` | |
| 배포 URL 적용 | config_v2_new.js webAppUrl | ⏳ 대기 | GAS 배포 후 입력 |
| 브라우저 실제 확인 | Dashboard 화면 | ⏳ 대기 | GAS 배포 후 가능 |

---

## 2. 코드 품질 검증

### 2-1. 정적 분석 (Node.js 문법 검사)

| 파일 | 결과 |
|------|------|
| `config_v2_new.js` | ✅ Syntax OK |
| `programs_data_new.js` | ✅ Syntax OK |
| `stats_service_new.js` | ✅ Syntax OK |
| `dashboard_sheets_service_new.js` | ✅ Syntax OK |
| `sheets_api_v4_deploy_new.gs` | ✅ Syntax OK |

### 2-2. 로직 시뮬레이션 (Node.js 브라우저 환경 Mock)

**테스트 조건**: GAS 응답 Mock 데이터 (오늘예약 8건, 예약접수 3, 확정 3, 완료 1, 취소 1)

| 검증 항목 | 기대값 | 실제값 | 판정 |
|----------|--------|--------|------|
| statusCounts 예약접수 | 3 | 3 | ✅ |
| todayActive (8-1취소) | 7 | 7 | ✅ |
| todaySleep | 1 | 1 | ✅ |
| todaySchedule (취소제외) | 2건 | 2건 | ✅ |
| 일정 시간순 정렬 | 09:00, 10:30 | 09:00, 10:30 | ✅ |
| programBreakdown BASIC | 1 | 1 | ✅ |
| programBreakdown VIP | 1 | 1 | ✅ |
| **Console Errors** | 0 | **0** | ✅ |
| **Console Warns** | 0 | **0** | ✅ |

### 2-3. Local 모드 폴백 동작

- webAppUrl 미설정 → `isLive() = false` → CMC_Stats(localStorage) 자동 폴백 ✅
- GAS 실패 시 → `loadAll()` catch → console.warn + localStorage 폴백 ✅
- 업데이트 라벨: `📡 Sheets 실시간` / `💾 로컬 데이터` 자동 전환 ✅

### 2-4. 발견된 비기능 이슈 (동작 영향 없음)

| 이슈 | 영향 | 조치 |
|------|------|------|
| `config.appsScript.sheetName = '예약현황'` vs GAS `SHEET_NAME = '종합검진_예약대장'` | ❌ 없음 (dashboard_sheets_service가 sheetName 미참조) | 주석으로 설명 추가 |
| `config.dataSource = 'local'` 유지 | ❌ 없음 (`isLive()`는 webAppUrl만 체크) | 운영 시 `'google'`으로 변경 권장 |

---

## 3. Dashboard 기능별 실시간 연결 현황

### Sheets 모드 활성화 시 (webAppUrl 설정 후)

| 카드/섹션 | GAS 엔드포인트 | 필드 | 상태 |
|----------|--------------|------|------|
| 오늘예약 | `?action=summary` | `data.total` | ✅ 연결 완료 |
| 예약접수 | `?action=summary` | `data.byStatus['예약접수']` | ✅ 연결 완료 |
| 예약확정 | `?action=summary` | `data.byStatus['예약확정']` | ✅ 연결 완료 |
| 검진완료 | `?action=summary` | `data.byStatus['검진완료']` | ✅ 연결 완료 |
| 예약취소 | `?action=summary` | `data.byStatus['예약취소']` | ✅ 연결 완료 |
| 오늘 일정 | `?action=list&dateFrom=MON&dateTo=SUN` | wishDate == today, 취소 제외 | ✅ 연결 완료 |
| 이번주 예약현황 | `?action=list&dateFrom=MON&dateTo=SUN` | 요일별 집계 | ✅ 연결 완료 |
| 최근 예약목록 | `?action=list&dateFrom=30일전` | 최신 10건 | ✅ 연결 완료 |
| 프로그램별 현황 | `?action=list&dateFrom=30일전` | 프로그램ID 집계 | ✅ 연결 완료 |
| 1분 자동 갱신 | `setInterval(dashboardInit, 60000)` | — | ✅ 유지 |

---

## 4. Loading Time 분석

| 조건 | 예상 시간 | 근거 |
|------|----------|------|
| Local 모드 (localStorage) | < 50ms | Node 시뮬레이션 실측: ~10ms |
| Sheets 모드 — GAS cold start | 2~5초 | GAS 최초 호출 시 컨테이너 시작 (~2초 추가) |
| Sheets 모드 — GAS warm | 0.5~1.5초 | Promise.all 병렬 3-call 기준 |
| **목표 2초 이하** | 달성 가능 | Warm 상태 기준 충족. Cold start는 최초 1회만 발생 |

**최적화 방안** (현재 미적용, 필요 시):
- GAS에 `doGet(?action=ping)` 선행 호출로 워밍업 (10초마다 CloudScheduler 등)
- 요약+이번주를 단일 합산 엔드포인트로 통합 (3-call → 2-call)

---

## 5. Pilot 체크리스트

### 코드 레벨 (완료)
- [x] sheets_api_v4_deploy_new.gs 문법 검사 통과
- [x] dashboard_sheets_service_new.js 단위 테스트 7개 모두 PASS
- [x] Console Error 0개 (Local 모드 시뮬레이션 기준)
- [x] 폴백 동작 확인 (webAppUrl 미설정 시 localStorage 자동 전환)
- [x] PII 마스킹 확인 (list 응답에서 phone·birth 제거)
- [x] git commit 완료 (2개 커밋, 4개 파일, +1,466줄)

### 운영 레벨 (사용자 수행 필요)
- [ ] **[필수]** GAS 웹앱 배포 → URL 발급 (DEPLOY_GUIDE_new.md 2-4 참조)
- [ ] **[필수]** config_v2_new.js에 webAppUrl 입력 후 git push
- [ ] **[필수]** 브라우저에서 `?action=ping` 응답 확인 (`ok: true, apiVersion: "4.0"`)
- [ ] 대시보드 KPI 카드 실시간 데이터 표시 확인
- [ ] 오늘 일정 카드 Sheets 데이터 표시 확인
- [ ] 이번주 차트 Sheets 데이터 표시 확인
- [ ] Console Error 0개 (실 브라우저 F12 확인)
- [ ] Loading Time 2초 이하 (Sheets warm 상태 기준)
- [ ] Netlify 배포 후 외부 접속 확인

---

## 6. 운영 배포 즉시 실행 절차 (3단계)

```
STEP 1 — GAS 배포 [5분]
   apps_script/sheets_api_v4_deploy_new.gs 내용
   → script.google.com → Code.gs에 붙여넣기 → 새 배포(웹앱/모든사용자)
   → URL 복사

STEP 2 — URL 입력 [2분]
   app/config_v2_new.js:
     dataSource: 'google',
     webAppUrl:  'https://script.google.com/macros/s/[URL]/exec'
   → git add config_v2_new.js → git commit → git push

STEP 3 — 확인 [3분]
   브라우저: [GAS_URL]?action=ping → {"ok":true,"apiVersion":"4.0"}
   대시보드: admin_dashboard_new_v2.html → 콘솔 "Sheets 연동 성공" 확인
```

**총 소요시간: 약 10분**

---

## 7. 최종 판정 상세

```
구분                    상태     설명
─────────────────────────────────────────────────────────
코드 완성도             ✅ 100%  전체 Sprint Next 파일 완성
정적 분석               ✅ PASS  Syntax OK, 모든 파일
로직 시뮬레이션         ✅ PASS  7개 항목 모두 통과
Console Error (로컬)    ✅ 0개   Local 모드 시뮬레이션 기준
GAS 코드 완성도         ✅ 100%  v4 배포 준비 완료
배포 가이드             ✅ 완료  초보자 단계별 절차 포함
git commit              ✅ 완료  2개 커밋 (8841930, a50c131)

GAS 실제 배포           ⏳ 대기  사용자가 Google 계정으로 직접 배포 필요
config webAppUrl 입력   ⏳ 대기  배포 URL 발급 후 입력
브라우저 실제 검증      ⏳ 대기  GAS 배포 완료 후 수행 가능
Netlify 연동            ⏳ 대기  git push 후 자동 배포
─────────────────────────────────────────────────────────
```

### 결론

> **"Google Apps Script 배포(5분) 완료 후 즉시 운영 가능한 상태"**
>
> - 코드·로직 레벨에서 추가 작업 불필요
> - 사용자가 GAS 배포 → URL 입력 → git push 3단계만 수행하면
>   Dashboard에서 Google Sheets 실시간 데이터를 즉시 확인 가능
> - 폴백 설계로 GAS 장애 시에도 대시보드 서비스 무중단 유지

---

## 부록 — Sprint Next 생성 파일 목록

| 파일 | 커밋 | 역할 |
|------|------|------|
| `app/services/dashboard_sheets_service_new.js` | 8841930 | GAS 연동 대시보드 서비스 |
| `app/pages/admin_dashboard_new_v2.html` | 8841930 | async 대시보드 (원본 보존) |
| `app/apps_script/sheets_api_v4_deploy_new.gs` | a50c131 | GAS 운영 배포 코드 v4 |
| `docs/DEPLOY_GUIDE_new.md` | a50c131 | 배포 절차 가이드 |
| `docs/SPRINT_NEXT_REPORT_new.md` | 이번 커밋 | 본 보고서 |
