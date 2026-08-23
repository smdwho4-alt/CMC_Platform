# Sprint8 DR-B-01 PoC#2 — GAS CacheService Eviction 격리 실행 결과 보고서

> **상태**: 실행 완료(Pre-Implementation Harness, ADR-017 §29). Commit8-3b 정식 구현이 아니며, 이 결과는 Commit8-3b 착수 승인이나 G6 최종검증 통과를 의미하지 않는다.
> **작성일**: 2026-08-23(Sprint8 Pre-G1-B-E)
> **실행계획 원본**: `docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Test_Plan.md`
> **harness**: `tests/pre_g1/gas/dr_b_01_poc2_cache_service_harness.gs`

---

## 1. 목적과 범위

ADR-017 §29 PoC#2("GAS CacheService의 실제 eviction 빈도를 이 시스템의 예상 트래픽 규모로 시뮬레이션")를 저장소 밖 격리 standalone GAS 프로젝트에서 실제 실행한 결과를 기록한다. 이 문서는 계획서(`Sprint8_DR_B_01_PoC2_GAS_CacheService_Test_Plan.md`)의 12개 시나리오(P2-01~P2-12)에 대해 계획된 검증 절차가 완료된 결과, 실행 중 발생한 OAuth Scope 이슈와 그 조치 경과, 그리고 이 결과의 해석 범위를 담는다.

## 2. 실행 환경

- 저장소 밖 **독립형(standalone) 격리 GAS 프로젝트**(계획서 §9 요구사항대로 생성, Spreadsheet 미바인딩)에서만 실행. 운영 GAS(`app/apps_script/sheets_api_v3_final.gs` 배포본), 운영 Google Sheets, 운영 데이터, 실 HMAC Secret은 어디에서도 사용하지 않았다.
- 저장소 harness SHA-256: `dcfe1ce4a2d0cbe5657820220d020aa5e1ddbefd569fad4e0171099b9708203b`(1183줄) — 격리 프로젝트에 push된 harness와 pull 비교로 동일함을 실행 전 확인(§3).
- 모든 key/value는 합성 문자열만 사용(`poc2test_` prefix), 실 예약번호·PII·실 nonce 미사용.
- 계정 이메일·scriptId·프로젝트 URL·Token은 이 문서 어디에도 기재하지 않는다.

## 3. OAuth Scope 이슈와 조치 경과

실행 전 Apps Script 편집기의 자동 OAuth Scope 탐지 화면에서 예상하지 않은 "모든 Google Sheets 스프레드시트 확인·수정·생성·삭제" 권한이 표시되었다. 사용자는 동의를 거부했으며, 이 시점에 GAS 함수는 실행되지 않았다.

### 3.1 원인 조사(결과: 미확정)

1. 저장소·격리 workspace harness 전수 검사 — `SpreadsheetApp.`/`Sheets.`(Advanced Service) 실제 호출 0건, manifest에 `oauthScopes`/`enabledAdvancedServices` 없음, `.clasp.json`에 `parentId`(container-bound 흔적) 없음.
2. Google 공식 Apps Script 문서(`developers.google.com/apps-script/concepts/scopes`) 확인 — 자동 scope 탐지는 코드의 함수 호출을 스캔하며, 문서는 "Apps Script sometimes automatically assigns permissive scopes"라고 명시하되 정확한 유발조건은 공개하지 않는다.
3. 원격 프로젝트 감사 Pull(별도 격리 감사 디렉터리, 저장소·기존 workspace 미접촉) — 원격 harness·manifest가 로컬과 완전 동일(diff 0건, SHA-256 일치), stray 파일·Sheets API·Advanced Service 없음을 확인.
4. 로컬·원격 코드와 manifest 어디에서도 근본 원인을 특정하지 못했다. 이 시점의 판정은 `BLOCKED — GAS AUTO-SCOPE OVERPERMISSION SUSPECTED`(자동탐지 과잉권한 부여로 추정되나 확정 근거 없음)였다. 이 문서도 자동탐지 과잉권한을 근본 원인으로 확정하지 않는다.

### 3.2 조치와 관찰된 효과(원인 규명과는 별개)

원인이 미확정인 상태에서, 최소권한 실증 조치로 격리 workspace manifest에 `"oauthScopes": []`(명시적 빈 배열)를 추가한 candidate를 문자 단위 검증 후 반영했다. `clasp push`는 manifest 변경 시 기본적으로 거부(`Skipping push.`)되는 clasp 자체의 안전장치(`--force`로만 우회 가능)를 확인했고, 이번 격리 프로젝트 1건에 한해 `clasp push --force`를 정확히 1회 실행하는 것으로 별도 승인받아 수행했다. Push 직후 신규 격리 감사 디렉터리에서 재차 `clasp pull`하여 원격 manifest가 `oauthScopes: []`이고 나머지 4개 필드·harness가 승인 해시와 정확히 일치함을 재확인했다.

관찰된 사실: `oauthScopes: []` 적용 이후 Apps Script 편집기의 프로젝트 개요에서 "요청된 OAuth 범위 없음"으로 표시됨을 사용자가 직접 확인했다. 즉 Sheets 권한 요청이 제거된 것은 실측 사실이다. 다만 이것이 §3.1의 원인을 확정 규명한 것은 아니며, 조치를 적용하니 증상이 사라졌다는 관찰일 뿐 인과관계를 증명하지 않는다. 실제 함수 실행은 이 확인 이후에만 진행했다.

이 조치는 이번 격리 PoC 1회에만 적용된 잠정값이며, Production manifest 정책으로 확정하는 것이 아니다(§12).

## 4. harness 구조 요약

계획서 P2-01~P2-12를 harness 함수로 구현했으며(전체 매핑은 harness 상단 Scenario Registry 참조), P2-04/P2-05는 Apps Script 편집기의 "함수 선택" Run이 인자를 전달할 수 없다는 제약 때문에 별도의 무인자 수동 어댑터(`poc2_beforeTtlManual()`/`poc2_afterTtlManual()`)를 두었다. 두 어댑터는 Script Properties를 결과 저장용이 아니라 P2-04→P2-05 간 일회성 합성 handoff 메타데이터 전달 통로로만 사용하며(`runId`/`key`/`startedAtMs`/`ttlSeconds`/`createdAt` 5개 필드만), 기존 property 존재 시 덮어쓰지 않는 Fail-Closed·LockService 보호가 적용되어 있다(harness §4.1).

## 5. 실행 순서

계획된 검증 절차는 단일 실행이 아니라 아래 4단계로 나뉘어 완료되었다.

1. `runPoc2All()` — P2-01/02/03/04(Phase A)/06/07/08/09/10/11/12를 한 번에 실행(단, P2-05는 이 단계에서 `NOT_RUN`으로 남고 아래 3~4단계로 이관됨)
2. `poc2_beforeTtlManual()` — P2-04 TTL 수동 사이클 시작, handoff 저장
3. 실제 시간 경과 대기(Utilities.sleep 미사용)
4. `poc2_afterTtlManual()` — TTL 경과 확인 후 P2-05 최종 판정, handoff 삭제
5. `poc2_verifyCleanup()` — 최종 정리 검증(인자 없음)

## 6. 실행 결과

### 6.1 `runPoc2All()` 일괄 실행(1단계)

전체 소요시간 19.218초.

| 시나리오 | 결과 | 비고 |
|---|---|---|
| P2-01 | PASS | put 후 즉시 get 값 일치 |
| P2-02 | PASS | overwrite 후 최신값 반환 |
| P2-03 | PASS | remove 후 null 확인 |
| P2-04 | PASS(Phase A) | put 직후 get 값 일치(참고용 스모크 테스트, §4 원칙대로 이 실행 자체는 TTL 판정 증적으로 사용하지 않음) |
| P2-05 | NOT_RUN | 설계대로 이 단계에서는 실행하지 않고 별도 수동 사이클(§6.2)로 이관 |
| P2-06 | PASS_WITH_CONDITIONS | 50개 투입, 50개 잔존(retentionRate=1) — 사전 pass 기준 없는 관측목적 시나리오, "정상 실행 완료"만 의미 |
| P2-07 | PASS_WITH_CONDITIONS | marker 5개와 pressure key 200개 투입, marker 5/5 잔존(earlyEvictionCandidates=0) — 이 규모에서 조기 eviction 미관측 |
| P2-08 | PASS_WITH_CONDITIONS | 3회 반복 잔존율 [1, 1, 1] — 편차 0 |
| P2-09 | PASS_WITH_CONDITIONS | lockAcquired=true, Lock 有/無 코드 경로 비교 완료. 실제 동시 경합은 이 harness 구조상(단일 실행 순차처리) 검증되지 않음 |
| P2-10 | PASS_WITH_CONDITIONS | P2-07/P2-08 결과 2건을 근거자료로 산출. Fail-Closed 정책 자체를 확정한 것이 아님 |
| P2-11 | PASS | 의도적 timeLimitMs=1 강제 조건에서 내부 P2-06 변형이 STOPPED로 조기 중단, 부분결과 보존과 cleanup 정상 동작 확인(자기검증 성공) |
| P2-12 | PASS | 이 배치가 자체 생성한 key의 cleanup·검증만 정상 수행(§10에서 최종 P2-12와 구분) |

수동 어댑터(`poc2_beforeTtlManual()`) 결과는 이 표의 P2-04 행과 별개이며 §6.2에 기재한다.

### 6.2 P2-04/P2-05 TTL 수동 왕복(2~4단계, §4 절차)

- `poc2_beforeTtlManual()`: 기존 handoff 없음 확인 후 Phase A 실행(`status='PASS'`), handoff 저장 성공. 수동 어댑터 결과: `PASS_WITH_CONDITIONS`(handoff 저장 성공) — 이 결과가 P2-04/P2-05 TTL 왕복의 권위 있는 증적이다.
- 대기: 실제 경과시간 366,283ms(TTL 300,000ms 대비 충분히 경과, Utilities.sleep 미사용)
- `poc2_afterTtlManual()`: handoff 로드·검증 통과 후 TTL 경과 확인(elapsedMs=366,283 ≥ requiredMs=300,000), 기존 `poc2_afterTtl(runId, startedAtMs)` 재사용 실행 결과 `nullAfterTtl=true`, 계획서 §16 기준 정상 TTL 만료로 분류(eviction 아님). P2-05 최종 결과: `PASS`. handoff 삭제 성공(삭제 후 부재까지 확인, §10).

### 6.3 최종 정리 확인(5단계)

`poc2_verifyCleanup()`(무인자, 별도 최종 실행): `checked=0`, `remaining=0`, `handoffPropertyPresent=false` → PASS. 이 수치의 정확한 의미는 §10을 참조 — Cache 전체의 무잔존을 보증하는 것이 아니라, harness가 이 시점까지 추적한 key 목록과 handoff property에 한정된 확인이다.

### 6.4 시나리오별 최종 결과 요약(P2-01~P2-12, 각 1행)

| ID | 최종 결과 |
|---|---|
| P2-01 | PASS |
| P2-02 | PASS |
| P2-03 | PASS |
| P2-04 | PASS(Phase A) |
| P2-05 | PASS(수동 사이클, TTL 경과 후 정상 만료 확인) |
| P2-06 | PASS_WITH_CONDITIONS |
| P2-07 | PASS_WITH_CONDITIONS |
| P2-08 | PASS_WITH_CONDITIONS |
| P2-09 | PASS_WITH_CONDITIONS |
| P2-10 | PASS_WITH_CONDITIONS |
| P2-11 | PASS |
| P2-12 | PASS(최종 정리 확인 기준, §6.3) |

수동 어댑터(`poc2_beforeTtlManual()`) 자체 결과 `PASS_WITH_CONDITIONS`는 위 표의 별도 행이 아니라 P2-04/P2-05 왕복 증적으로서 §6.2에 귀속된다.

## 7. eviction 관측 결과

이번 실행 규모(P2-06 50개, P2-07 marker 5개와 pressure 200개, P2-08 3회 반복)에서 TTL 미경과 시점의 조기 eviction은 관측되지 않았다(P2-06 잔존율 1, P2-07 marker 5/5 잔존과 earlyEvictionCandidates=0, P2-08 반복 잔존율 [1,1,1]). P2-05는 TTL(300초) 경과 후 정상 만료(`nullAfterTtl=true`)만 관측했으며 이는 계획서 §16 기준 eviction으로 집계하지 않는다.

## 8. Lock 적용/미적용 비교 결과

P2-09에서 `LockService.getScriptLock()` 적용 경로(`lockAcquired=true`)와 미적용 경로 모두 순차 실행 결과값이 일관됨을 확인했다. 다만 이 harness는 단일 실행 내 순차 비교 구조이므로 실제 동시 요청 경합 상황의 Lock 효과는 이번 실행으로 검증되지 않았다.

## 9. quota/time guard 결과(P2-11)

의도적으로 극히 짧은 timeLimitMs=1을 부여해 내부 시간 가드를 강제 트리거한 결과, 대상 시나리오가 즉시 STOPPED로 중단되었고 그 시점까지의 부분 결과와 cleanup이 정상적으로 보존·수행되었다(자기검증 PASS). 실제 GAS quota 초과는 이번 실행에서 발생하거나 유발되지 않았다.

## 10. Cleanup 및 handoff 부재 결과(범위 제한 명시)

GAS `CacheService`는 전체 key를 열거하는 API를 제공하지 않는다(계획서 §25 재확인). 따라서 이 문서가 보고하는 cleanup 결과는 harness가 추적한 key와 handoff property의 잔존이 확인되지 않음이라는 제한된 의미이며, Cache 전체에 테스트 리소스가 전혀 잔존하지 않는다는 보증이 아니다.

- `runPoc2All()` 내부 P2-12 배치 cleanup: 그 실행이 자체 생성·추적한 key에 한해 정상 cleanup·검증 완료(§6.1).
- `poc2_afterTtlManual()`의 handoff 자체 삭제: TTL 왕복에 사용된 handoff property 1건을 삭제하고 삭제 후 부재를 재확인함(§6.2).
- 최종 `poc2_verifyCleanup()`(`checked=0, remaining=0, handoffPropertyPresent=false`): 이 시점에 harness에 전달된 key 목록이 비어 있었고(추적 대상이 없었음), handoff property도 부재임을 확인한 것이며, 이는 앞의 두 단계에서 이미 각자 정리된 결과가 최종적으로 재확인된 것이다.

## 11. 한계

- 이번 실행은 단일 계정, 단일 실행 세션, 1회 사이클 기준이다. 반복 실행 규모도 계획서 잠정값(50~200개, 3회)에 한정되어 있어, 더 큰 트래픽 규모에서의 eviction 발생 여부는 이 결과만으로 판단할 수 없다.
- OAuth Scope 이슈(§3)의 근본 원인은 미확정 상태로 남아 있다. `oauthScopes: []` 조치로 증상은 해소됐으나, 향후 Commit8-3b 실제 배포 시 동일 현상이 재현될 수 있는지는 이 결과만으로 알 수 없는 운영 관찰사항이다.
- LockService 실동시성, 대규모 quota 초과 상황은 이 harness 구조로 재현되지 않았다.
- Cache 전체 무잔존은 GAS API 제약상 검증 불가하며, harness가 추적한 범위에 한해서만 정리를 확인했다(§10).

## 12. 해석 제한(과대 해석 금지)

- 이번 50~200개, 3회 반복 규모에서 조기 eviction이 관측되지 않았다는 사실을, Production 규모에서 eviction이 발생하지 않는다는 보증으로 확대 해석하지 않는다.
- CacheService 단독으로 Replay 차단에 Production 적합하다는 것이 입증된 것으로 표현하지 않는다(ADR-017 §13은 이중 저장 구조를 유지하며, 이 결과가 그 필요성을 약화시키지 않는다).
- TTL 300초를 이 실행으로 Production 최종값으로 확정하지 않는다(여전히 PROPOSED INITIAL VALUE).
- LockService의 실제 동시 경합 방어 효과는 이번 실행으로 검증되지 않았다(§8).
- `oauthScopes: []`는 이번 격리 PoC 1회에만 적용된 실증값이며 Production manifest 정책으로 확정하지 않는다(§3.2).
- 이 결과는 DR-B-02 Phase 1(예비 부하검증)이나 Phase 2(G6 최종검증)를 대체하지 않는다.
- 이 결과 자체가 Commit8-3b 정식 착수 승인이나 G6 Pass를 의미하지 않는다(ADR-017 §29 원칙 그대로).

## 13. PoC#1·#3, DR-B-02와의 관계

PoC#1(SQLite UNIQUE 원자성)은 이미 완료·Push됨(PASS, `Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md`)이며 이 결과와 별개다. PoC#3(양쪽 저장소 정합성 불일치 처리)은 이 문서가 산출한 P2-10 근거자료를 참고자료로 활용할 수 있으나 이 문서에서 설계하지 않는다. DR-B-02(Idempotency 부하검증) Phase 1과 Phase 2는 이 결과와 별개의 검증 대상이며 대체되지 않는다.

## 14. 최종 판정

```
PASS WITH CONDITIONS — EXECUTION COMPLETED, EVICTION NOT OBSERVED
```

P2-01~P2-12에 대해 계획서가 정의한 검증 절차가 4단계(§5)에 걸쳐 완료되었으며, 이번 실행 규모에서 조기 eviction은 관측되지 않았다. §12의 해석 제한을 벗어난 결론(Production 적합성 입증, TTL 확정, Commit8-3b 착수와 G6 통과 등)은 이 문서로 내려지지 않는다. 실행 전 OAuth Scope 문제(§3)는 격리 프로젝트 범위 내에서 증상이 해소되었으나 근본 원인은 미확정이며, 이는 §11에 운영 관찰사항으로 남는다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 GAS 함수를 추가 실행하지 않았다. 운영 GAS·Google Sheets에 접근하지 않았다. 실제 계정 이메일·scriptId·URL·Token·property 원문을 포함하지 않았다. Production 코드·기존 Gate 문서를 수정하지 않았다. Git add/commit/push를 수행하지 않았다.
