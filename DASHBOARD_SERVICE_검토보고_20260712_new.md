# dashboard_sheets_service_new.js 커밋 전 검토 보고 (2026-07-12)

> 대상: `app/services/dashboard_sheets_service_new.js` (워킹트리 미커밋 수정분)
> 목적: 커밋 승인 판단 자료. 사용자 요청 4개 항목(diff / 정본 판단 근거 / 회귀 테스트 영향 / 변경 범위) 순으로 기술.

---

## 1. HEAD ↔ Working Tree diff 요약

전체 diff는 `git diff -- app/services/dashboard_sheets_service_new.js`로 확인 가능. 실질 변경은 아래 4가지.

### (1) 기능 변경 — HotFix#1 로직 복원 (핵심)

| 위치 | HEAD (현재 커밋 상태) | Working Tree |
|---|---|---|
| `fetchRecentList()` | `list&dateFrom=30일전&dateTo=오늘` (30일 필터) | `list` 무필터 전체 조회 |
| `statusCounts()` | `statusCounts(summary)` 1-인자 — 오늘 요약만 집계 | `statusCounts(summary, allList)` 2-인자 — 전체 목록 누적 집계 |
| `_daysAgo()` | 존재 | 삭제 (30일 필터 제거로 불필요) |

### (2) 구문 하드닝 (동작 동일)

- 템플릿 리터럴 → 문자열 연결, 화살표 함수 → `function`, 스프레드(`...`) → `Object.assign`, `Math.max(...)` → `apply`
- 주석의 유니코드 화살표(`→`) → ASCII(`->`), 박스 문자(`──`) 제거
- 추정 사유: cc5803f에서 확인된 FUSE 파일 잘림 사고 이후 특수문자/최신 구문 회피 목적

### (3) `_get()` 개선 (소규모)

- 쿼리스트링이 빈 경우 `?` 없이 호출하도록 처리 (무필터 `list` 호출 시 필요)

### (4) 주석/로그 문구 정리 — 동작 무관

---

## 2. Working Tree가 정본이라고 판단한 근거

git 이력 분석으로 3단계 사고 경위가 확인된다.

1. **`b5bb240` (HotFix#1, 7/7)** — "Dashboard 전체 0 표시 수정". 커밋 메시지에 이 파일의 두 가지 수정(날짜 필터 제거, statusCounts 누적 집계)이 명시됨. **그러나 이 커밋에 포함된 파일 blob(`3f67dc0`)은 잘린 파일이다** — `recentN(recentList, n)`에서 중간 절단, 개행 없이 끝남(git이 `\ No newline at end of file` 표시). 즉 HotFix#1 커밋 자체가 FUSE 잘림 피해본이었다.
2. **`cc5803f` (Critical HotFix, "FUSE 파일 잘림 복구")** — 잘린 파일을 복구하면서 **HotFix#1 이전 버전(blob `edf688e`, `65682ac` 시점과 동일)으로 되돌려 커밋**했다. 이때 HotFix#1의 기능 수정이 유실됐다. 이 상태가 현재 HEAD까지 이어짐(dc6bcb9, 3288382는 이 파일을 건드리지 않음).
3. **Working Tree (blob `4612204`)** — 완전한 파일 + HotFix#1 기능 수정 복원 + 구문 하드닝. 어떤 커밋과도 blob이 일치하지 않는 미커밋 상태.

**결정적 근거 — 호출부와의 정합성**: HotFix#1은 이 파일과 함께 `admin_dashboard_new_v2.html`도 수정했고(2-인자 호출 `statusCounts(summary, recentList)`, 현재 HEAD의 [admin_dashboard_new_v2.html:228](app/pages/admin_dashboard_new_v2.html)에 커밋되어 있음), cc5803f는 HTML 쪽은 되돌리지 않았다. 즉 **현재 HEAD는 HTML(2-인자 호출) ↔ 서비스(1-인자 정의)가 불일치**한 상태다. JS 특성상 크래시는 없지만 두 번째 인자가 무시되어, Live 모드에서 오늘 예약이 없으면 KPI가 전체 0으로 표시되는 **HotFix#1 이전 버그가 재발**한다. Working Tree 버전만이 커밋된 HTML과 정합한다.

## 3. 회귀 테스트 영향

| 테스트 | 결과 | 비고 |
|---|---|---|
| DEV-003 3종 (backend 26 / frontend 29 / adapter 5) | **60/60 PASS** | 본 세션에서 워킹트리 상태로 재실행 완료 |
| `node --check` 구문 검사 | PASS | 파일 완결성 확인 (`};`로 정상 종료, 잘림 없음) |
| 전용 단위 테스트 | 없음 | 이 파일을 직접 검증하는 자동화 스위트는 부재. 커밋 후 `admin_dashboard_new_v2.html` 실브라우저 확인 권장 (Follow-up #1과 병행 가능) |

- GAS(.gs), 예약 흐름, STEP1.5 DateFix와는 **접점 없음** — 이 파일은 프론트 대시보드 읽기 전용 서비스로, `summary`/`list` GET 호출만 수행. 쓰기 API·시트 데이터 형식에 영향 없음.

## 4. 변경 범위

- **파일 1개만 변경**: `app/services/dashboard_sheets_service_new.js` (net +56/−56줄)
- **사용처 1곳**: `admin_dashboard_new_v2.html`의 `dashboardInit` 경로만 이 서비스(`CMC_DashboardSheets`)를 사용. 다른 페이지(admin_reservations 계열 등)는 `CMC_Stats`(localStorage)를 직접 호출하므로 무관
- API 계약 변경 없음(추가 인자는 하위호환), GAS·데이터 저장소·구조 변경 없음 → **Architecture Freeze 위반 없음**

## 5. 권고

**커밋 승인 권고.** 커밋 메시지 제안:

```
fix: dashboard 서비스 HotFix#1 유실분 복원 (FUSE 복구 시 회귀)

- cc5803f가 FUSE 잘림 복구 과정에서 dashboard_sheets_service_new.js를
  HotFix#1(b5bb240) 이전 버전으로 되돌려 '전체 0 표시' 수정이 유실됨
- fetchRecentList 날짜 필터 제거 + statusCounts(summary, allList) 복원
- 특수문자/최신구문 회피 하드닝 (FUSE 잘림 재발 방지)
- 검증: DEV-003 60/60 PASS, node --check PASS
```
