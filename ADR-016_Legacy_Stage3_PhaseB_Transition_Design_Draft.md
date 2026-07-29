# ADR-016 (Draft): Legacy Stage3 Phase B — 예약변경/취소/검진완료 전이 설계

> **상태**: 🔲 **Proposed(제안 단계)** — PM 승인 없이 Accepted로 확정하지 않는다(Sprint7 Commit7-3 원칙 6 — Phase B 설계와 구현을 명확히 구분). `DECISIONS.md` 원본은 이 단계에서 수정하지 않았다.
> **작성일**: 2026-07-29(Sprint7 Commit7-3)
> **범위**: 예약변경(일정변경)/예약취소/검진완료 3개 전이를 Legacy Portal에서 Admin Portal/FastAPI 기반으로 전환하는 설계. 예약확정/거절(이미 ADR-014로 다뤄짐)과 겹치지 않는다.

---

## Context

Sprint 6 Commit6-1에서 Legacy Portal(`admin_reservations_v2_new.html`)의 "예약확정" 전이만 클라이언트측에서 차단해 TD-S5-04(Legacy 승인 우회 경로)를 부분 해소했다. 그러나 예약변경/예약취소/검진완료 3개 전이는 여전히 Legacy Portal이 전담하며, 이는 `reservation_approval_states.py`의 기존 설계 의도(모듈 Docstring: "그 외 상태(검진중/검진완료/일정변경/예약취소 등)와 그 전이는 기존 admin_reservations_v2_new.html이 계속 담당한다")와 일치하는 상태였다. Sprint7 Operation Readiness Assessment(Commit7-2)에서 이 3개 전이가 FastAPI 검증·권한 검사·감사 로그가 전무한 상태임을 실측으로 확인했고, 이번 Commit7-3에서 실제 코드(`_actionUpdateStatus`, GAS `doPost`)를 조사해 추가로 두 가지 중대한 사실을 발견했다: **GAS 쓰기 액션 자체에 인증/인가가 전혀 없다는 점**, 그리고 **예약취소 시 Slot이 반환되지 않는다는 점**이다.

## Problem

1. 예약변경/취소/검진완료는 FastAPI Policy Layer(Sprint4 Commit5-2A)를 전혀 거치지 않는다.
2. GAS `_actionUpdateStatus()`/`_actionUpdate()`는 이전 상태 검증도, 호출자 인증도 하지 않는다 — Web App URL만 알면 누구든 임의의 상태로 쓸 수 있다(코드 확인, `google_sheets_service_v2_new.js`의 기존 보안 주석에서도 이미 인지된 사실).
3. 예약취소 시 로컬 JSON Slot(`reservedCount`)이 반환되지 않아 Slot 정원이 점진적으로 왜곡될 수 있다.
4. "예약변경"은 현재 실제로 희망일시를 변경하지 않는다 — 상태 라벨만 바뀐다(Legacy 상세 모달의 `dDate`가 읽기 전용 `<span>`임을 코드로 확인).
5. 3개 전이 모두 `audit_logs.json`에 기록되지 않아 사후 추적이 불가능하다.

## Current State

- `reservation_approval_states.py`: `SHEETS_APPROVAL_TRANSITIONS = {"예약접수": {"예약확정", "거절"}}`만 정의. 다른 전이는 검증 대상 밖으로 명시적으로 제외됨.
- `routes_admin_portal.py`: `approve`/`reject` 2개 엔드포인트만 존재.
- `_actionUpdateStatus(no, status, confirmedAt)`(GAS): 이전 상태 비교 없이 `COL.예약상태`를 그대로 덮어씀. `검진완료`일 때만 `COL.검진종료`에 타임스탬프 부여, `일정변경`/`예약취소`는 부수효과 없음.
- `_actionUpdate(no, data)`(GAS): `wishDate`/`wishTime` 매핑이 이미 존재하나 Legacy Portal UI가 이를 호출하지 않음.
- `roles.json`: `reservation:change`/`reservation:cancel` 권한 문자열은 ROLE-STAFF에 이미 정의돼 있으나 어떤 엔드포인트도 검사하지 않음. `완료` 관련 권한은 존재하지 않음.

## Decision Drivers

- 기존 승인/거절 파이프라인의 재사용성(Sprint4 Commit2~5-2 패턴)
- Slot 정합성 복구(취소 시 반환)의 시급성
- 감사 가능성 확보
- 기존 운영 기능(Legacy)의 무중단 유지(핵심 원칙 1/2)
- Google Sheets SSOT 유지(핵심 원칙 3)

## Options Considered

상세 비교는 `Legacy_Stage3_PhaseB_Design_v1.0.md` §8 참조.

- **Option A**: 전이별 개별 FastAPI Endpoint(`/change`, `/cancel`, `/complete`) 추가 — 기존 approve/reject 패턴 복제
- **Option B**: 단일 `/transition` Endpoint로 통합
- **Option C**: Legacy 화면만 Admin Portal로 이식, GAS 직접 호출 유지

## Recommended Option

**Option A.** 기존 승인/거절 패턴을 그대로 재사용할 수 있고, 3개 전이가 서로 다른 권한·Policy·부수효과(Slot 반환/재배정/단순 타임스탬프)를 가지므로 개별 Endpoint가 Policy Layer/Execution Layer 분리 원칙(ADR 미부여, Sprint4 Commit5-2A에서 확립)에 더 부합한다. Option C는 근본 문제(GAS 무인증, Slot 미반환, 감사 불가)를 전혀 해결하지 못해 제외한다. 최종 확정은 PM 승인 필요 — 이 ADR은 Proposed 상태로 남는다.

## Consequences

- **긍정적**: Slot 정합성 회복(취소 시 반환), 3개 전이 전부 감사 가능해짐, RBAC 실제 적용, GAS/Sheets 스키마 무변경(기존 컬럼 재사용).
- **부정적/트레이드오프**: FastAPI에 신규 Endpoint 3개 추가로 표면적 확대, Phase B-1~B-6 완료까지 상당한 개발·검증 기간 필요, Phase B 기간 중 Admin/Legacy 두 화면이 병행돼 운영자 혼선 가능성(Risk #9).
- **해결되지 않는 것**: GAS 자체의 인증/인가 부재는 Phase B 완료 후에도 구조적으로 남는다(Web App 직접 호출 우회는 별도 과제, Risk #1) — Apps Script 자체에 토큰 검증을 추가하는 것은 "Apps Script 구조 변경"에 해당해 Sprint7 범위 밖이다.

## Risks

`Legacy_Stage3_PhaseB_Design_v1.0.md` §15 Risk Register 참조(10개 항목, Critical 2/High 4/Medium 4).

## Migration Plan

`Legacy_Stage3_PhaseB_Design_v1.0.md` §13 참조(Phase B-0~B-6, 각 Phase 개별 PM 승인 필요).

## Rollback

`Legacy_Stage3_PhaseB_Design_v1.0.md` §14 참조. B-2(취소) Rollback 시 Slot 경쟁 상태 위험을 **High Risk**로 별도 표시함.

## Open Decisions

`Legacy_Stage3_PhaseB_Design_v1.0.md` §16 Decision Required 10개 항목 참조 — 예약변경 허용 시점/횟수/당일 여부, 취소 사유 필수 여부, 검진완료 복원 가능 여부, 완료 권한 신설 여부, Slot 반환/재배정 규칙, 변경 이력 보존 기간, 감사 로그 저장 위치, 운영자 실인증 방식. **어느 것도 이 ADR에서 확정하지 않는다.**

## Approval Gate

- 이 ADR을 Accepted로 승격하려면 PM이 §Open Decisions 최소 항목 8·9(Sheets 컬럼/감사 로그 위치)를 결정해야 한다.
- Phase B-1 착수는 이 ADR의 Accepted 승격과 별개로, 자체 PM 승인이 추가로 필요하다(문서 승인 ≠ 구현 승인).

## 상태

Proposed. Sprint7 Commit7-3에서 초안 작성. Push/Deploy 없음, 구현 없음.
