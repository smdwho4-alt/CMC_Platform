# Sprint8 Security Architecture Design

> **상태**: 설계 통합문서(Draft). 코드 구현 없음, 정책 확정 없음(DEFERRED 8건은 미확정 상태 그대로 유지), PoC·부하검증 결과 반영 없음. Commit(Git 반영) 없음 — 이 문서는 작성 시점까지 작업트리 산출물일 뿐이다.
> **작성일**: 2026-08-02(Sprint8 Commit8-3a STEP 3-B)
> **기준선**: `main`/`origin/main` = `e792e41280a02e9e8c0e2522bb1e1973f2082817`
> **목적**: Commit8-3a의 잔여 설계문서 4종(Admin Operations API Contract / State Transition Matrix / RBAC Permission Matrix / Security Test and Deployment Gate Plan)이 공유할 상위 보안 아키텍처 원칙을 하나의 문서로 통합한다. 이 문서는 정책 미결정 사항(DEFERRED 8건)과 PoC·부하검증 결과에 의존하지 않는 범위에서만 작성되었다.

---

## 1. 문서 목적

`ADR-016`(Legacy Stage3 Phase B, 관리자 업무 전환 규칙)과 `ADR-017`(FastAPI Proxy and Signed GAS Operations, 전송·인증 보안 계약)에서 각각 확정한 결정을 하나의 그림으로 통합해, 이후 작성될 잔여 설계문서 4종(§10)이 참조할 공통 기준을 제공한다. 이 문서 자체는 새로운 결정을 내리지 않으며, 두 ADR과 `docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md`(Commit8-0 실행계획)에 이미 존재하는 결정만 인용·정리한다.

## 2. 적용 범위와 제외 범위

**적용 범위**: 관리자 브라우저-FastAPI-GAS-Google Sheets 경로의 인증·인가·전송보안·감사·상태전이 보호 구조 전반. 공개 예약 등록(`create`) 경로의 신뢰 경계.

**제외 범위**:
- Legacy Portal 3개 전이의 구체적 업무 규칙 값(허용 시점/횟수 등, DEFERRED — companion#1~3) — ADR-016 범위
- HMAC 실제 구현 코드, GAS 서명검증 코드 — Commit8-3b 범위
- 관리자 4개 Operation의 실제 구현, `reservedCount` 결함 수정 — Commit8-3d 범위
- Netlify 공개 배포 경계 자체의 재설계 — Commit8-2d/8-2e 범위(완료됨, 이 문서는 결과만 인용)
- Google Sheets 스키마 변경(대상 없음 — 기존 컬럼 재사용 원칙 유지)

## 3. 기준 ADR 및 추적성

| 출처 | 문서 | 역할 |
|---|---|---|
| ADR-011 | `DECISIONS.md` L98-107 | 구조 Freeze(신규 파일 추가는 조건부 허용) |
| ADR-013 | `DECISIONS.md` L120-127 | Google Sheets = Reservation SSOT |
| ADR-016 | `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md`(Proposed) | 관리자 3개 전이(변경/취소/완료) 업무 규칙 전환 |
| ADR-016 companion | `Legacy_Stage3_PhaseB_Design_v1.0.md` | ADR-016의 상세 설계 및 Open Decisions 10건 |
| ADR-017 | `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md`(Accepted with Conditions) | FastAPI Proxy·HMAC·Nonce·Idempotency 전송보안 계약 |
| 실행계획 | `docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md` | Commit8-0 시점 원래 Commit8-3/8-4 정의, Decision ID **D6~D9, D11, D27** |

**중요 — Decision ID 임의 병합 금지 확인**: `D11`(Slot 반환·재할당 정책)은 `companion#7`(Slot 반환/재배정 규칙)과 사실상 같은 주제를 다른 문서·다른 문구로 다루나, **두 ID를 병합하지 않고 각자의 출처 그대로 보존**한다. `D9`(Legacy 기능 종료·전환 시점)는 ADR-017 §24·§26(Legacy 보호조건/대체기능 완료조건)과 관련되나 동일 ID로 취급하지 않는다. `D27`(GAS Deploy 승인권자)은 ADR-017 §33(Production 금지조건)과 관련되나 별개로 유지한다. `D6/D7/D8`(GAS 직접호출 제거·검증방식·Proxy 적용범위)은 ADR-017 §11-12(대안 A 채택, HMAC-SHA256)로 사실상 답변되었으나, **실행계획 문서 자체의 D6/D7/D8 상태(미확정)를 이 문서가 대신 확정하지 않는다** — 이는 별도 STEP에서 실행계획 문서를 갱신하거나 ADR-017을 명시적으로 참조 처리해야 할 사항으로 남긴다.

## 4. 현재 시스템 AS-IS 보안 구조

- 관리자 브라우저(Legacy Portal `admin_reservations_v2_new.html`, 구버전 Dashboard 일부)가 GAS Web App URL을 **직접 호출**하며, GAS `doGet`/`doPost`는 action 문자열만으로 분기하고 호출자 인증·인가가 없다(Security Gate STEP1 확정사실, ADR-017 §7).
- Admin Portal(`admin_portal_new.html`)은 FastAPI 세션+CSRF+RBAC로 보호되며, 승인/거절만 서버측에서 GAS(`sheets_write_service.py`)를 대리 호출한다(코드 확인).
- FastAPI-GAS 서버간 호출은 `CSHSP_GAS_WEBAPP_URL` 환경변수(=URL 자체)만이 유일한 자격증명이며, GAS는 이 호출의 출처를 검증하지 못한다(ADR-017 §7-3).
- GAS 플랫폼 자체 제약(공식 확인): 커스텀 HTTP 헤더 미지원, CacheService 비영속(1,000항목 상한), PropertiesService(9KB/값·500KB/전체), 실행시간 6분 상한, 동시실행 1,000 상한(ADR-017 §7-4, 출처 §10 인용).
- 공개 예약 등록(`reservation_v3_new.html`, action=`create`)은 의도적으로 무인증이나, 같은 GAS URL로 `list`/`get`/`update`/`updateStatus`까지 함께 노출된다(Security Gate STEP1 V1/V2/V4/V5).

## 5. 목표 TO-BE 보안 구조

```
[관리자]
관리자 브라우저 → FastAPI Admin Portal(세션·CSRF·RBAC)
  → 관리자 업무 Service → HMAC-SHA256 서명(Nonce+Timestamp+Idempotency Key)
  → 서명검증하는 GAS 관리자 API → Google Sheets

[수검자]
수검자 브라우저 → 공개 예약 create(서명 없음, 의도된 설계) → GAS → Google Sheets
```

관리자 브라우저는 어떤 경우에도 GAS URL이나 HMAC Secret을 직접 보유·호출하지 않는다(ADR-017 §12 원칙). 이 목표 구조의 인증·서명 계약은 ADR-017에서 이미 확정되었다(§13-18). **이 문서는 그 확정 내용을 재인용할 뿐 새로 정의하지 않는다.**

## 6. 신뢰 경계와 주요 데이터 흐름

| Trust Boundary | 경계 위치 | 현재 통제(AS-IS) | 목표 통제(TO-BE) |
|---|---|---|---|
| TB1: 수검자 브라우저 ↔ GAS | 공개 인터넷 | 없음(의도됨, `create`만) | 변경 없음(ADR-017 §25 보호조건) |
| TB2: 관리자 브라우저 ↔ FastAPI | 공개 인터넷(로그인 필요) | 세션+CSRF(Admin Portal만), Legacy Portal은 없음 | Legacy Portal도 궁극적으로 FastAPI 경유(ADR-016, Commit8-3d 이후) |
| TB3: 관리자 브라우저 ↔ GAS 직접 | 공개 인터넷 | **현재 존재(Legacy Portal, 무인증)** | **제거 목표**(Commit8-2e, 대체기능 완료 후 — ADR-017 §24) |
| TB4: FastAPI ↔ GAS | 서버간 | URL만(자격증명 아님) | HMAC-SHA256 서명(ADR-017 §12-18) |
| TB5: GAS ↔ Google Sheets | GAS 실행 컨텍스트 | GAS 자체 권한(Google 계정), LockService 직렬화 | 변경 없음(Sprint8 범위 밖, Threat Model §12 인용) |

## 7. 인증 구조

- **관리자**: FastAPI 세션 기반(Sprint8 Commit8-2 기 구현, Argon2id/SQLite 세션store — 코드 기 존재 사실). 이 문서는 그 위에 **HMAC-SHA256 서버간 인증**을 추가한다(ADR-017 §12, Canonical String 정의 인용).
- **수검자**: 인증 없음(의도된 설계, ADR-017 §25).
- **서버간(FastAPI→GAS)**: HMAC-SHA256, `keyId` 기반 키 상태모델(`ACTIVE`/`GRACE`/`REVOKED`/`RETIRED`, ADR-017 §9/§15).

## 8. 인가 및 RBAC 기본 구조

- 기존 역할: `ROLE-DIRECTOR`/`ROLE-ADMIN`/`ROLE-STAFF`/`ROLE-CRM`/`ROLE-AI-AGENT`(`data/roles.json`, 이전 STEP에서 확인, PII 없음).
- 신설 예정(**미구현**, ADR-017 §20): `reservation:complete`, `reservation:note` — 이 문서 작성 시점에도 `data/roles.json`에 반영되지 않은 상태.
- 재사용 예정: `reservation:cancel`, `reservation:change`(이미 `data/roles.json`에 정의되어 있으나 현재 어떤 라우트도 검사하지 않음 — Commit8-2e STEP1 확인).
- **담당 부서(STEP1§24-3) 미확정** — 완전한 RBAC Permission Matrix(§10 잔여문서)는 이 결정 없이 완성될 수 없음. **DEFERRED**.

## 9. 관리자 작업 통제 구조

관리자의 상태변경(쓰기) 작업은 다음을 모두 통과해야 한다(ADR-017 §11 요약 인용):
1. FastAPI 세션 인증 + CSRF
2. RBAC 권한 검사
3. HMAC 서명 검증(GAS 측)
4. Timestamp 허용범위(±120초, ADR-017 §7 인용)
5. Nonce 재사용 검사
6. Idempotency 충돌 검사
7. 상태전이 검증(§10 참조)
8. LockService 임계구역 내 쓰기(ADR-017 §11 요구사항 인용, 3단계 임계구역 구조)

**클라이언트가 임의의 GAS action, 열 번호, 시트명 또는 필드 목록을 지정할 수 없다** — 서버측(FastAPI 서비스 계층)이 항상 화이트리스트로 필드를 고정한다(원칙 재확인).

## 10. 예약 상태 전이 보호 구조

현재 코드로 확인된 상태값 6종: `예약접수/예약확정/검진완료/일정변경/예약취소/거절`. GAS `_actionUpdateStatus`는 현재 이전 상태를 검증하지 않음(AS-IS, ADR-016 companion §5-1 항목4 인용). TO-BE는 서버측(FastAPI) 상태전이 화이트리스트를 전제로 한다.

- **취소 사유**: 필수(ADR-017 §21 확정)
- **검진완료→취소·복원**: 불가(ADR-017 §21 확정, 종결상태)
- **예약변경**: 상태 라벨이 아니라 실제 일정변경을 의미하도록 재정의(ADR-017 §22 원칙 인용) — 단 **허용 시점/횟수/당일여부는 DEFERRED**(companion#1~3, STEP1§24-1)
- **Slot 반환**: 취소 시 반환을 원칙으로 채택(ADR-017 §22 확정) — **세부규칙(즉시/유예/재배정 알고리즘)은 DEFERRED**(companion#7, D11과 관련성만 표시)
- **`reservedCount` 정합성 결함**: 이 문서에서 다루지 않으며 **Commit8-3d 범위**(ADR-017 §22 명시 재인용)

## 11. Admin Operations API 보안 원칙

후속 문서(Admin Operations API Contract, §10 참조)가 구체화할 Operation(승인/거절/일정변경/취소/검진완료/메모저장/조회)은 다음 불변조건을 지켜야 한다:
- 모든 쓰기 Operation은 HMAC 서명 필수(조회 계열은 예외, §14)
- Operation ID → GAS action의 매핑은 서버측 고정(클라이언트 미지정)
- 각 Operation은 §8의 RBAC 권한 중 하나 이상을 요구
- 응답 계약은 `protocolVersion`/`requestId`/`operation`/`ok`/`code`/`retryable`을 포함(ADR-017 §12 필드 정의 인용)
- HTTP 성공(200)과 업무 성공을 분리 판정(GAS는 전송계층에서 오류 상황을 항상 200으로만 반환한다고 공식 문서가 보장하지 않으므로 이 가정에 의존하지 않음, ADR-017 §3/§7-4 근거 재인용)

## 12. 입력 검증과 서버 측 검증

- 공개 예약(`create`): `name`/`birth`/`phone`/`gender`/`program`/`wishDate`/`wishTime`/`sleep`/`optionalTests`/`company`/`route`/`note`만 수신, 관리자 전용 필드(상태/비용/결과 등)는 스키마에 정의하지 않음(`extra` 거부 원칙).
- 관리자 Operation: Operation별 화이트리스트 필드만 GAS에 전달(§9).
- **클라이언트 측 검사만으로 보안을 충족한다고 간주하지 않는다**(작성 원칙 재확인) — 모든 검증은 서버측(FastAPI 또는 GAS 서명검증)에서 재수행되어야 한다.

## 13. 세션·토큰·Secret 관리 원칙

- HMAC Secret: FastAPI는 서버 환경변수, GAS는 `PropertiesService.getScriptProperties()`(ADR-017 §9·§14 확정 재인용).
- 소스코드에 Secret 하드코딩 금지(기존 세션 전체 원칙, Commit8-2c에서 이미 `tools/settings_new.ps1` 사례로 확인·정정된 바 있음).
- Key Rotation: `ACTIVE`+`GRACE`(48시간, ADR-017 §15 확정) 병존, 회전 순서는 "GAS 먼저, FastAPI 나중"(ADR-017 §9 원칙 재인용).
- 관리자 세션 쿠키는 Sprint8 Commit8-2 기존 구조(HttpOnly/Secure/SameSite=Lax) 유지, 이 문서는 재정의하지 않는다.

## 14. 개인정보 최소처리 및 로그 마스킹

- 조회 응답은 기존 `pii_mask.py`(`build_masked_reservation`)로 마스킹된 상태로만 반환(코드 기 존재 사실, 재확인).
- 감사로그·Nonce 로그에 성명·생년월일·연락처 원문, Secret 원문, 서명 원문을 기록하지 않는다(ADR-017 §19 확정 재인용, Nonce는 지문(앞 8자)만).
- 조회계열(HMAC 미적용, ADR-017 §18)이라도 FastAPI 세션+RBAC로 보호되는 전제가 유지되어야 이 원칙이 성립한다(전제 조건, ADR-017 §18 명시).

## 15. 감사로그와 추적성

- 저장 위치: `data_dir / "audit_logs.json"`(append-only), 함수: `src/reservation/reservation_audit.py::append_audit()`(**기존 코드, 재사용 대상**, ADR-017 §19 확인된 정확한 경로 재인용).
- 신규 이벤트 타입(`NONCE_ISSUED`/`NONCE_REPLAYED`/`HMAC_VERIFICATION_FAILED`/`TIMESTAMP_EXPIRED`/`IDEMPOTENCY_CONFLICT` 등)은 **Commit8-3b에서 구현 예정이며 현재 미구현**(ADR-017 §19 명시, 구현 완료로 오인하지 않도록 이 문서에서도 동일하게 표시).

## 16. 오류처리와 정보노출 방지

- 오류 응답은 일반화된 `message`만 클라이언트에 노출, 상세 사유는 내부 로그(`error` 필드, 클라이언트 미노출)에만 기록(ADR-017 §12 응답계약 원칙 재인용).
- 서명 검증 실패는 사유 불문 동일한 `AUTH_FAILED`류 응답으로 통일(Oracle 공격 방지 원칙, ADR-017 §12 인용).

## 17. Rate Limit·재시도·중복요청 통제 기본 원칙

- 재시도 최대 3회, 지수 백오프+Jitter(ADR-017 §16 확정 재인용).
- Idempotency Key로 중복 실행 방지, 상태별 TTL(60초/900초/300초/900초/48시간, ADR-017 §14 확정 재인용).
- Rate Limit 구체값(IP당/전화번호당 등)은 **DEFERRED**(STEP1§24-4, 실측 트래픽 데이터 부재).
- GAS 자체 쿼터(동시실행 1,000/스크립트, 공식 확인)를 초과하지 않도록 FastAPI 계층에서 통제하는 것을 목표로 하나, 구체 임계치는 이 문서에서 확정하지 않는다.

## 18. Netlify·GAS·Google Sheets 경계

- **Netlify**: 공개 정적 게시 경계는 Commit8-2d(Allowlist 도입)로 이미 완료됨(별도 커밋 `d1060ad`, `af29624`와 무관한 이전 작업, 이 문서 범위 밖). Legacy Portal의 Netlify 공개 제외(Commit8-2e)는 관리자 대체기능 완료 후로 계속 보류 상태(ADR-017 §24).
- **GAS**: 이 문서는 GAS 코드를 수정하지 않는다. GAS 신규버전 배포는 별도 승인 대상(D27, ADR-017 §33)이며 항상 "새 버전"으로 배포해야 한다(과거 STEP1.5 DateFix 미반영 사고 이력 — `PROJECT_STATUS.md` 인용).
- **Google Sheets**: SSOT(ADR-013)이며 스키마 변경 없음(기존 컬럼 재사용 원칙).

## 19. 개발·검증·운영 환경 분리

- `CSHSP_ENV`(development/staging/production) + `CSHSP_ALLOW_MOCK_AUTH`로 Mock 인증을 환경별 통제(Sprint8 Commit8-2 기존 구조, 재확인만).
- Production 배포는 Netlify Auto Publishing Locked 상태를 유지하며(현재 상태), 별도 Gate C6 승인 전까지 해제하지 않는다(ADR-017 §33 재인용).

## 20. 배포 전 보안 Gate 기본 구조

Commit8-3a STEP2-C/2-D의 Gate C1~C6 정의를 그대로 인용한다(ADR-017 §32에서 계승 명시). 이 문서는 Gate 조건을 재정의하지 않으며, §23의 미결정사항이 각 Gate의 미충족 사유로 그대로 대응된다.

**Pre-Implementation Harness와 Integrated Implementation 구분(PM 결정, Commit8-3a STEP3-G)**: ADR-017 §29가 정의하는 Commit8-3b 착수 전 사전 Gate는 **Pre-Implementation Harness(격리된 최소 harness, Commit8-3b Production 코드와 별개 산출물)를 통한 Preliminary Validation**을 가리키며, Commit8-3b Production 코드 자체의 완성을 의미하지 않는다. 통합 구현(Commit8-3b) 완료 후에는 `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md`의 G6에서 실제 코드 기준의 **Final G6 Validation**을 별도로 수행해야 한다. 이 문서는 이 두 Gate의 구분만 명시하며, 각 Gate의 상세 절차·Pass 기준은 재정의하지 않는다(ADR-017 §29, Security Test and Deployment Gate Plan §32/§40 참조).

## 21. 위협·통제·검증 매핑표

| 위협(Security Gate STEP1/Threat Model 근거) | 통제 | 통제 상태 | 검증 방법 |
|---|---|---|---|
| 무인증 전체 PII 조회(V1) | Legacy Portal 공개 제외(궁극) + Admin Portal 세션+마스킹(현재) | 부분 완료(Admin Portal), Legacy는 DEFERRED(대체기능 후) | Deploy Preview 404 확인(Commit8-2e 시점) |
| 무인증 임의 쓰기(V2/V4) | HMAC 서명(§9) | **설계완료, PoC 미완료**(DR-B-01) | Commit8-3b PoC 3건 |
| CSRF성 Blind Write(V5) | HMAC 서명(URL만으로는 위조 불가) | 설계완료, 구현전 | Commit8-3b |
| GAS 직접호출(T13/T14, Threat Model) | FastAPI Proxy 일원화 | 설계완료(ADR-017), 구현전 | Commit8-3b/8-3d |
| Replay(T09) | Nonce+Timestamp | 설계완료, **PoC 필요**(DR-B-01) | Commit8-3b PoC 3건 |
| 중복 처리 | Idempotency Key | 설계완료, **부하검증 필요**(DR-B-02) | Commit8-3b 부하검증 |
| Slot 정합성 붕괴(companion#7/D11/ADR-016 Risk#3) | Slot 반환 원칙 | 원칙확정, 세부규칙 **DEFERRED** | Commit8-3d |

## 22. 후속 설계문서와의 인터페이스

| 후속 문서 | 필요 입력자료 | 지켜야 할 불변조건 | 관련 ADR | 정책결정 필요 | PoC/부하검증 의존 | 검증기준 | Commit8-3b/8-3d 경계 |
|---|---|---|---|---|---|---|---|
| Admin Operations API Contract | §9·§11(이 문서), STEP1 §10 초안 | Operation ID→GAS action 서버 고정, 필드 화이트리스트 | ADR-017 §12·§20-22 | 일부(완료권한 담당부서 등, §8) | 아니오(계약 정의 자체는 무관) | 각 Operation 스키마·응답계약 완전성 | Commit8-3b(HMAC 틀)/8-3d(실제 구현) 경계 명시 |
| State Transition Matrix | §10(이 문서), companion §6 | 모든 전이는 서버 검증 전제, 라벨≠일정변경 구분 유지 | ADR-016, ADR-017 §21-23 | **예**(companion#1-3, STEP1§24-1) | 아니오 | 상태값 6종 전이 완전성 | Commit8-3d |
| RBAC Permission Matrix | §8(이 문서), `data/roles.json` | 신설 권한과 기존 권한 구분(구현완료로 오인 금지) | ADR-017 §20 | **예**(STEP1§24-3) | 아니오 | 역할×Operation 매트릭스 완전성 | Commit8-3d |
| Security Test and Deployment Gate Plan | §21(이 문서), STEP2-B §14(30개 장애시나리오) | Fail-closed 원칙, 불확실 성공상태 자동재시도 금지 | ADR-017 전체 | 아니오(테스트 계획 자체는 무관) | **예**(DR-B-01/02 결과가 있어야 "완료" 판정 가능) | 30개 시나리오 커버리지 | Commit8-3b/8-3d 공통 |

## 23. DEFERRED·PoC·부하검증 의존항목

**DEFERRED 8건(정책결정, ADR-017 §30 원문 그대로 인용 — 이 문서에서 확정하지 않음)**: companion#1(변경시점)/#2(변경횟수)/#3(당일변경)/#8(보존기간)/#10(운영자실인증), STEP1§24-1(RESCHEDULED상태)/§24-3(담당부서)/§24-4(RateLimit).

**DR-B-01 PoC 3건(기술검증, ADR-017 §29 원문 그대로 인용)**: (1) FastAPI SQLite UNIQUE 제약의 동시요청 원자성 실측, (2) GAS CacheService eviction 빈도 시뮬레이션, (3) 양쪽 저장소 정합성 불일치 시나리오 처리 검증. 3건 전부 **Pre-Implementation Harness(Commit8-3b Production 코드와 별개)** 로 수행하며, 항목(2)는 GAS를 실제 사용하므로 **별도 PM 승인과 격리된 테스트 환경(운영 GAS·Google Sheets 미사용) 확보 전에는 착수하지 않는다**(PM 명시 조건, ADR-017 §29 재인용).

**DR-B-02 부하검증(성능검증, ADR-017 §29 원문 그대로 인용)**: Idempotency TTL 5개값에 대한 실측 트래픽/재시도 패턴 기반 부하검증. **2단계로 구분한다**(PM 결정, ADR-017 §29 재인용): **Phase 1(Preliminary Validation)** — Pre-Implementation Harness 기반 예비 부하검증, 결과는 TTL·저장방식·동시성 설계의 잠정 선택 근거일 뿐 Production 적합성을 보증하지 않음. **Phase 2(Final G6 Validation)** — Commit8-3b 통합 구현 완료 후 G6에서 실제 코드 기준으로 최종 재검증, 최종 TTL 확정은 Phase 2 결과로만 이루어짐. Phase 1 결과가 Phase 2나 배포 승인을 대체하지 않는다.

이 세 범위는 혼합하지 않았으며, 각각 `TBD`(정책)/`PoC required`(기술)/`Load test required`(성능)로 후속 문서에서 표기할 것을 권고한다.

## 24. 미결정사항 및 Open Questions

- D6/D7/D8(실행계획 문서)의 상태 자체를 ADR-017 결정으로 갱신할지 여부(§3에서 지적) — **Open Question, 이 문서에서 결정하지 않음**
- D9(Legacy 종료·전환 시점)와 ADR-017 §26(대체기능 완료조건)의 구체적 판정 기준 합치 여부 — Open Question
- D11과 companion#7의 관계를 향후 어느 시점에 하나의 결정으로 정리할지 — Open Question(§13 STEP3-A에서 이미 PM 결정 필요사항으로 보고됨)

## 25. Commit8-3b·8-3d와의 경계

이 문서는 **문서 작성만**이며 코드 구현을 포함하지 않는다. Commit8-3b(HMAC/Nonce/Idempotency/Grace/재시도/감사연계 실제 구현, PoC·부하검증 선행)와 Commit8-3d(예약변경·취소·완료 Operation 구현, `reservation:complete`/`reservation:note` 권한 구현, Slot 반환, `reservedCount` 수정)의 범위를 침범하지 않는다(ADR-017 §31 이관표 재인용).

## 26. 완료 기준

이 문서는 다음을 모두 충족하면 "작성 완료"로 간주하되, **문서 승인 자체가 Commit8-3b/8-3d 착수 승인을 의미하지 않는다**:
- 26개 섹션 전부 작성됨
- ADR-016/017/실행계획(D6-D9/D11/D27)과의 추적성이 명시됨
- DEFERRED 8건이 미확정 상태로 표시됨
- PoC 3건·부하검증 결과가 추정되지 않음
- 개인정보·Secret·운영 URL 원문이 포함되지 않음
- 구현 완료로 오인될 문구가 없음

---

**완료 조건 준수 확인**: 이 문서 작성 중 ADR-016·ADR-017을 포함한 어떤 기존 파일도 수정하지 않았다. 코드 구현 없음. DEFERRED 8건 미확정 유지. PoC·부하검증 결과 추정 없음. 실제 Secret·서명·Nonce·운영 URL·개인정보 미포함. Git add/commit/push 없음.
