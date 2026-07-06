# STEP 1.5 — create API 실검증(QA) 결과

> 대상: Apps Script `/exec` (배포본 v3_final, 시트 `종합검진_예약대장`, 문서 1WFnsy…)
> 방식: 실서버 직접 호출(curl) — reservation_v2_new.html이 호출하는 것과 동일한 create 엔드포인트
> 원칙: 코드 미수정, QA 결과만 보고 · 더미 데이터만 사용 · 검증일 2026-07-01

---

## 종합 판정: ⚠️ 부분 통과 — create/append/채번/재전송 정상, **날짜·시간 포맷 결함 1건 발견**

| # | 항목 | 결과 |
|---|------|------|
| 1 | create 호출 | ✅ `{"ok":true,"message":"예약 등록 완료"}` |
| 2 | Google Sheets 행 생성(append) | ✅ get 재조회 + list count로 확인 (3행 생성) |
| 3 | ReservationNo | ✅ 서버 채번 `20260701-0001 → 0002 → 0003` (순차 +1) |
| 4 | Response JSON | ✅ 스키마 `{ok, message, data:{reservationNo, createdAt}}` 정상 |
| 5 | 재전송 | ✅ 동일 데이터 재전송 시 **새 번호로 별도 행** 생성(중복검사 없음 — 설계상 정상) |
| 6 | 날짜/시간 포맷 | ❌ **결함** (아래) |
| — | 한글 인코딩 | ✅ 백엔드 정상(UTF-8). 초기 깨짐은 curl(Windows) 테스트 방식 문제로 확정 |

---

## Response JSON (원문)

create #1:
```json
{"ok":true,"message":"예약 등록 완료","data":{"reservationNo":"20260701-0001","createdAt":"2026-07-01 11:31:56"}}
```
create #2(재전송):
```json
{"ok":true,"message":"예약 등록 완료","data":{"reservationNo":"20260701-0002","createdAt":"2026-07-01 11:31:58"}}
```
get #3(UTF-8 본문, 저장 확인):
```json
{"ok":true,"data":{"reservationNo":"20260701-0003","name":"QA테스트","birth":"1980-05-05 00:00:00",
"gender":"남성","program":"SMART","wishDate":"2026-07-20 00:00:00","wishTime":"1899-12-30 09:00:00",
"optionalTests":"갑상선 초음파, 위내시경(수면)","company":"QA더미사업장","status":"예약접수", ...}}
```

---

## 🔴 발견된 결함 (CRITICAL) — 날짜/시간 필드 자동 변환

| 필드 | 보낸 값 | 저장/응답 값 | 기대값 |
|------|---------|-------------|--------|
| `birth` | `1980-05-05` | `1980-05-05 00:00:00` | `1980-05-05` |
| `wishDate` | `2026-07-20` | `2026-07-20 00:00:00` | `2026-07-20` |
| `wishTime` | `09:00` | `1899-12-30 09:00:00` | `09:00` |

**근본 원인** (정적 점검 '주의5'가 실제로 발현):
1. `appendRow`가 문자열을 쓰면 Google Sheets가 날짜/시간처럼 보이는 값을 **Date/시간 serial로 자동 변환**(셀 서식 '자동').
2. 읽을 때 `_rowToObj`가 `val instanceof Date`이면 `DATE_FORMAT='yyyy-MM-dd HH:mm:ss'`로 포맷 → 날짜에 시간이 붙고, `09:00`은 스프레드시트 기준일(1899-12-30) 기반 datetime으로 왜곡.

**영향 범위**:
- 화면 표시 오류(특히 `wishTime`이 `1899-12-30 09:00:00`으로 완전 왜곡).
- `_actionSummary`의 당일 매칭 `String(희망검진일) === 'YYYY-MM-DD'`가 `"...00:00:00"` 때문에 **불일치 → 당일 통계 0 처리** 위험.
- `_actionList`의 `dateFrom/dateTo` 필터 부정확 가능.
- 이 결함은 UTF-8/브라우저와 무관하게 **실운영에서도 동일 발생**.

**수정 방향(다음 단계에서 결정 — 이번엔 미수정)**:
- (A) 쓰기 시 birth/wishDate/wishTime 열 서식을 **텍스트('@')로 지정** 후 append → 자동 변환 차단(권장, 데이터 원본 보존).
- (B) 읽기 시 `_rowToObj`를 **필드별 포맷 적용**(birth·wishDate→`DATE_ONLY`, wishTime→`HH:mm`, createdAt 등만 datetime).
- (A)+(B) 병행이 가장 안전.

---

## 정리

- **예약 저장 핵심 기능(create→append→채번→재전송→Response)은 실서버·실시트에서 정상 동작 확인.**
- 단, **날짜/시간 포맷 결함**으로 인해 "완전 통과"는 아니며, STEP 2(관리자 화면) 진행 전 또는 병행하여 이 결함 수정을 권장.
- 한글 인코딩은 백엔드 정상(초기 깨짐은 테스트 도구 문제).

## 정리 필요 (사용자 조치)
- 시트 `종합검진_예약대장`에 **QA 더미 3행(20260701-0001·0002·0003)** 이 생성되어 있습니다. 검토 후 삭제 권장.
  - 0001·0002는 curl 인코딩 문제로 한글이 깨져 있으니 특히 삭제 대상. (삭제는 사용자 승인 후 진행 원칙 — 제가 임의 삭제하지 않았습니다.)

*QA 결과 보고 · 코드 미수정 · 저장: CMC_Platform_new/*
