# STEP 1.5.1 — 날짜/시간 포맷 결함 수정(DateFix) & 재QA

> 목적: STEP 1.5 QA에서 확인된 birth·wishDate·wishTime 왜곡 수정 (최소 범위, 3개 필드만)
> 대상: `app/apps_script/sheets_api_v3_final.gs`
> 원칙: 다른 컬럼·API 구조·CRUD·ReservationNo·LockService 변경 없음
> 작성: 2026-07-01

---

## 1. 수정 내용 (2곳, 3개 필드 한정)

### ① 쓰기(create) — 텍스트('@') 저장으로 자동 변환 차단
`_actionCreate`의 `appendRow` 직후, **3개 열만** 텍스트 서식으로 재기록:
```js
const r = sheet.getLastRow();
sheet.getRange(r, COL.생년월일).setNumberFormat('@').setValue(String(data.birth    || ''));
sheet.getRange(r, COL.희망검진일).setNumberFormat('@').setValue(String(data.wishDate || ''));
sheet.getRange(r, COL.희망시간).setNumberFormat('@').setValue(String(data.wishTime  || ''));
```
- LockService `try/finally` 블록 내부(잠금 유지 상태)에서 수행.
- 다른 28개 동작·컬럼은 그대로.

### ② 읽기(_rowToObj) — 필드별 포맷 적용
```js
const DATE_ONLY_KEYS = { '생년월일': true, '희망검진일': true };
const TIME_ONLY_KEYS = { '희망시간': true };
// Date 인 경우: 생년월일·희망검진일 → yyyy-MM-dd, 희망시간 → HH:mm, 그 외 → yyyy-MM-dd HH:mm:ss
// 문자열(텍스트 저장)인 경우: 그대로 반환
```
- 쓰기 수정으로 문자열 저장되면 그대로 반환, 혹시 Date로 저장돼도 필드별 포맷으로 정규화(이중 안전장치).

### 변경하지 않은 것
- API 라우팅(doGet/doPost), create/get/list/summary/updateStatus/updateOps/update 로직
- ReservationNo 채번(`_generateNo`), LockService
- birth·wishDate·wishTime 외 모든 컬럼

---

## 2. 재배포 (사용자 조치 — 필수 선행)

재QA는 **수정본이 배포에 반영된 뒤**에만 의미가 있습니다.
1. 수정된 `sheets_api_v3_final.gs` 내용을 Code.gs에 붙여넣기 → 저장
2. 배포 관리 → 편집 → **새 버전** → 배포 (`/exec` URL 유지)
3. `?action=ping` 정상 확인 후 재QA 진행

---

## 3. 재QA 절차 (create 한정) & 합격 기준

| # | 검증 | 합격 기준 |
|---|------|----------|
| 1 | create(더미) | `ok:true`, reservationNo 발급 |
| 2 | get 재조회 `birth` | **`1980-05-05`** (시간 없음) |
| 3 | get 재조회 `wishDate` | **`2026-07-20`** (시간 없음) |
| 4 | get 재조회 `wishTime` | **`09:00`** (1899-12-30 없음) |
| 5 | 그 외 필드 | 기존과 동일(정상 유지) |

---

## 4. 재QA 결과 (1차 시도 — 2026-07-01, 배포 미반영)

재배포 완료 통보 후 신규 생성한 `20260701-0004` 검증 결과, **수정 전과 동일**:

| 필드 | 수정 전 | 재QA(0004) | 판정 |
|------|---------|-----------|------|
| birth | `1980-05-05 00:00:00` | `1980-05-05 00:00:00` | ❌ 미반영 |
| wishDate | `2026-07-20 00:00:00` | `2026-07-20 00:00:00` | ❌ 미반영 |
| wishTime | `1899-12-30 09:00:00` | `1899-12-30 09:00:00` | ❌ 미반영 |
| summary(2026-07-20) | total 0 | total 0 | ❌ 미반영 |

**원인 진단**: 코드 결함이 아니라 **배포 미반영**. 쓰기·읽기 수정 흔적이 전혀 없으므로 `/exec`가 여전히 수정 전 버전을 실행 중. (Apps Script는 Code.gs 저장만으로 웹앱 버전이 갱신되지 않음 → 배포 시 반드시 "새 버전" 선택 필요.)

**조치**: 아래 절차로 재배포 후 재QA 2차 진행.
1. Apps Script 편집기에서 Code.gs에 DateFix 반영본이 있는지 확인
   (검색: `setNumberFormat('@')`, `DATE_ONLY_KEYS` 문자열이 있어야 함)
2. **배포 → 배포 관리 → (연필)편집 → 버전: 반드시 "새 버전" 선택 → 배포**
3. 새 행으로 재QA (birth=1980-05-05 / wishDate=2026-07-20 / wishTime=09:00 확인)

---

## 5. 판정
- ⛔ 현재 **미완료** (배포 미반영으로 재QA 실패).
- 재배포(새 버전) 후 birth·wishDate·wishTime 3개가 기대 포맷으로 확인되면 **STEP 1.5 완료**로 판정.

*코드 수정 3개 필드 한정 · 저장: CMC_Platform_new/*
