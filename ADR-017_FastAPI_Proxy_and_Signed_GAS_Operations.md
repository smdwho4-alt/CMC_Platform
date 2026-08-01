# ADR-017: FastAPI Proxy and Signed GAS Operations

> **상태**: 🟡 **Accepted with Conditions** — 핵심 아키텍처 결정(대안 A: FastAPI Proxy + HMAC-SHA256 서명)은 확정되었으나, 아래 §29(구현 전 검증조건)의 PoC·부하검증과 §30(DEFERRED 8건)의 병원 운영정책이 해소되기 전에는 Commit8-3b/8-3d 구현에 착수하지 않는다. `DECISIONS.md` 원본은 이 단계에서 수정하지 않았다.
> **작성일**: 2026-08-02(Sprint8 Commit8-3a STEP 2-D)
> **범위**: 관리자 브라우저의 GAS Web App 직접호출을 FastAPI Proxy로 일원화하고, FastAPI-GAS 서버간 쓰기 호출에 HMAC-SHA256 서명·Timestamp·Nonce·Idempotency 통제를 적용하는 전송·인증 계층 설계를 다룬다. Legacy Portal 3개 전이(예약변경/예약취소/검진완료)의 **업무 규칙**(허용 시점, 횟수, 상태 라벨 등)은 ADR-016(Legacy Stage3 Phase B)이 다루며, 이 ADR은 그 업무 규칙이 어떤 **보안 계약**을 통해 GAS에 도달하는지만 다룬다. 두 ADR은 서로를 대체하지 않고 상호 참조한다(§10).

---

## 1. 제목

ADR-017 — FastAPI Proxy and Signed GAS Operations

## 2. 상태

**Accepted with Conditions**(§29·§30의 조건이 모두 충족되기 전에는 Commit8-3b/8-3d 구현에 착수하지 않는다)

## 3. 결정일

2026-08-02(초안 작성). 최종 발효는 PM의 문서 승인 시점.

## 4. 승인 주체

PM(최종 승인). 개발팀(기술 설계, 이 문서 초안 작성).

## 5. 관련 Commit 및 작업단계

Sprint8 Security Gate STEP1 → Commit8-2e STEP1(영향도 분석) → Commit8-3a STEP1(보안 아키텍처 설계) → STEP2-A(기준선·ADR 충돌 확인) → STEP2-B(HMAC/Nonce/Idempotency 상세 설계, 보완 재수행 CONDITIONAL PASS) → STEP2-C(통합 결정관리, CONDITIONAL PASS) → **STEP2-D(본 문서, ADR-017 확정)**. 후속: Commit8-3b(HMAC 구현), Commit8-3c(공개 create 분리), Commit8-3d(관리자 4기능+reservedCount 수정), Commit8-3e(상태전이 화이트리스트+보안회귀), Commit8-2e(Legacy Portal 공개 제외, 대체기능 검증 후).

## 6. 배경

Security Gate STEP1에서 GAS Web App(`app/apps_script/sheets_api_v3_final.gs`)의 `doGet`/`doPost`가 호출자 인증·인가 없이 action 문자열만으로 분기함이 코드로 확인되었다(V1: 무인증 전체 PII 조회, V2/V4: 무인증 임의 쓰기, V5: CSRF성 Blind Write — 전부 Critical). 이는 이 세션 이전부터 Threat Model(T13/T14)과 ADR-016 companion 문서(`Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1 항목2)에서도 독립적으로 확인된 사실이다. PM은 이 문제를 두 축으로 분리하기로 결정했다(Commit8-3a STEP2-A 검토결과): **ADR-016**은 "무엇을 할 수 있어야 하는가"(관리자 업무 기능 전환), **ADR-017**(이 문서)은 "어떻게 안전하게 전달하는가"(전송·인증 보안)를 각각 담당한다.

## 7. 문제 정의

1. 관리자 브라우저(Legacy Portal `admin_reservations_v2_new.html`, 구버전 Dashboard)가 GAS Web App URL을 직접 호출하며, GAS는 호출자가 관리자 브라우저인지 제3자인지 구분하지 못한다.
2. GAS Web App은 커스텀 HTTP 요청 헤더를 지원하지 않는다(Google 공식 확인, 2023-09-19 의도적 결정 — §10 출처).
3. FastAPI-GAS 서버간 호출(`sheets_readonly_service.py`/`sheets_write_service.py`)도 `CSHSP_GAS_WEBAPP_URL` 환경변수(=URL 자체)만이 유일한 "자격증명"이며, GAS 측은 이 호출이 실제로 FastAPI로부터 온 것인지 검증할 수단이 없다.
4. GAS 플랫폼은 CacheService(비영속, 1,000항목 상한), PropertiesService(9KB/값, 500KB/전체), LockService(원자적 배타 락이나 waitLock 타임아웃 존재), 6분 실행시간 상한, 1,000 동시실행 상한이라는 구조적 제약을 가진다(Google 공식 확인 — §10).
5. 이종 시스템(FastAPI-GAS-Google Sheets) 간 완전한 분산 트랜잭션은 구조적으로 불가능하다(요구사항 원칙9, ADR-016 companion §5-1도 동일하게 인정).

## 8. 적용 범위

- FastAPI가 GAS의 상태변경(쓰기) action(`create` 제외 — 아래 §18)을 호출하는 모든 서버간 요청의 서명·검증 계약
- Nonce/Timestamp/Idempotency Key를 이용한 Replay 방지 및 중복처리 방지
- HMAC Secret의 저장·회전·폐기 수명주기
- 응답 계약(정상/오류)과 GAS 플랫폼 제약을 반영한 실패 처리 원칙

## 9. 제외 범위

- Legacy Portal 3개 전이의 구체적 업무 규칙(허용 시점, 횟수 등) — **ADR-016 범위**
- GAS 소스코드의 실제 수정(이번 STEP은 설계 문서만, GAS 코드 변경은 Commit8-3b 이후)
- Netlify 공개 배포 경계(Commit8-2d/8-2e 범위, 이 ADR과 독립)
- Google Sheets 스키마 변경(적용하지 않음 — 기존 컬럼 재사용 원칙 유지)

## 10. 선행 문서와 출처

- `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md`(Proposed, 78줄)
- `Legacy_Stage3_PhaseB_Design_v1.0.md`(ADR-016 companion, 389줄, §16 Open Decisions 10건)
- `DECISIONS.md` ADR-011(구조 Freeze, L98-107), ADR-013(Sheets=SSOT, L120-127)
- Sprint8 Threat Model(`docs/Sprint8_Admin_Authentication_Authorization_Design_and_Threat_Model.md`, T09/T13/T14, §35)
- Google 공식 문서: [Web Apps](https://developers.google.com/apps-script/guides/web), [커스텀헤더 미지원 공지](https://groups.google.com/g/google-apps-script-community/c/bgnzoAUV_No), [Cache](https://developers.google.com/apps-script/reference/cache/cache), [Apps Script Quotas](https://developers.google.com/apps-script/guides/services/quotas), [LockService](https://developers.google.com/apps-script/reference/lock/lock-service), [Utilities](https://developers.google.com/apps-script/reference/utilities/utilities)
- 이 세션의 Sprint8 Security Gate STEP1, Commit8-2e STEP1, Commit8-3a STEP1/STEP2-A/STEP2-B(보완 재수행)/STEP2-C(통합 결정관리) — 저장소 파일이 아닌 세션 산출물이나, 이 ADR의 직접 입력자료

## 11. 고려한 대안

| 대안 | 개요 | 판정 |
|---|---|---|
| A. FastAPI Proxy + HMAC Signed GAS Operations | 관리자 쓰기는 전부 FastAPI 경유, HMAC 서명 | **채택** |
| B. GAS 직접호출 유지 + 제한적 보완 | 현행 구조 유지, 부분 완화만 | 기각(근본 문제 미해결) |
| C. FastAPI가 Google Sheets API 직접 사용 | GAS 우회, Service Account 사용 | 기각(ADR-013 SSOT 경로 변경 소지, GAS의 기존 검증로직 재구현 부담) |
| D. 별도 API Gateway/Cloud Function 도입 | 신규 중계 계층 | 기각(ADR-011 구조 Freeze 취지와 배치 소지) |

(비교 상세: Commit8-3a STEP2-B §16, 15개 기준 비교표)

## 12. 채택 결정

**대안 A 채택.** 관리자 쓰기 경로(상태변경 전이 전체)는 FastAPI Proxy를 통해서만 GAS에 도달하며, 각 요청은 HMAC-SHA256으로 서명된다. GAS는 서명 검증에 성공한 요청만 Sheets에 쓴다. 공개 예약 등록(`create`)은 수검자 편의를 위해 서명 없이 계속 허용한다(§18).

**Canonical String**(서명 대상, 언어독립적 정의 — Commit8-3a STEP2-B §6):
```
CMC-HMAC-SHA256
1
<HTTP Method>
<operation>
<timestamp>
<nonce>
<idempotencyKey>
<payloadHash>
```
UTF-8, LF 구분자, 트레일링 개행 없음, JSON 키는 유니코드 코드포인트순 정렬 후 compact 직렬화, 해시는 소문자 hex, Unicode NFC 정규화. Envelope는 Canonical String 전체를 서명하며 `payload` 원문은 서명 대상에서 제외하고 `payloadHash`(SHA-256)만 포함한다(GAS 실행시간 제약과 언어 간 JSON 직렬화 불일치 위험을 동시에 회피). `Utilities.computeHmacSha256Signature()`가 GAS에서 공식 지원됨을 확인했다(§10).

## 13. Nonce 영속화 구조

**채택**: CacheService(GAS, TTL 300초, 2차 방어)와 **FastAPI 측 영속 저장소(기존 `src/auth/auth_store.py`의 SQLite 패턴을 확장 재사용, 1차 방어)의 이중 구조.** CacheService 단독 사용은 채택하지 않는다(공식 확인된 1,000항목 상한과 비영속성 때문에 Replay 차단을 단독으로 보장할 수 없음 — Commit8-3a STEP2-B §4.2/§7).

- FastAPI가 발신 전 자체 DB에 Nonce를 기록해 자신이 이미 발급한 Nonce의 재사용을 1차로 차단
- GAS CacheService는 FastAPI를 거치지 않은 직접 재요청에 대한 2차 방어
- **저장 실패 시 Fail-Closed**(양쪽 저장소 중 어느 한쪽이라도 기록에 실패하면 해당 요청을 진행하지 않음)
- 원자성: GAS측은 Nonce 존재확인~기록 구간을 LockService로 감쌈, FastAPI측은 SQLite UNIQUE 제약으로 원자성 확보(별도 Lock 불필요)
- 정리 정책: GAS Cache는 TTL 자동 만료, FastAPI DB는 배치 작업(예: 1시간 주기)으로 만료분 삭제
- 원문 Nonce는 저장소에 그대로 보관(검증 목적상 필요), 감사로그에는 앞 8자 지문만 기록(§19)
- **이 구조는 단순 메모리 저장이나 CacheService 단독 구조로 축소하지 않는다**(PM 명시 요구사항 그대로 반영)
- **§29의 PoC 3건이 완료되기 전까지 이 구조는 "구현 확정"으로 간주하지 않는다**(PM 명시 조건)

## 14. Idempotency 상태모델과 TTL

5개 상태(`IN_PROGRESS`/`SUCCEEDED`/`FAILED_RETRYABLE`/`FAILED_FINAL`/`UNKNOWN`)와 다음 TTL을 채택한다(PM 확정값, Commit8-3a STEP2-C §7 근거):

| 상태 | TTL | 비고 |
|---|---|---|
| `IN_PROGRESS` | **60초**(정체 판정 시간 — TTL 경과 후 만료삭제가 아니라 자동으로 `UNKNOWN`/`RECONCILIATION_REQUIRED`로 전이) | GAS 실행 최대 6분(§10)이지만 정상 처리는 수 초 내 완료되므로 60초 초과는 이상 신호 |
| `SUCCEEDED` | **900초** | 응답유실 후 운영자가 화면 재확인·복귀하는 현실적 시간 반영 |
| `FAILED_RETRYABLE` | **300초** | Nonce TTL과 동일하게 맞춤, 재시도는 새 Nonce로 이루어짐(§16) |
| `FAILED_FINAL` | **900초** | 동일 키 재문의 시 일관된 실패결과 반환 |
| `UNKNOWN` | **48시간** | **별도 상태로 보존**하며 자동 재실행하지 않고 조회·운영 확인 절차와 연결(야간·휴일 장애 대응 시간 감안) |

응답 유실이나 결과 확인 불능은 단순 실패(`FAILED_*`)로 처리하지 않고 `UNKNOWN`으로 명확히 구분한다(PM 명시 요구사항 그대로 반영). **§29의 부하검증이 완료되기 전까지 위 TTL은 "구현 확정값"이 아니라 "설계 확정값"으로만 간주한다.**

## 15. Grace 기간

**48시간**(Commit8-3a STEP2-C §8 DR-B-03 확정). 키 회전 시 신규 키(`ACTIVE`)와 구 키(`GRACE`)를 병존시켜 무중단 전환을 지원하며, 회전 순서는 반드시 **"GAS 먼저, FastAPI 나중"**(양쪽 배포 불일치 시나리오 완화, Commit8-3a STEP2-B §9).

## 16. 재시도 정책

**최대 3회**(Commit8-3a STEP2-C §8 DR-B-04 확정), 지수 백오프(1초→2초→4초)+Jitter(±20%), `retryable:true`로 분류된 오류코드에만 적용, 업무 오류(`VALIDATION_FAILED`/`PERMISSION_DENIED`/`INVALID_TRANSITION`/`IDEMPOTENCY_CONFLICT`)와 불확실 성공 상태(`UNKNOWN`/`RECONCILIATION_REQUIRED`)는 자동 재시도 금지, 조회·조정 절차 우선.

## 17. HMAC 적용 범위

관리자 **쓰기**(상태변경) 경로 전체(승인/거절 기존 경로 포함 여부는 §29에서 재검토 대상). 공개 예약 등록(`create`)은 서명 없이 계속 허용(§18). 조회 계열은 HMAC 미적용(§18).

## 18. 조회계열 HMAC 미적용 근거

**미적용 채택**(Commit8-3a STEP2-C §8 DR-B-05 확정). `routes_admin_portal.py::list_reservations`/`get_reservation`이 이미 `Depends(require_reservation_view)`로 FastAPI 세션 인증을 거치고 있음이 코드로 확인되었다(Commit8-3a STEP2-A). 이미 세션으로 보호되는 조회 경로에 HMAC을 추가하는 것은 이번 설계의 핵심 위협(쓰기 경로의 무인증 문제)과 무관한 범위 확대이며, 구현 복잡도 대비 보안 이득이 낮다고 판단했다. 이 전제(조회 경로가 항상 세션 인증을 거친다는 것)가 깨지지 않는 한 유효하다.

## 19. 감사로그 저장정책

**기존 구조를 재사용한다**(Commit8-3a STEP2-C §6 companion#9 확정). 실제 저장소에서 확인한 정확한 경로:
- `src/reservation/reservation_audit.py::append_audit(data_dir, action, entity_type, entity_id, actor_user_id, before, after, channel, note)` — 기존 함수(신규 구현 아님, 재사용 대상)
- 저장 위치: `data_dir / "audit_logs.json"`(append-only, 코드로 확인)

**신규로 필요한 것**(구현되지 않은 상태임을 명확히 표시): `NONCE_ISSUED`/`NONCE_REPLAYED`/`HMAC_VERIFICATION_FAILED`/`TIMESTAMP_EXPIRED`/`IDEMPOTENCY_CONFLICT` 등 이 ADR이 새로 정의하는 이벤트 타입을 `append_audit()` 호출 시 `action` 인자로 전달하는 연계 코드는 **Commit8-3b에서 구현**한다(현재 미구현, 구현완료로 표현하지 않음). Secret 원문·서명 원문·PII 원문은 어떤 로그에도 기록하지 않으며, Nonce는 지문(앞 8자)만 기록한다.

## 20. 권한 정책

**신설**: `reservation:complete`(검진완료), `reservation:note`(메모 저장) — `data/roles.json`에 아직 존재하지 않는 권한 문자열이며, **이 문서 승인만으로 저장소에 반영되지 않는다. Commit8-3d에서 `data/roles.json` 및 관련 `_build_require_permission()` 호출부에 실제로 추가되어야 비로소 구현 완료**로 간주한다(PM 명시 요구사항: 신설 예정과 구현 완료를 정확히 구분).

**재사용**: `reservation:cancel`, `reservation:change` — `data/roles.json`에 ROLE-STAFF 권한으로 이미 정의되어 있으나 현재 어떤 라우트도 검사하지 않는 상태(코드 확인, Commit8-2e STEP1). Commit8-3d에서 실제 라우트에 연결되어야 Enforcement가 시작된다.

## 21. 취소 및 검진완료 상태정책

- **취소 사유: 필수**(PM 확정, companion#4)
- **검진완료 상태의 취소·복원: 불가**(PM 확정, companion#5 — 종결 상태, 감사 무결성 우선)
- 두 정책 모두 **오류코드 스키마(`RESERVATION_REASON_REQUIRED`, `ALREADY_COMPLETED` 등, Commit8-3a STEP2-B §12)에는 반영되어 있으나 실제 코드는 Commit8-3d에서 구현**한다

## 22. Slot 반환 원칙

**취소 시 Slot `reservedCount` 반환을 원칙으로 채택한다**(PM 확정). 단, **즉시 반환/유예/재배정 알고리즘의 세부 규칙은 Commit8-3d 착수 전에 별도 확정**해야 하며(PM 명시 조건, companion#7의 미해소 부분), 이 ADR은 그 세부 규칙을 확정하지 않는다. **`reservedCount` 정합성 결함(취소 시 미반환, ADR-016 companion §5-1 항목3/§15 Risk#3 Critical) 수정은 이 문서에서 수행하지 않으며 Commit8-3d 범위로 명확히 유지한다.**

## 23. 불확실 성공 상태 처리

`UNKNOWN`/`RECONCILIATION_REQUIRED`는 자동 재실행을 절대 금지하고, 운영자의 Sheets 직접 확인 후 수동으로 `SUCCEEDED` 또는 `FAILED_FINAL`로 전이시킨다(§14). 이는 FastAPI-GAS-Sheets 간 완전한 트랜잭션이 구조적으로 불가능하다는 전제(§7-5) 위에서, "보상(Compensation)"이 아니라 "재확인(Reconciliation)"을 원칙으로 삼은 결과다.

## 24. Legacy Portal 보호조건

**Legacy 공개 쓰기 경로(`admin_reservations_v2_new.html` 등)는 관리자 대체기능(Commit8-3d의 4개 Operation)이 완료되고 검증되기 전에는 제거하지 않는다**(PM 명시 조건). 기존 기능을 임의로 삭제하지 않는다. Commit8-2e(Netlify 공개 Allowlist 제외)는 이 조건이 충족된 이후에만 재개한다.

## 25. Reservation Portal 보호조건

수검자용 예약 등록(`reservation_v3_new.html`, `create` action)은 이 ADR로 인해 영향받지 않는다. 정상 예약 흐름을 침해하지 않으며, 공개 경로 자체를 임의로 변경하지 않는다.

## 26. 관리자 대체기능 완료조건

Commit8-3d에서 다음 4개 Operation이 전부 구현·검증되어야 "완료"로 간주한다: 예약변경(실제 일정변경, 라벨 아님), 예약취소(Slot 반환 포함), 검진완료(선행상태 CONFIRMED로 제한), 메모저장. 완료 검증은 Preview 환경에서의 기능시험과 STEP2-B §14 장애 시나리오 기반 테스트를 포함한다.

## 27. Rollback 독립성 위험

**GAS Rollback(서명검증 있는 버전 → 없는 버전으로 되돌리는 것)과 Commit8-2e Allowlist Rollback(Netlify 공개범위를 되돌리는 것)은 서로 독립적인 별개의 Rollback 경로다.** 한쪽만 Rollback하면 다른 쪽 보호가 무력화될 수 있다는 위험을 **공식으로 인정**한다(PM 확정). **구체적인 대응 정책(예: 두 Rollback을 항상 함께 검토하는 체크리스트)은 이 ADR에서 확정하지 않으며, Commit8-2e 재개 시점에 별도로 수립한다**(PM 명시 조건).

## 28. 보안·운영·정합성 영향

- **보안**: GAS 무인증 위험(V1/V2/V4/V5)의 구조적 완화 경로 확보. 단 §34의 잔여위험은 소멸하지 않는다.
- **운영**: 키 회전(48시간 Grace), Idempotency 조회 절차 등 신규 운영 부담 발생 — Runbook 이관 필요(§31).
- **정합성**: Slot `reservedCount` 결함 해소 경로 확보(Commit8-3d), 단 이 문서 자체는 수정하지 않음.

## 29. 구현 전 검증조건

Commit8-3b(HMAC/Nonce/Idempotency) 착수 전 반드시 완료해야 하는 PoC 3건(**Commit8-3a STEP2-C §6 원문 그대로, 임의로 명칭을 만들지 않음**):

1. FastAPI SQLite UNIQUE 제약이 실제 동시 요청에서 원자적으로 중복을 거부하는지 실측 검증
2. GAS CacheService의 실제 eviction 빈도를 이 시스템의 예상 트래픽 규모로 시뮬레이션
3. 양쪽 저장소 간 정합성이 어긋나는 경우(FastAPI는 신규로 판단했으나 GAS Cache에 이미 존재하는 극단적 사례)의 처리 로직 검증

그리고 §14의 Idempotency TTL·저장구조에 대한 **부하검증**(Commit8-3a STEP2-C §7: 운영자 재시도 행동 패턴에 대한 실측 데이터 부재를 명시적으로 인정, 900초/1800초/48시간은 합리적 추정치이지 실측 확정값이 아님).

## 30. DEFERRED 8건

다음 8건은 이 ADR에서 임의로 확정하지 않는다(PM 명시).

| ID | 항목 | 상태 | 확정 시점/Gate | 미확정시 차단 | 담당 주체 | ADR-017에서 미확정인 이유 |
|---|---|---|---|---|---|---|
| companion#1 | 예약변경 가능 시점 | DEFERRED | Commit8-3d(B-3 대응) 착수 전 | 예약변경 Operation 세부설계 | PM/병원운영팀 | 병원 운영정책 사안, 코드·설계로 판단 불가 |
| companion#2 | 예약변경 허용 횟수 | DEFERRED | 상동 | 상동 | PM/병원운영팀 | 상동 |
| companion#3 | 당일 예약변경 허용여부 | DEFERRED | 상동 | 상동 | PM/병원운영팀 | 상동 |
| companion#8 | 변경이력 보존기간 | DEFERRED | Commit8-3d(Sheets 컬럼설계) 착수 전 | Sheets 신규 컬럼 필요여부 확정불가 | PM/개인정보보호책임자 | 개인정보 보존정책 사안, 별도 ADR 검토 후보 |
| companion#10 | 운영자 실인증 방식 | DEFERRED | 별도 Sprint(Sprint7 원문 범위 유지) | Risk#1/#6 근본 대응 | PM/병원전산담당 | ADR-016 companion 원문이 "Sprint7 범위 밖"으로 명시, 이 세션(Sprint8)에서도 확대 해석하지 않음 |
| STEP1§24-1 | `RESCHEDULED` 상태 도입여부 | DEFERRED | Commit8-3d(B-3) 착수 전 | 상태모델 최종 확정 | PM | companion#1-3과 함께 결정되어야 하는 정책값 |
| STEP1§24-3 | 검진완료 담당부서 | DEFERRED | Commit8-3d(권한 배정) 착수 전 | 권한 매트릭스(§20) 최종 확정 | PM/병원운영팀 | 운영조직 정보, 코드로 확인 불가 |
| STEP1§24-4 | Rate Limit 구체값 | DEFERRED | Commit8-3c(공개 create 분리) 착수 전 | QUOTA_EXCEEDED 대응 설계 | PM | 실측 트래픽 데이터 부재 |

## 31. 후속 Commit 이관표

| Commit | 이관 항목 |
|---|---|
| Commit8-3a(본 문서 이후) | ADR-017 외 나머지 설계문서(Operation 인터페이스 계약 상세화 등) — **이번 STEP에서는 미승인·미작성** |
| Commit8-3b | HMAC 적용 쓰기경로 구현, Nonce 이중구조(§13) 실제 코드, Idempotency 처리(§14), Grace 기간(§15) 적용, 재시도 정책(§16) 구현, 감사로그 연계(§19 신규 이벤트타입), **PoC 3건 및 부하검증(§29) 선행** |
| Commit8-3d | 예약변경·취소·검진완료 상태전이(§21), 취소사유 필수화(§21), `reservation:complete`/`reservation:note` 권한 구현(§20), Slot 반환(§22, 세부규칙 별도확정 후), **`reservedCount` 정합성 결함 수정** |
| Commit8-2e 또는 별도 운영작업 | GAS Rollback과 Commit8-2e Rollback 독립성 위험 대응(§27), 운영 Runbook(키 회전 등), 장애대응·모니터링, Production Publish Gate(§33) |

## 32. Gate 조건

Commit8-3a STEP2-C의 Gate C1~C6 정의를 그대로 계승(§35 추적성 표에서 재연결). Commit8-3b 착수는 §29 완료가, Commit8-3d 착수는 §30 중 관련 항목 확정 및 §22 세부규칙 확정이 전제조건이다.

## 33. Production 금지조건

Netlify Auto Publishing 잠금 해제, Production Publish, GAS 신규버전 실배포, Google Sheets 운영데이터 접근은 **별도 Gate C6 승인 전까지 금지**한다. 이 문서 승인은 Production 적용을 어떤 형태로도 승인하지 않는다.

## 34. 잔여 위험

- §13 Nonce 이중구조에도 불구, "FastAPI를 거치지 않은 직접 재요청 + GAS CacheService의 정확히 그 순간 축출"이라는 좁은 창은 구조적으로 완전히 제거되지 않는다(Commit8-3a STEP2-B §4.2).
- Legacy Portal이 공개 유지되는 동안(Commit8-2e 재개 전까지) 기존 무인증 위험(V1/V2/V4/V5)은 그대로 잔존한다.
- §27의 Rollback 독립성 위험은 대응정책 수립 전까지 구조적으로 존재한다.
- §30의 DEFERRED 8건이 미확정인 동안 관련 Operation의 최종 설계는 완결되지 않는다.

## 35. 추적성 표

| Decision ID | 출처 | ADR-017 반영위치 | 최종상태 | 후속작업 | 차단Gate | 비고 |
|---|---|---|---|---|---|---|
| ADR-016(Draft) | `ADR-016_...Draft.md` | §6, §9(제외범위) | Proposed(별개 유지) | ADR-016 자체 Open Decision 해소 | - | ADR-017과 상호참조, 통합 안 함 |
| companion#1~3 | `Legacy_Stage3_PhaseB_Design_v1.0.md` §16 | §30 | DEFERRED | 정책결정 | Commit8-3d | PM/병원운영팀 |
| companion#4 | 상동 | §21 | **PM확정 반영**(필수) | Commit8-3d 구현 | Commit8-3d | - |
| companion#5 | 상동 | §21 | **PM확정 반영**(불가) | Commit8-3d 구현 | Commit8-3d | - |
| companion#6 | 상동 | §20 | **PM확정 반영**(신설) | Commit8-3d 구현 | Commit8-3d | STEP1§24-2와 통합 반영 |
| companion#7 | 상동 | §22 | **부분확정**(반환원칙만) | 세부규칙 확정 후 Commit8-3d | Commit8-3d | 세부규칙은 DEFERRED 성격 잔존 |
| companion#8 | 상동 | §30 | DEFERRED | 정책결정 | Commit8-3d | 별도ADR 후보 |
| companion#9 | 상동 | §19 | **PM확정 반영**(재사용) | 신규 이벤트타입 연계코드(Commit8-3b) | Commit8-3b | 정확한 경로 확인·기재 완료 |
| companion#10 | 상동 | §30 | DEFERRED | 별도 Sprint | 범위밖 | 원문 범위 유지 |
| STEP1§24-1 | 세션(Commit8-3a STEP1) | §30 | DEFERRED | 정책결정 | Commit8-3d | companion#1-3과 연계 |
| STEP1§24-2 | 세션(Commit8-3a STEP1) | §20 | **PM확정 반영** | Commit8-3d 구현 | Commit8-3d | companion#6과 통합 |
| STEP1§24-3 | 세션(Commit8-3a STEP1) | §30 | DEFERRED | 운영확인 | Commit8-3d | - |
| STEP1§24-4 | 세션(Commit8-3a STEP1) | §30 | DEFERRED | 실측필요 | Commit8-3c | - |
| STEP1§24-5 | 세션(Commit8-3a STEP1) | §27 | **위험인지 확정, 대응정책 DEFERRED** | 대응정책 수립 | Commit8-2e 재개시점 | - |
| STEP1§24-6 | 세션(Commit8-3a STEP1) | §4(범위 헤더) | SUPERSEDED_WITH_TRACEABILITY | 없음 | 없음 | PM STEP2-A 결정으로 대체(ADR-016/017 분리) |
| DR-B-01 | 세션(STEP2-B/2-C) | §13 | **확정(조건부)** | PoC 3건(§29) | Commit8-3b | - |
| DR-B-02 | 세션(STEP2-B/2-C) | §14 | **확정(조건부)** | 부하검증(§29) | Commit8-3b | - |
| DR-B-03 | 세션(STEP2-C) | §15 | **확정** | 없음 | Commit8-3b | 48시간 |
| DR-B-04 | 세션(STEP2-C) | §16 | **확정** | 없음 | Commit8-3b | 3회 |
| DR-B-05 | 세션(STEP2-C) | §18 | **확정** | 없음 | Commit8-3b/3c | 미적용 |
| PM 공식결정(STEP2-D 지시서) | 이 세션 사용자 메시지 | 전체 | 채택 반영 | - | - | §2.2·§2.3·§2.4 원문 그대로 반영 |

## 36. 승인 기록

| 일자 | 승인자 | 내용 |
|---|---|---|
| 2026-08-02 | (초안) | ADR-017 초안 작성(Commit8-3a STEP2-D), 상태 Accepted with Conditions로 표기 — **PM의 파일 내용 최종 확인·서명은 별도 절차** |

---

**완료 조건 준수 확인**: 이 문서 작성 중 `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md`를 포함한 어떤 기존 파일도 수정하지 않았다. Commit8-3a의 다른 설계문서, 코드, 테스트는 작성하지 않았다. Git add/commit/push, 배포, GAS/Google Sheets/Netlify 접근 없음. 실제 Secret·서명·Nonce·운영 URL·개인정보를 포함하지 않았다.
