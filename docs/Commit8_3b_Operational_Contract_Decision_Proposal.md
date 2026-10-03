# Commit8-3b — 운영 통합 계약 결정안(제안)

> **상태**: **결정 제안서(Proposal)다. ADR 승인·SSOT 갱신·운영 코드 변경을 수행하지 않았다.**
> 이 문서가 제시하는 권고안은 PM/아키텍처 승인 전까지 운영 계약으로 간주하지 않는다.
> **작성 기준 HEAD**: `1bff4166c3321e7143fb2074333f86931b49bd70`(개발 브랜치
> `worktree-commit8-3b-idempotency-store`, origin에 push 완료).
> **범위**: 문서 작성까지. 운영 코드·기존 ADR·SSOT(ARCHITECTURE.md/ROADMAP.md/
> DECISIONS.md/PROJECT_STATUS.md/CLAUDE.md) 수정 없음, GAS 접근 없음, 추가 실행
> 없음, git add/commit/push 없음, main 병합·배포 없음.
> **OFFICIAL PHASE 1 GATE는 이 문서와 무관하게 BLOCKED INPUT으로 유지된다**
> (`Sprint8_DR_B_02_Phase1_Idempotency_TTL_Preliminary_Load_Test_Result_Report.md`
> §12.2 재확인 — 이 문서는 그 판정을 바꾸지 않는다).
> **작성일**: 2026-10-04.

---

## 0. 이 문서가 다루는 두 개의 서로 다른 실측 자산 — 먼저 구분

이 결정안의 근거 자료에는 **서로 범위가 다른 두 개의 실제 GAS(Google Apps
Script) 실측**이 등장한다. 이 둘을 혼동하면 "검증됨"의 범위를 과대 해석하게
되므로 먼저 구분한다.

| | A. HMAC v2 교차검증 (격리 프로젝트 `CMC_HMAC_V2_ISOLATED_TEST`) | B. Replay Guard A/B 60건 실측 (이번 세션, commit `d130c56`/`1bff416`) |
|---|---|---|
| 검증 대상 | `protocolVersion="2"`(9필드, keyId 포함) 서명·검증 **암호 연산** 자체, Option B payload 가드 | nonce 저장방식(A=CacheService/B=PropertiesService)의 **replay 차단 동작**, 서명 거부, 예산 가드 |
| 벡터/건수 | 22개 합성 벡터(V01~V22), MATCH 12(독립 OpenSSL 검증 1건=V01, 나머지 Python 비교) / 거절 9 / 필드거절 1 | 60건(exec 53 + status 7), s1/s2/s4/s7 시나리오 |
| idempotency 5상태 모델 포함 여부 | **아니오** | **아니오** — `gas_candidate/`에는 `IdempotencyStore`에 대응하는 `.gs` 파일이 없다(nonce/서명/예산만 포팅됨) |
| 키 회전(Grace) 테스트 | **아니오**(고정 키 1쌍만 사용) | **아니오**(`TestKeyRegistry.gs`에 고정 키 1쌍만 등록) |
| 출처 문서 | `Sprint8_Commit8_3b_Isolated_GAS_CrossValidation_Result_Report.md` | `Commit8_3b_Replay_Guard_Isolated_GAS_Test_Report.md` |

**결론**: 두 실측 모두 ADR-017 §13(nonce)·§12(HMAC)의 **일부**만 실제 GAS
V8 런타임에서 검증했을 뿐, §14(Idempotency 5상태)·§15(키 회전)는 **어느
실측에도 포함되지 않는다.** 아래 6개 항목에서 이 구분을 반복해 적용한다.

## 1. 확정 요구사항 vs 구현된 실험안 vs 미확정 결정 — 전체 분류표

| 구분 | 의미 | 이 결정안에서의 예 |
|---|---|---|
| **확정(ADR-017 Accepted with Conditions)** | PM이 설계값으로 확정했으나, §29 조건(PoC 3건+부하검증) 충족 전까지는 "구현 확정"이 아님 | Nonce 이중구조 원칙(§13), 5상태 TTL 수치(§14), Grace 48h(§15), 재시도 3회(§16), 조회 HMAC 미적용(§18) |
| **구현된 실험안(격리 개발 계약, 운영 미확정)** | 이번 세션 또는 선행 세션이 격리 worktree에서 실제로 구현·실행했으나 ADR 개정으로 승격되지 않음 | HMAC v2 9필드(keyId 포함), Option B payload 가드, 양쪽 이중 nonce 저장(발급측/수신측), `idempotency_store.py`+`gas_orchestration.py` |
| **PoC/부하검증 완료(Pre-G1)** | ADR-017 §29가 요구한 사전검증 3건 중 완료분 | PoC#1(SQLite 원자성, PASS), PoC#2(CacheService eviction, PASS WITH CONDITIONS), PoC#3(저장소 정합성 불일치 Fail-Closed, PASS), DR-B-02 Phase1(TTL 예비부하검증, PASS — **단 4개 상태의 TTL 만료 후 정책은 POLICY UNRESOLVED로 명시 보고**) |
| **미확정(DEFERRED/Open Question)** | 이 결정안이 새로 확정하지 않는 것 | 만료 후 정책(SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN 4개), 재시도 집행 책임 소재, HTTP 오류코드 체계의 실제 통합, `service_hmac.py` vs ADR-017 §12 vs v2 draft 3중 형식 불일치 해소 |

**이번 60건 실측(B)이 추가한 것**: 위 "확정" 설계값 중 §13(nonce)과 일부
§12(서명 거부) 분기가 **처음으로 실제 GAS 런타임**에서 behavior 수준으로
재현됐다는 사실. **그 이상으로 확대 해석하지 않는다** — 특히 §14 Idempotency
상태모델은 이번 실측에 전혀 등장하지 않는다(§0 표 재확인).

---

## 2. 항목별 결정안

### 2-1. nonce 저장방식과 발급측/수신측 책임

**근거**:
- ADR-017 §13: "FastAPI 측 영속 저장소(1차) + GAS CacheService(2차, TTL
  300초)의 **이중 구조**"를 확정. **"CacheService 단독 사용은 채택하지
  않는다"**를 명시적으로 기록(공식 확인된 1,000항목 상한과 비영속성 때문).
  저장 실패 시 **Fail-Closed**.
- `Commit8_3b_Signed_Integration_Experimental_Status.md` §2-1~2-3: 이번
  세션 선행 작업이 "발급측 저장소"와 "수신측 저장소"를 **물리적으로 분리**한
  실험안을 구현했으나, 이는 ADR-017이 확정한 것이 아니라 **이 작업이 범위
  안에서 새로 도입한 실험안**이라고 스스로 명시. 같은 문서 §2-2: "실제 GAS
  런타임에는 로컬 파일시스템도 SQLite도 없다"는 사실만 확실하며, **"그러므로
  CacheService/PropertiesService뿐"이라고 단정하지 않는다.**
- `Sprint8_DR_B_01_PoC2_GAS_CacheService_Result_Report.md` §12: 50~200개
  규모·3회 반복에서 조기 eviction은 **관측되지 않았으나**, "CacheService
  단독으로 Replay 차단에 Production 적합하다는 것이 입증된 것으로 표현하지
  않는다"를 명시적으로 경고. TTL 300초도 "PROPOSED INITIAL VALUE"일 뿐.
- 이번 60건 실측(B)에서 VariantA(CacheService+Lock)와 VariantB
  (PropertiesService+Lock) 둘 다 s1/s2/s4/s7에서 동일하게 PASS했다
  (`Commit8_3b_Replay_Guard_Isolated_GAS_Test_Report.md` §1). **그러나
  캐시 유실(조기 eviction) 자체를 유발하는 시나리오는 이번 60건에
  포함되지 않았다** — 같은 보고서 §1이 "캐시 조기 유실 모사"를 미검증
  항목으로 명시한다. 즉 VariantB(PropertiesService)가 PASS한 것은
  **"VariantA와 같은 조건에서 같은 결과를 냈다"는 뜻일 뿐, "PropertiesService가
  운영 환경에서 nonce 저장소로 적합하다"는 것을 보여준 것이 아니다** — 이
  60건 자체가 CacheService 유실 상황을 재현하지 않았으므로, 유실 시
  VariantA가 겪는 replay 위험을 VariantB가 실제로 더 잘 막는지조차 이
  실측으로는 비교되지 않았다.

**권고안(1개)**: ADR-017 §13의 "FastAPI 1차 + GAS 2차 이중 구조" 원칙을
그대로 유지하고, 이번 세션이 구현한 "발급측/수신측 물리적 분리" 실험안은
**§13의 구체화(= GAS 2차 방어의 구현 형태로 CacheService/PropertiesService
중 하나를 "격리 실험 수준에서 검증 완료"로 승격)로만 좁게 받아들인다**.
즉 VariantA/B 중 하나를 "운영 GAS 2차 저장소"로 최종 채택하는 결정은
**이 문서에서 내리지 않으며**, 다음 조건이 충족된 뒤에 결정한다:
(a) 캐시 조기 유실을 실제로 유발하는 부하 조건에서 A/B 재검증,
(b) FastAPI 1차 저장소와의 실제 연동 통합 테스트.

**정정(이번 재검토, 이전 초안의 오류 수정)**: 이전 초안은 "FastAPI 1차
저장소가 현재 어디에도 구현되지 않음"이라고 썼다 — **이는 틀렸다.**
`src/idempotency/nonce_store.py`를 직접 열어 확인한 결과, Primary(SQLite)는
**실제로 구현되어 있다** — `_primary_try_insert()`가 house convention
(`BEGIN IMMEDIATE`+`UNIQUE` 제약, `auth_store.py`/`idempotency_store.py`와
동일 패턴)으로 원자적 삽입을 수행하고, `evaluate_and_register_nonce()`가
Primary 먼저 확인·커밋 후 Secondary(`FakeSecondaryNonceStore`, 이쪽만 실제로
미구현·Fake)를 확인하는 전체 흐름까지 갖춰져 있다(`tests/test_nonce_store.py`,
`tests/pre_g1/test_dr_b_01_poc1_sqlite_nonce_atomicity.py`, `tests/pre_g1/
test_dr_b_01_poc3_nonce_store_consistency_fail_closed.py`로 단위·PoC 검증
완료). **정확한 상태는 "미구현"이 아니라 "구현됨 + 운영 미연결"이다** —
`grep -rln nonce_store src/`로 확인한 결과 `src/idempotency/` 바깥의 어떤
파일도(라우트·서비스 포함) 이 모듈을 import하지 않는다. 즉 코드는 있지만
어떤 운영 요청도 실제로 이 경로를 타지 않는다.

**대안**:
- (대안1) VariantB(PropertiesService)를 "유실 없음"이 더 중요하다는 이유로
  바로 운영 후보로 확정 — **기각**: PropertiesService는 9KB/값·500KB/전체
  한도가 있어(ADR-017 §7-4 재인용) 트래픽 증가 시 다른 방식으로 실패할 수
  있고, 이번 실측은 그 한도 근처 부하를 전혀 가하지 않았다.
- (대안2) CacheService 단독 구조로 §13을 축소(FastAPI 1차 저장소 생략) —
  **기각**: ADR-017 §13이 "CacheService 단독 사용은 채택하지 않는다"를
  PM 명시사항으로 이미 못박았고, 이번 어떤 실측도 이를 재검토할 근거를
  제공하지 않았다.

**영향**: FastAPI 1차 저장소는 이미 구현돼 있으므로("정정" 참조), 선행
병목은 "구현"이 아니라 **"운영 라우트 배선(wiring)"**이다 — Commit8-3b 운영
통합은 GAS 측 Variant 결정과 무관하게, 기존 `nonce_store.py`를 실제 예약
흐름의 라우트/서비스 계층에 연결하는 작업이 먼저다(이번 세션에서 승인/거절
경로에 `idempotency_store.py`+`gas_orchestration.py`를 배선한 것과 동일한
종류의 작업 — §5 "다음 최소 구현 범위" 참조, nonce_store.py는 그 범위에
아직 포함되지 않았다).

**수용조건**: 이미 PASS한 s1/s2/s4/s7·PoC#2 결과를 재시험하지 않는다.
추가로 필요한 최소 검증(운영 전환 전):
1. (네트워크 없는 로컬) `nonce_store.py`(발급측/수신측 분리 설계)와
   VariantA/B 각각의 GAS 측 로직을 **같은 통합 플로우**로 묶는 로컬 테스트 —
   현재 두 자산(§0의 A/B)이 서로 다른 격리 프로젝트에 존재하며 한 번도
   같은 흐름에서 같이 실행된 적이 없다.
2. (실제 GAS 대상, 별도 PM 승인 필요) CacheService 조기 eviction을
   의도적으로 유발하는 부하(PoC#2 §11이 지적한 "더 큰 트래픽 규모")에서
   VariantA/B 재비교 — 이번 60건·PoC#2 어느 쪽도 이 조건을 만들지 않았음을
   재확인.

### 2-2. HMAC v2의 9필드 계약·keyId·키 회전·timestamp 허용범위

**근거**:
- `Commit8_3b_HMAC_Nonce_V2_Contract_Draft.md`: "**격리 개발용 제안 계약
  초안이다 — ADR-017의 공식 개정이 아니다**"를 문서 최상단에 명시. ADR-017
  §12는 `protocolVersion="1"`(8필드, keyId 없음)만 확정했고, v2(9필드,
  keyId 포함)는 이 draft가 처음 정의한 **제안**이다. keyId는 서명 대상에
  **포함**(이전 "서명 대상 밖" 대안을 철회).
- `Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §5/§8: **3번째 형식
  불일치**를 코드로 확인 — `src/auth/service_hmac.py`(운영 코드, 5필드,
  `idempotencyKey` 없음)는 ADR-017 §12(8필드)와도 다르다. 즉 현재
  저장소에는 **5필드(운영 코드)/8필드(ADR-017 §12, v1)/9필드(이 세션
  draft, v2)라는 3개의 서로 다른 Canonical String 형식**이 공존하며,
  어느 쪽으로 통합할지는 Gate Plan §44가 "Commit8-3b 설계 세부사항으로
  제안"만 하고 **결정하지 않음**으로 명시했다.
- 이번 60건 실측(B)의 `SignatureV2Port.gs`/`TestKeyRegistry.gs`는 **v2(9필드)
  만** 포팅·검증했다 — 실제로 검증된 것: 정상 서명 수용(s1), 무효 서명 거절,
  action/variant 변조 거절(S8~S10, `node_harness/entrypoint_tests.js`),
  `request.secret` 클라이언트 주입 거절(`SECRET_FIELD_NOT_ALLOWED`), 미등록
  `keyId` 거절(`UNKNOWN_KEY_ID`), 클라이언트가 주장한 `max_skew_seconds`
  무시(서버 상수만 적용, S5). **검증되지 않은 것**: 키 회전(Grace 기간 중
  구키/신키 병존, ADR-017 §15) — `TestKeyRegistry.gs`에는 고정 키 1쌍만
  등록되어 있어 회전 자체가 테스트 대상이 될 수 없는 구조다.
- A(§0, 22벡터 교차검증)가 실제 GAS V8 `Utilities.computeHmacSha256Signature`
  수준에서 9필드 서명 연산 자체의 정확성(Python/JS와 바이트 단위 일치,
  V01은 OpenSSL 독립검증)을 확인했으나, 이 역시 키 회전과 무관하다.

**권고안(1개)**: v2(9필드, keyId 포함) 계약을 **ADR-017 §12의 공식 후속
개정 후보**로 승격 검토하되, 승격 조건으로 (a) 운영 `service_hmac.py`와의
형식 통합 방법을 **먼저** 결정하고(§44 Open Question 해소), (b) 키 회전
시나리오(구키 Grace 기간 중 양쪽 키 모두 유효해야 함, ADR-017 §15)를
최소 2개 키를 등록한 상태로 실제 GAS에서 1회 재현하기 전까지는 "완료"로
표시하지 않는다.

**대안**:
- (대안1) v1(8필드, keyId 없음)으로 되돌리고 v2 draft를 폐기 — **기각**:
  keyId 없이는 키 회전 중 "어떤 키로 서명했는지"를 서버가 판별할 방법이
  없어(여러 키가 동시에 유효한 Grace 기간), §15의 48시간 Grace 설계
  자체가 구조적으로 불가능해진다.
- (대안2) 5필드 운영 `service_hmac.py` 형식을 그대로 GAS에 포팅 — **기각**:
  `idempotencyKey`가 없어 §14 Idempotency 모델과 서명을 묶을 수 없다.

**영향**: Canonical String 형식 통합 결정이 늦어질수록 운영 라우트 통합
착수(Commit8-3b 정식 구현) 자체가 지연된다 — Gate Plan §29(G3) Entry
criteria가 "Commit8-3b 대상 함수 구현 완료"이므로 형식이 확정되지 않으면
구현 자체를 시작할 수 없다.

**수용조건**: s1/s5/s8~s10(서명 거절 계열)·22벡터 교차검증은 재시험하지
않는다. 추가로 필요한 최소 검증:
1. (네트워크 없는 로컬) 3개 형식(5/8/9필드) 중 하나로 통합하는 결정이
   나오면, 그 결정에 따라 `service_hmac.py`를 갱신하거나 폐기하는 설계
   문서 1건.
2. (실제 GAS 대상, 별도 PM 승인 필요) `TestKeyRegistry.gs`에 2개 키(신/구)를
   등록하고 Grace 기간 중 양쪽 키로 서명한 요청이 모두 수용되는지, Grace
   만료 후 구키가 거절되는지(`KEY_GRACE_EXPIRED`) 1회 재현.

### 2-3. Option B raw JSON 검증과 payload 정규화 적용 위치

**근거**:
- `Commit8_3b_Payload_Normalization_Policy_Proposal.md`: 상태 헤더에 "Option
  B는 격리 개발 계약(이 worktree 안에서만 유효한 구현 전제)이다 — 운영
  ADR-017 개정이 확정되기 전까지는 운영 계약이 아니다"를 명시. §1에서 ADR-017
  범위(관리자 쓰기 스키마)에 실제로 `float`/`Decimal`/자유형 객체가 없음을
  코드로 확인해 "제약을 둬도 기능 손실이 없다"는 근거를 세움. §2에서
  RFC 8785(JCS, Option A)와의 비교 후 **Option B(요청 스키마 제한+명시적
  직렬화)를 권고**로 제시(§5 "결정이 필요한 사항"은 여전히 미결로 유지).
- §6-4: NFC 정규화는 **canonical string 전체**(payload 직렬화 결과 포함)에
  적용된다는 ADR-017 §12 원칙을 그대로 유지, 이번 Option B 구현이 이
  로직 자체를 바꾸지 않았음을 재확인.
- §6-3: "이미 파싱된 객체 경로"만으로는 "원문에 소수점이 있었는가"를 영원히
  복구할 수 없다는 **구조적 제한**을 코드로 고칠 수 없는 사실로 문서에
  유지(raw JSON 경로를 거치지 않고 dict를 직접 생성하면 재현됨을 실측).
- 이번 60건 실측(B)의 `JsonStrictParser.gs`는 Option B의 raw-JSON 선행
  검증(중복 키 거절, float/지수표기 거절)을 실제 GAS에서 S2/S3으로 검증
  (`MALFORMED_REQUEST_BODY`). A(§0, 22벡터 교차검증)의 V02/V04/V13도 같은
  가드를 검증했다. **그러나 "이미 파싱된 객체 경로"(`validate_payload_schema_interim`)
  자체는 GAS 쪽에 포팅되지 않았다** — GAS 코드는 raw JSON 경로만 포팅되어
  있고, Python 쪽에서만 재현된 "레거시 파싱 경로의 구조적 제한"(§6-3)은
  GAS에서 별도로 재현·확인된 적이 없다.

**권고안(1개)**: Option B를 ADR-017 §12 개정안(payload value 제약 절
신설)의 공식 후보로 승격 검토한다. 단, 승격 전 §5의 미결 항목(① Option
A/B 채택 여부, ② NFC 적용범위 명시, ③ 중복 키 거절 계층, ④ 개발용 가드
배선 여부)을 전부 결정해야 하며, 이 문서는 ④만 부분적으로 "결정됨(raw
JSON 경로가 GAS에도 배선되어 실제로 작동함을 확인)"으로 갱신한다.

**대안**:
- (대안1) Option A(RFC 8785/JCS) 전면 채택 — **기각**: Python 표준
  라이브러리에 JCS 미지원(UTF-16 코드 유닛 정렬 별도 구현 필요)이고, JCS의
  "Unicode 값은 있는 그대로 보존"이 기존 ADR-017 §12의 NFC 요구와 정면
  충돌(§2-3 재확인) — 이 결정안에서 그 충돌을 해소하지 않는다.
- (대안2) 정규화 규칙을 아예 확정하지 않고 Commit8-3d까지 보류 — **기각**:
  이미 §1에서 "기능 손실 없음"이 코드로 확인되어 결정을 늦출 이유가 약하고,
  Idempotency fingerprint(§14) 계산이 이 규칙에 의존하므로 더 미루면
  Commit8-3b 전체가 막힌다.

**영향**: fingerprint 계산 규칙(Idempotency 충돌 판정의 기준)이 이 결정에
직접 의존한다(`Commit8_3b_Idempotency_Store_Implementation_Status.md` §2
"payload 정규화 규칙 자체는 미확정"과 직결).

**수용조건**: S2/S3·22벡터의 V02/V04/V13 REJECT 결과는 재시험하지 않는다.
추가로 필요한 최소 검증:
1. (네트워크 없는 로컬) "이미 파싱된 객체 경로"의 구조적 제한을 GAS
   코드에서도 동일하게 재현되는지(또는 GAS 쪽에는 그 경로 자체가 없어
   해당 없음인지) 1회 확인·문서화.
2. (네트워크 없는 로컬) §5 미결 4항목 중 ①②③을 ADR 개정 논의 전에
   PM/아키텍처가 결정.

### 2-4. 최대 3회 재시도 집행 책임·허용 오류·UNKNOWN 재시도 차단

**근거**:
- ADR-017 §16: "최대 3회, 지수 백오프(1→2→4초)+Jitter(±20%), `retryable:true`
  오류에만 적용, 업무오류·`UNKNOWN`/`RECONCILIATION_REQUIRED`는 자동
  재시도 금지"를 **확정값**으로 명시.
- `Commit8_3b_Idempotency_Store_Implementation_Status.md` §7/§8: "재시도
  상한(3회)·간격 집행은 이 계층의 책임이 아니다"를 **Open Question으로
  명시**. `gas_orchestration.py`는 "1회 호출=1회 시도"만 수행하며 횟수를
  세지 않는다.
- `Commit8_3b_Signed_Integration_Experimental_Status.md` §2-4/§5: "자동
  재시도는 이 실험안 어디에도 추가하지 않았다"를 재확인 — 모든 "재시도"는
  테스트가 `handle_request()`를 **수동으로 다시 호출**해 시뮬레이션한 것.
  §5-4: "재시도 횟수 상한·간격 집행 책임 소재 — 이 실험안도 여전히 다루지
  않는다"를 남은 과제로 재확인.
- `Sprint8_Security_Test_and_Deployment_Gate_Plan.md` 추적성 표 RATE-03:
  재시도(3회, 지수백오프)는 "확정(원칙)"이나 "EXECUTABLE AFTER
  IMPLEMENTATION"(구현 자체가 없음)으로 표시.
- 이번 60건 실측(B)의 s4("원본승인→동일nonce거절→신규nonce승인→STATUS_OK")는
  **신규 nonce를 쓰는 재시도 1회가 GAS 레벨에서 수용된다**는 것만 확인했다
  — 이것은 ADR-017 §16의 "최대 3회 상한 집행"이나 "지수 백오프 타이밍"을
  검증한 것이 **아니다**(1회만 재시도했고, 상한을 초과시키는 4번째 시도를
  보내 거절되는지는 시도하지 않았다, `Commit8_3b_Replay_Guard_Isolated_GAS_Test_Report.md`
  §1 재확인). **더 중요한 제한**: `UNKNOWN 재시도 차단` 불변조건은 GAS
  쪽 코드(`gas_candidate/`)에 Idempotency 5상태 모델 자체가 없으므로(§0
  표 재확인) **real GAS에서 전혀 테스트되지 않았다** — 이 불변조건은
  오직 로컬 Python Fake-GAS 통합테스트(`test_signed_gas_integration.py::
  test_timeout_after_business_execution_marks_unknown_and_blocks_retry`)
  에서만 확인됐다.

**권고안(1개)**: 재시도 **집행 책임을 라우트/서비스 계층(FastAPI
`sheets_write_service.py` 확장 예정 지점)으로 명시 배정**하고,
`gas_orchestration.execute_with_idempotency()`는 "1회 호출=1회 시도"
원칙을 그대로 유지한다(재시도 루프를 저장 계층에 넣지 않는다 — 이미
검증된 "동일 key 동일 fingerprint 재시도 시 새 실행권 획득" 로직과
충돌하지 않도록). 상한 집계(현재 시도 횟수)는 호출부가 관리하는
별도 카운터로 설계한다.

**대안**:
- (대안1) `gas_orchestration.py` 내부에 재시도 루프와 횟수 카운터를
  추가 — **기각**: 1회 호출=1회 시도라는 현재 설계(38+18+130 테스트가
  이 전제로 작성됨)를 깨므로 기존 테스트 자산 전체를 재설계해야 한다.
- (대안2) GAS 측(`ServerBudgetGuard.gs`)에 재시도 횟수 추적을 추가 —
  **기각**: GAS는 요청당 단발 실행이라 "같은 작업의 몇 번째 시도인가"를
  판단할 상태가 없고(서버 예산 60/80건은 전체 요청 수 제한일 뿐 "같은
  작업의 재시도 횟수"가 아님), 이 책임을 GAS로 옮기면 ADR-017 §7-5
  "GAS는 호출자 신원 판단을 하지 않는다"는 책임경계 원칙과 충돌한다.

**영향**: 재시도 집행 책임이 결정되지 않으면 Gate Plan RATE-03이 영구히
"EXECUTABLE AFTER IMPLEMENTATION"에 머물고, G3(단위테스트 Gate) 진입
자체가 막힌다.

**수용조건**: s4(신규 nonce 재시도 1회 수용)·UNKNOWN 차단(로컬 Fake-GAS
불변조건)은 재시험하지 않는다. 추가로 필요한 최소 검증:
1. (네트워크 없는 로컬) 재시도 집행 책임을 명시 배정한 뒤, 상한(3회)을
   실제로 "초과시키는 4번째 시도"가 거절되는 단위 테스트 1건(현재
   미존재 — 1회 재시도만 테스트됨).
2. (실제 GAS 대상, 별도 PM 승인 필요) **선행조건 충족 전까지 보류** —
   GAS 쪽에 Idempotency 5상태 모델이 없는 한 "UNKNOWN 재시도 차단"을
   real GAS에서 검증할 방법 자체가 없다. 이 모델을 GAS에 포팅하는 결정이
   먼저 필요하다(§2-1 결정과도 연동).

### 2-5. 캐시된 결과·충돌·불확실 결과의 HTTP 응답 계약

**근거**:
- `Sprint8_Admin_Operations_API_Contract.md` §13-14: 공통 응답 구조
  (`protocolVersion/requestId/operation/ok/code/message/retryable/data/
  serverTimestamp`)와 19개 오류코드(`IDEMPOTENCY_CONFLICT`/
  `IDEMPOTENCY_IN_PROGRESS`/`RECONCILIATION_REQUIRED` 포함)를 **PROPOSED**로
  정의 — "현재 구현된 오류 응답(`HTTPException(403/404/409/502/503,...)`)은
  CURRENTLY CONFIRMED이나 위 코드 체계와는 아직 통합되지 않았다"를 명시.
- `idempotency_store.py` classification(`CACHED_RESULT`/`IDEMPOTENCY_CONFLICT`/
  `RECONCILIATION_REQUIRED` 등)은 **내부 Python 반환값일 뿐**,
  `Commit8_3b_Idempotency_Store_Implementation_Status.md` §8이 "`result`
  (자유 문자열)를 실제 응답 JSON/상태코드로 변환하는 계층 없음"을 남은
  과제로 명시.
- 이번 60건 실측(B)의 GAS 응답 형식(`{stage, detail}`, 예:
  `BUSINESS_EXECUTED`/`SIGNATURE_REJECTED`/`NONCE_REJECTED_OR_BLOCKED`/
  `MALFORMED_REQUEST_BODY`/`INTERNAL_ERROR`/`REQUEST_FIELD_INVALID`)는
  **API Contract §13의 공식 응답 구조도 아니고 §14의 19개 오류코드 명명도
  아닌, 이 격리 실험이 독자적으로 만든 어휘**다. 즉 real GAS 응답 계약은
  **이 실험 하나만 존재**하며 공식 계약과 아직 통합되지 않았다.
- `UNKNOWN`/`RECONCILIATION_REQUIRED`의 HTTP 표현은 **어느 자산에도
  real GAS 수준으로 구현된 적이 없다**(§2-4 재확인 — GAS 쪽에 그 상태
  자체가 없음).

**권고안(1개)**: 60건 실측이 쓴 `{stage, detail}` 어휘를 **API Contract
§13-14의 공식 오류코드로 매핑하는 변환표**를 다음 설계 문서에서 작성한다
(예: `SIGNATURE_REJECTED`→`AUTH_FAILED`류, `NONCE_REJECTED_OR_BLOCKED`→
`NONCE_REPLAYED`). 이 매핑은 **이번 결정안에서 직접 확정하지 않는다** —
19개 오류코드 자체가 아직 "PROPOSED"이기 때문이다.

**대안**:
- (대안1) 이번 실험의 `{stage, detail}` 어휘를 그대로 운영 계약으로
  승격 — **기각**: API Contract가 이미 더 풍부한 필드(`requestId`,
  `retryable`, `serverTimestamp`)를 설계했고, 이를 무시하면 §13 전체를
  재작업해야 한다.
- (대안2) API Contract §13-14를 지금 확정하고 GAS 코드를 그에 맞춰
  재작성 — **기각(시기상조)**: §13-14 자체가 DEFERRED 8건·CAS 설계
  (Open Question)와 맞물려 있어, 이것만 먼저 확정하면 후속 설계와
  불일치할 위험이 있다(Admin Operations API Contract §34 Open Question
  재확인).

**영향**: 이 매핑 없이는 Commit8-3b 운영 구현이 GAS 응답을 어떻게
FastAPI 오류코드로 번역할지 결정할 수 없다 — Gate Plan G4(통합테스트)
진입 조건 중 하나다.

**수용조건**: 60건 실측의 `{stage, detail}` 분류 자체는 재시험하지 않는다.
추가로 필요한 최소 검증:
1. (네트워크 없는 로컬) `{stage, detail}` → 19개 오류코드 매핑표 작성 +
   매핑표 기준 단위 테스트(실제 GAS 불필요, 순수 변환 로직).
2. (실제 GAS 대상 불필요) `UNKNOWN`/`RECONCILIATION_REQUIRED`의 HTTP
   표현은 §2-4의 "GAS에 5상태 모델 포팅" 결정이 먼저 나야 설계 가능 —
   이 문서는 그 순서만 기록하고 설계 자체는 보류한다.

### 2-6. 4개 상태의 TTL 만료 후 정책

**근거**:
- ADR-017 §14: 5상태(`IN_PROGRESS`/`SUCCEEDED`/`FAILED_RETRYABLE`/
  `FAILED_FINAL`/`UNKNOWN`) TTL을 확정값으로 명시하되, "§29의 부하검증이
  완료되기 전까지 '구현 확정값'이 아니라 '설계 확정값'으로만 간주한다"는
  유보를 달았다.
- `NonceTtlBoundary.gs`(이번 60건 실측에 실제 쓰인 코드)의 경계 공식은
  `signature_allowed_end = signed_timestamp + max_skew_seconds`이며,
  최악의 경우(timestamp가 미래로 최대한 패딩된 경우) 유효한 재전송 최종
  시점은 `T0 + 2×max_skew_seconds`다 — **이것은 nonce/서명 TTL 경계
  공식이며, ADR-017 §14의 Idempotency 5상태 TTL과는 별개의 수치·별개의
  메커니즘이다.** s7 시나리오(237.2초 후 nonce 거절→1초 후 서명만료거절)가
  실제 GAS에서 이 공식을 검증했다(`Commit8_3b_Replay_Guard_Isolated_GAS_Test_Report.md`
  §1).
- `Sprint8_DR_B_02_Phase1_Idempotency_TTL_Preliminary_Load_Test_Result_Report.md`
  §9: **IN_PROGRESS의 TTL 만료 후 정책(자동으로 UNKNOWN 전이)은 B2-02로
  PASS 확인됐으나**, 나머지 **4개 상태(`SUCCEEDED`/`FAILED_RETRYABLE`/
  `FAILED_FINAL`/`UNKNOWN`)의 TTL 만료 후 정책은 harness가 "아무 조치도
  취하지 않음"(`POLICY_UNRESOLVED_BLOCKED` 반환, 삭제·재생성 없음)으로
  **명시적으로 POLICY UNRESOLVED**라고 보고했다 — "운영 정책이 확정됐다는
  의미가 아니라, harness가 범위를 제한하고 실제로 지켜졌다는 의미일 뿐"
  이라고 그 보고서가 직접 경계를 그었다. **이 4개 상태가 정확히 사용자가
  지정한 "4개 상태"다.**
- 이 4개 상태의 만료 후 정책은 real GAS에서 전혀 다뤄지지 않았다(GAS
  쪽에 이 5상태 모델 자체가 없음, §2-4/§0 재확인) — PASS 보고는 전부
  로컬 SQLite harness 기준이다.

**권고안(1개)**: 4개 상태의 만료 후 정책을 **"조치 없음(그대로 보존,
조회만 가능)"을 임시 기본값으로 명문화**하고, 삭제·재생성 자동화는
Commit8-3b 범위에 포함하지 않는다(운영자가 수동 조정 `reconcile_unknown()`
경로로만 종결시킨다는 ADR-017 §23 "재확인(Reconciliation)" 원칙과 일치).
이는 "harness가 실제로 한 것"을 운영 기본값으로 그대로 승격하는
가장 보수적인 선택이다.

**대안**:
- (대안1) TTL 만료 시 4개 상태를 자동 삭제(디스크 공간 관리) — **기각**:
  `FAILED_FINAL`/`SUCCEEDED`를 삭제하면 "동일 키 재문의 시 일관된 결과
  반환"(ADR-017 §14 `FAILED_FINAL` TTL 900초의 설계 의도)이 깨지고,
  `UNKNOWN`을 삭제하면 운영자의 재확인 절차(§23) 자체가 불가능해진다.
- (대안2) 지금 이 문서에서 구체적 보존기간·배치삭제 주기를 확정 —
  **기각**: 실측 트래픽·운영자 재시도 행동 패턴 데이터가 없다는 사실이
  `Sprint8_DR_B_02...` §12.2가 OFFICIAL PHASE 1 GATE를 BLOCKED INPUT으로
  고정한 바로 그 이유이며, 이 문서가 그 데이터 없이 수치를 만들면 같은
  문제를 반복한다.

**영향**: 이 정책이 없으면 SQLite(Idempotency Store) 저장소가 무한히
누적되며, 운영자 재확인(Reconciliation) UI/절차(Commit8-3d 이후 범위로
추정되나 아직 어디에도 명시 배정되지 않음) 없이는 `UNKNOWN` 레코드가
영구히 쌓인다.

**수용조건**: B2-01~B2-12(IN_PROGRESS 포함 5상태 TTL 경계 자체)는
재시험하지 않는다. 추가로 필요한 최소 검증:
1. (네트워크 없는 로컬) "조치 없음" 기본값을 실제 코드(`idempotency_store.py`
   `reconcile_expired_in_progress()`류 함수의 4-상태 대응판)로 명문화하고,
   DR-B-02 harness를 확장해 4개 상태가 TTL 수백~수천 배 경과해도 레코드가
   변하지 않음을 가상시계로 1회 재확인(실제 대기 불필요, 기존 harness
   패턴 재사용).
2. (실제 GAS 대상 불필요) 운영자 수동 재확인 절차(UI/CLI)의 설계는 이
   문서 범위 밖이며 Commit8-3d 이후로 명시 이관한다.

---

## 3. ADR 개정 후보

| 후보 | 개정 대상 | 근거 |
|---|---|---|
| **ADR-017 §12 개정(또는 ADR-018 신설)** | Canonical String을 v1(8필드)→v2(9필드, keyId 포함)로 승격, payload value 제약(Option B) 절 신설 | §2-2, §2-3 — 이미 격리 환경에서 실제 GAS로 암호 연산 정확성(22벡터)과 behavior(60건 중 서명 거절 분기)를 둘 다 확인했으나 키 회전은 미검증 |
| **ADR-017 §13 개정 범위 명확화(§13 본문 수정, 신규 ADR 불필요)** | "발급측/수신측 물리적 분리" 실험안을 §13의 구체화로 받아들일지, VariantA/B 중 운영 채택안을 명시 | §2-1 — 현재 §13은 "하나의 이중 판정"만 서술, 이번 실험은 그보다 넓은 구조를 임의로 도입했음을 스스로 인정 |
| **신규 ADR 후보("ADR-019": `service_hmac.py` 폐기/갱신 결정)** | 운영 코드(5필드)·ADR-017 §12(8필드)·v2 draft(9필드) 3중 불일치 해소 | §2-2, Gate Plan §44 — 이 결정 없이는 어떤 Canonical String 버전도 "유일한 운영 계약"이 될 수 없다 |
| **ADR-017 §14 개정 불필요(현 상태 유지)** | 4개 상태 만료 후 정책은 ADR 본문 개정보다 **구현 세부규칙 문서**(Commit8-3b 설계서)로 충분 | §2-6 — ADR이 이미 TTL 수치는 확정했고, 이번 결정안은 "만료 후 조치"만 보완하므로 ADR 레벨 개정의 무게가 아니다 |

## 4. 운영 라우트 통합 착수에 필요한 결정 우선순위

**착수 전 반드시 필요(차단 요인)**:
1. **§2-2(3중 Canonical String 형식 통합)** — 이 결정 없이는 GAS 서명
   검증 코드를 어느 형식으로 "최종" 작성할지 정할 수 없다. Gate Plan
   G3 Entry criteria 자체가 이 결정에 의존한다.
2. **§2-1(VariantA/B 중 GAS 2차 nonce 저장소의 운영 채택 선택)** — **정정**:
   이전 초안은 이 항목을 "FastAPI 1차가 전혀 구현되지 않음"을 근거로
   차단 요인에 올렸으나, 그 근거가 틀렸다(§2-1 "정정" 참조 — Primary
   SQLite는 이미 구현되어 있다). 그래도 이 항목 자체는 여전히 착수 전
   필요하다 — 근거가 "미구현"에서 "GAS 2차(VariantA/B) 운영 채택 미확정 +
   실제 배선 미완료"로 바뀔 뿐이다. 단, **이번 세션에 착수한 예약 승인/거절
   idempotency 배선(아래 "이번 세션 반영" 참조)은 이 항목과 무관하게 이미
   진행됐다** — 그 작업은 `idempotency_store.py`/`gas_orchestration.py`
   (예약 중복요청/충돌 방지)만 썼고 `nonce_store.py`(HMAC v2 재전송 방지)는
   건드리지 않았기 때문이다. 즉 이 항목이 실제로 차단하는 것은 "HMAC
   서명이 적용된 GAS 쓰기 경로"뿐이며, 그 경로는 §2-2(Canonical String
   통합)가 먼저 끝나야 비로소 의미가 생긴다(순서상 1번 뒤에 옴).

**이번 세션 반영(참고, 차단요인 아님)**: 아래 "다음 최소 구현 범위"(§5)에서
제안했던 작업을 이 결정안 자체의 검토 과정에서 바로 진행했다 — 예약
승인/거절(`routes_admin_portal.py`)의 GAS 쓰기 단계를
`gas_orchestration.execute_with_idempotency()`(기존 모듈, 신규 로직 없음)로
감싸 "결과 불확실(timeout 등)"과 "확정 실패"를 구분했고, Fake GAS·로컬
SQLite로 성공/중복/충돌/timeout/기록실패/UNKNOWN재요청차단 6개 흐름을
검증했다(`tests/test_commit8_3b_reservation_approval_idempotency_integration.py`,
6/6 PASS). `nonce_store.py`는 이 작업 범위에 포함되지 않았다(여전히 미배선).

**나중에 결정해도 되는 것(착수를 막지 않음)**:
3. §2-5(HTTP 오류코드 매핑표) — 내부 로직이 먼저 안정화된 뒤 매핑만
   하면 되는 변환 작업이라 뒤로 미뤄도 구현 착수 자체는 가능하다.
4. §2-6(4개 상태 만료 후 정책) — "조치 없음" 보수적 기본값으로 착수는
   가능하고, 정밀 정책은 운영 데이터가 쌓인 뒤 재검토 가능(§2-6 권고안
   자체가 이미 이를 전제로 설계됨).
5. §2-3(Option B 공식 승격) — 이미 격리 환경에서 작동 확인된 가드이므로,
   형식 승격이 늦어져도 구현에서 그대로 재사용 가능(뒤로 미뤄도 손실 적음).
6. §2-4(재시도 집행 책임 배정) — 1차 구현은 "재시도 없음(클라이언트가
   수동 재시도)"으로도 동작하므로, 집행 책임 배정은 재시도 기능 자체를
   추가하는 시점에 결정해도 된다.

## 5. 다음 최소 구현 범위

**정정**: 이전 초안은 "`nonce_store.py`를 `src/idempotency/`로 옮긴다"고
썼으나 — 그 파일은 **이미** `src/idempotency/nonce_store.py`에 있다(이번
재검토에서 직접 확인). "옮기는" 작업은 필요하지 않다.

**이미 완료(이번 세션)**: §2-1/§4에서 밝힌 대로, 예약 승인/거절(`routes_
admin_portal.py`)의 GAS 쓰기 단계를 기존 `gas_orchestration.py`/
`idempotency_store.py`로 감싸는 최소 통합을 이번 결정안 검토 과정에서 바로
진행했다(`sheets_write_service.update_status_idempotent()` 추가,
`reservation_audit.py`에 신규 감사 이벤트 1개 추가, 6개 흐름 시나리오
전부 PASS). 운영 GAS 접근·commit/push는 하지 않았다(개발 worktree 내부
변경만, 아래 "완료 조건 준수 확인" 참조).

**다음으로 남은 최소 단위**: `nonce_store.py`(HMAC v2 재전송 방지, 이번
작업과 별개)는 아직 어떤 라우트에도 배선되지 않았다 — 하지만 §4에서 밝힌
대로 그 배선은 §2-2(Canonical String 통합)가 먼저 끝나야 의미가 생기므로,
다음 최소 단위는 **nonce_store.py 자체를 먼저 건드리는 것이 아니라
§2-2(3중 형식 불일치 해소) 결정**이다 — 결정이 나면 `nonce_store.py`를
그 결정된 서명 검증 경로에 단위테스트 수준으로 먼저 연결(라우트 배선 없이)
하는 것이 그 다음 조각이 된다.

---

**완료 조건 준수 확인(이 문서 작성 시점 기준 — 아래 "이미 완료" 작업은
같은 턴에서 사용자가 추가로 승인한 별도 지시에 따라 수행됐으며, 그 상세
보고는 이 문서가 아니라 해당 작업의 완료 보고에서 한다)**:
ADR-017·DECISIONS.md·ARCHITECTURE.md·ROADMAP.md·PROJECT_STATUS.md·
CLAUDE.md를 포함한 SSOT 문서는 이번 재검토 중 수정하지 않았다. 실제
GAS·Google Sheets에 접근하지 않았다(Fake GAS·로컬 SQLite만 사용). git
add/commit/push를 수행하지 않았다(개발 worktree 내부 변경만). 이 문서의 모든
권고안은 제안일 뿐이며, 실제 ADR 승인·SSOT 갱신은 PM/아키텍처 승인 후
별도 작업이다. **OFFICIAL PHASE 1 GATE는 이 문서와 무관하게 BLOCKED
INPUT으로 유지된다.**
