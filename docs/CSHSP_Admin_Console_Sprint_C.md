# CSHSP Admin Console — Sprint C 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** C — Admin Console 구현
> **작성일:** 2026-07-02
> **위치:** `99_임시보관_정리대기/CMC_Platform_new/admin/`
> **실행:** `npx serve -p 4000 CMC_Platform_new` (또는 `python -m http.server`) → `http://localhost:4000/admin/`

---

## 1. Sprint C 목적

Sprint A(Core Data Layer) + Sprint B(Reservation Engine) 기반으로, 검진센터 직원이
예약 조회·승인·거절·취소·Slot 관리·일정 조회·감사로그 확인을 수행하는 관리자 콘솔을 구현한다.

- AI는 예약 확정 권한이 없음 — 승인 화면에서 직원 계정만 CONFIRMED 처리 가능 (UI에서 실증)
- 목록 화면 개인정보 최소 표시, 상세 화면 제한적 표시 (RBAC 연동 지점 분리)
- 모든 조작은 감사로그 기록

## 2. 관리자 콘솔 구조

```
admin/
├── index.html      메인 콘솔 (사이드바 + 7개 화면 SPA)
├── admin.css       스타일 (라이트 운영 테마, 반응형)
├── admin.js        UI 컨트롤러 — AdminAPI를 통해서만 데이터 접근
├── admin_api.js    ★ API 어댑터 (MODE='mock' → Sprint D에서 'live' REST로 교체)
└── test.html       자동 테스트 하니스 (29개 검증)
```

기존 구조(순수 HTML/CSS/JS, 외부 라이브러리 없음)를 따르며 기존 파일 수정 없음.

**Mock API 설계**: `admin_api.js`의 함수는 Sprint B `reservation_engine.py`와 1:1 대응
(`approveReservation ↔ approve_reservation`, `rejectReservation ↔ reject_reservation`,
`cancelReservation ↔ cancel_reservation`, `releaseHold`). 데이터는 `data/*.json`을 fetch로
읽고, 조작은 세션 메모리에서 엔진 로직(권한 확인 → 상태 전이 → Slot 점유/해제 → 감사기록)을
미러링한다. Sprint D에서 fetch 대상만 REST API로 바꾸면 화면 코드는 그대로 재사용된다.
UI에 "Mock 모드" 배너로 명시.

## 3. 메뉴 구성

| 메뉴 | 화면 | 상태 |
|------|------|------|
| Dashboard 요약 | KPI 카드 7종 + 승인 대기 바로가기 | ✅ |
| 예약 승인 대기 | PENDING_APPROVAL 목록 + 승인/거절 버튼 | ✅ |
| 전체 예약 목록 | 상태 필터 10종 + 통합 검색 | ✅ |
| 예약 상세 | 목록 행 클릭 진입 (별도 화면) | ✅ |
| Slot 관리 | 상태 필터 + HOLD 해제 | ✅ |
| 일정 관리 | 5개 탭 조회 (수정은 Sprint D 이후) | ✅ 조회 |
| 감사로그 | 이벤트/대상/사용자/날짜 필터 | ✅ |

우상단 "로그인 직원" 셀렉터로 계정을 전환하며 권한 동작(AI 계정 차단 등)을 실증할 수 있다
(Sprint D에서 실제 로그인으로 대체).

## 4. 예약 승인 대기함

- PENDING_APPROVAL만 조회. 표시: 예약번호·신청일시·수검자명·생년월일(YYYY****)·프로그램·희망일시·신청경로·상태·승인/거절 버튼
- 승인: `AdminAPI.approveReservation(id, 현재직원)` → 권한 확인(reservation:approve) → CONFIRMED → Slot 점유(정원 도달 시 FULL) → `RESERVATION_APPROVED` 감사기록 → 토스트 알림
- 거절: `rejectReservation` → REJECTED + Slot 복구 + `RESERVATION_REJECTED`
- AI 예약비서(ROLE-AI-AGENT) 계정 선택 시 승인 거부됨 — 원칙 3 실증

## 5. 전체 예약 목록

- 상태 필터: 전체 + 9개 표준 상태 (REQUESTED~REJECTED)
- 통합 검색: 예약번호 / 수검자명 / 전화 뒷4자리(정확 일치) / 프로그램 코드·명 / 날짜(YYYY-MM-DD)
- 목록 개인정보: 생년월일 `1988****`, 전화 `010-****-0002` 마스킹

## 6. 예약 상세

- 예약 기본정보 / 수검자 / 프로그램 / Slot / 신청경로 / 상태 / 해당 예약의 감사로그 이력
- **가능한 다음 액션**: `StateMachine.allowedNext()`(state_machine.py 미러) 기준 칩 표시 + 해당 액션 버튼(승인/거절/취소)만 노출. 종결 상태는 "종결 상태" 표시
- 상세 개인정보는 `Privacy.detailLevel(roleId)`로 분리 — STAFF/ADMIN/DIRECTOR는 FULL, 그 외 MASKED (향후 서버 RBAC 대체 지점)

## 7. Slot 관리

- 표시: 날짜·시간·검사실·장비·담당의(해당 요일 근무)·간호사·정원·예약·대기·상태
- 상태 필터 6종 (AVAILABLE/FULL/WAITING/DUPLICATED/HOLD/BLOCKED)
- **HOLD 해제**: `slot:manage` 권한 필요, 해제 시 `SLOT_RELEASED` 감사기록, 정원 기준 AVAILABLE/FULL 복구

## 8. 일정 관리 (조회 중심)

탭 5개: 의사(근무요일+등록일정) / 간호사 / 검사실(층·순번) / 장비(모델·점검일정) / 휴진일·공휴일.
등록·수정 기능은 Sprint D 이후로 이관.

## 9. 감사로그 조회

- 필터: 이벤트 유형(12종) / 텍스트(예약번호·사용자) / 날짜
- 표시: 발생일시·이벤트·대상(entityType+entityId)·수행자(+역할)·상세(note/after)
- 세션 중 발생한 조작(mock)도 즉시 반영 표시

## 10. Dashboard 요약 (KPI 7종)

| KPI | 산출 |
|-----|------|
| 오늘 예약 신청 | requestedAt이 오늘인 예약 수 |
| 승인 대기 / 확정 / 취소 / 노쇼 | 상태별 건수 |
| Slot 가동률 | Σ reservedCount ÷ Σ capacity (BLOCKED 제외) × 100 |
| 온라인 예약 비율 | channel ∈ {WEB, AI_ASSISTANT} ÷ 전체 × 100 |

## 11. 개인정보 표시 기준

- 목록: 이름 표시, 생년월일 `YYYY****`, 전화 `010-****-1234` (`Privacy.maskBirth/maskPhone`)
- 상세: 역할 기반 `Privacy.detailLevel()` — RBAC 적용 지점을 UI 로직에서 분리
- Sprint D에서 서버 측 RBAC/필드 레벨 마스킹으로 이관 예정

## 12. 테스트 결과

**자동 테스트 29건 + 브라우저 상호작용 검증 8건 = 37건 전체 PASS**
(결과: `tests/sprint_c_test_result.csv`, 하니스: `admin/test.html`)

- 요구 항목 전부 검증: 화면 로드(콘솔 오류 0) / 승인 대기 표시 / 상태 필터 / 5종 검색 / 상세+allowed_next / Slot 목록 / 감사로그 / KPI 계산 / 마스킹
- 실동작 검증: 승인 버튼 클릭 → CONFIRMED + Slot reservedCount 2→3 + 감사기록 + 대기 배지 (1)→(0)
- 권한 실증: AI 계정 승인·HOLD 해제 모두 차단
- Sprint B Python 테스트 회귀: 38/38 PASS 유지

## 13. 발견된 문제

1. **시드 감사로그 이벤트명 불일치** — Sprint A 시드가 구 명칭(RESERVATION_APPROVE 등) 사용 → Sprint B 표준(RESERVATION_APPROVED 등)으로 `data/audit_logs.json` 정합화 (자체 QA 더미 데이터 수정, 3건 + meta)
2. **Mock 모드 한계** — 조작이 세션 메모리에만 반영되어 새로고침 시 초기화. Sprint D API 연동으로 해소
3. **동시 편집 미보호** — 두 직원이 동시에 같은 예약 처리 시 감지 불가 (Sprint D 서버 처리 필요)
4. **로그인 없음** — 직원 셀렉터는 데모용. 실제 인증·세션 관리는 Sprint D 범위

## 14. Sprint D 제안 (API Layer)

| 우선순위 | 작업 | 비고 |
|:---:|------|------|
| 1 | Python HTTP API 서버 (표준 라이브러리 또는 FastAPI) — reservation_engine 함수를 REST로 노출 | POST /api/reservations, POST /api/reservations/{id}/approve 등 |
| 2 | `admin_api.js` MODE='live' 구현 — fetch 대상만 API로 전환 | 화면 코드 무수정 |
| 3 | 인증/세션 + 서버 측 RBAC (Privacy.detailLevel 서버 이관) | users/roles.json 기반 |
| 4 | 동시성 제어 (파일 잠금 또는 SQLite 이관) | Sprint B 리스크 해소 |
| 5 | Slot/일정 등록·수정 API + 화면 | 일정 관리 쓰기 기능 |
| 6 | Dashboard API (KPI 서버 계산) + AI Agent용 예약신청 API | Sprint E AI 연계 준비 |

---

*CSHSP Sprint C | 2026-07-02 | 천안의료원 건강검진센터*
