# Sprint8 Commit8-3b — Replay 차단 격리 GAS A/B 실측 보고서

- 작성일: 2026-10-04
- 범위: 격리 테스트 프로젝트(합성 키·합성 데이터, 운영 GAS·Sheets 비연결)에서 수행한 Replay 차단 설계 검증. **OFFICIAL PHASE 1 GATE는 이 작업 전체와 무관하게 BLOCKED INPUT으로 유지됨.**
- 이 문서는 이번 턴에 `test: record isolated GAS replay guard experiment and evidence` 커밋에 포함된다. **push는 수행하지 않았다** — 개발 worktree 브랜치에만 commit됨.

---

## 1. 실제 전송 수와 시나리오별 결과 (원본 증적 대조)

원본 증적(`tests/cross_validation/gas_replay_experiment/evidence/real_gas_execution_result_v3.json`)에서 독립 재계산:

```
exec_count = 53, status_count = 7, total = 60
```

스크립트 자체가 보고한 `computed_total_requests: 60`과 일치(자가보고를 그대로 믿지 않고 별도 재계산으로 확인).

| 시나리오 | 결과 | 판정 |
|---|---|---|
| s1(A/B 최초허용·재사용거절) | 양쪽 BUSINESS_EXECUTED→NONCE_REJECTED_OR_BLOCKED→STATUS_OK | PASS |
| s2(A/B 동시 20건, 1회) | 양쪽 `server_accepted:1, server_rejected:19, network_errors:0` | PASS |
| s4(A/B 업무실행 전 실패 후 재전송) | 원본승인→동일nonce거절→신규nonce승인→STATUS_OK | PASS |
| s7(A 대표, 서명유효기간-nonce 경계) | t0승인→237.2초 후 nonce거절→1초 후 서명만료거절→STATUS_OK | PASS |

미확인 항목 없음 — 60건 전부 스크립트의 실시간 검증을 통과했고 중단 없이 종료됨.

**실제 검증 범위는 s1·s2·s4·s7로 한정된다.** 아래는 이번 실측에 포함되지 **않은** 항목이다(로컬 시뮬레이션에서만 확인됨, 실제 GAS 검증 아님):
- 캐시 조기 유실 모사(명시적 `cache.remove()` 호출 기반)
- 잠금 타임아웃·저장소 강제 오류 주입
- 서버 요청 상한(80건) 초과 시 실제 차단 동작(§2 참조)
- 운영 GAS·Sheets 연동

## 2. 계획 요청 수(60건)와 서버 상한(80건)

이 둘은 **서로 다른 값**이다. `ExperimentConfig.gs`에 하드코딩된 값:
```
var EXPERIMENT_DEADLINE_SECONDS = 900;   // 15분
var EXPERIMENT_REQUEST_CAP = 80;         // 계획된 60건 + 소폭 여유(재시도 대비)
```
이 주석은 이 값을 **왜 이렇게 골랐는지에 대한 작성 당시의 의도 설명일 뿐**이며, 80이라는 값 자체가 별도의 검토·승인 절차를 거쳤는지는 확인된 바 없다. 이번 실측에서는 정확히 60건만 전송했고 80에 도달하지 않았으므로, **"81번째 요청이 실제로 차단되는가"라는 상한 차단 기능은 실제 GAS에서 검증되지 않았다.** 이 로직의 원자성은 로컬 전용 테스트(`local_verification/test_server_budget_guard.py::test_budget_cap_enforced_atomically_under_real_concurrency`, 합성 저cap값 40스레드 동시 테스트)로만 확인됐다.

## 3. 코드 해시 — 실행에 쓰인 원본 vs 저장소 후보

아래 표는 **실제 60건 실행에 쓰인 원본 파일(scratchpad)**의 SHA-256과, **이번에 저장소 후보로 재배치한 파일(git staged blob, `git show :<path>` 기준)**의 SHA-256을 모두 남긴다. 최초 작성 시점에는 "이름만 바꿨고 내용은 바이트 단위로 동일"하다고 기록했으나, 이번 최종 점검에서 재확인한 결과 **그 전제가 일부 틀렸다는 것을 발견했다** — 가져오기 경로(`_new` 접미사 제거)와 절대 로컬 경로를 고치는 과정에서 `local_verification/`의 10개 파일과 `node_harness/node_gas_http_server.js` 1개 파일의 실제 내용이 추가로 바뀌었다. 아래 표는 이 사실을 반영해 전부 재검증한 값이다.

| 저장소 경로 | 배너 | 내용 변경 | 실행에 쓰인 원본 SHA-256 | 저장소 후보 SHA-256 |
|---|---|---|---|---|
| `gas_candidate/AdminOnly_ManualCacheRemoval.gs` | 아니오 | 없음(이름만) | `ebbad3cc...9bd4` | 동일 |
| `gas_candidate/ExperimentConfig.gs` | 아니오 | 없음(이름만) | `110663fb...cf48` | 동일 |
| `gas_candidate/JsonStrictParser.gs` | 아니오 | 없음(이름만) | `53fa9e29...f0bf` | 동일 |
| `gas_candidate/Main_doPost_stub.gs` | 아니오 | 없음(이름만) | `a3d9b0ca...7a23` | 동일 |
| `gas_candidate/NonceTtlBoundary.gs` | 아니오 | 없음(이름만) | `a35eeaab...de1c2` | 동일 |
| `gas_candidate/RealEntryPoint.gs` | 아니오 | 없음(이름만) | `202704fc...3d55` | 동일 |
| `gas_candidate/ServerBudgetGuard.gs` | 아니오 | 없음(이름만) | `14abe232...ce03` | 동일 |
| `gas_candidate/SignatureV2Port.gs` | 아니오 | 없음(이름만) | `ae67a5e6...ea1cc` | 동일 |
| `gas_candidate/TestKeyRegistry.gs` | **예** | 배너 추가 | `35760b58...8303` | `ad3bee8a...502c` |
| `gas_candidate/VariantA_CacheLock.gs` | 아니오 | 없음(이름만) | `627a5634...a20d1` | 동일 |
| `gas_candidate/VariantB_PropertiesLock.gs` | 아니오 | 없음(이름만) | `5e3b4c9d...a512ff` | 동일 |
| `gas_candidate/appsscript_candidate.json` | 아니오 | 없음(이름만) | `a18066b0...1eab8` | 동일 |
| `node_harness/gas_stubs.js` | 아니오 | 없음(이름만) | `fc2d343d...e225cc` | 동일 |
| `node_harness/entrypoint_tests.js` | **예** | 배너+실행안내 주석 추가 | `2c8af2c2...deb6e`(최초 배너 추가 시점) | `daefbc1c...767105` |
| `node_harness/node_gas_http_server.js` | 아니오 | **재작성**(제외된 빌드산출물 `concatenated_all_v2.js` 의존 제거 → `gas_candidate/*.gs` 직접 읽어 연결) | `ca4c78d9...dab312c` | `821a8332...4630ca4` |
| `local_verification/sim_cache_service.py` | 아니오 | 없음(이름만) | `eb041b27...2b03315` | 동일 |
| `local_verification/sim_properties_service.py` | 아니오 | 없음(이름만) | `396b0da0...4a38789` | 동일 |
| `local_verification/sim_script_lock.py` | 아니오 | 없음(이름만) | `9d423fde...1d9fd3e` | 동일 |
| `local_verification/nonce_ttl_boundary.py` | 아니오 | 없음(이름만) | `8244641d...936ec278f` | 동일 |
| `local_verification/concurrent_http_driver.py` | 아니오 | import 경로(`_new` 제거)+절대경로→`Path(__file__)` 상대화 | `84763c92...b6e07059` | `4b6297b0...c32246` |
| `local_verification/local_mock_gas_server.py` | 아니오 | import 경로 수정 | `f989ceea...2d2ec26c7d4` | `7ce299bf...6ca3084689` |
| `local_verification/real_execution_run.py` | 아니오 | import 경로 수정 | `8684fd0d...f799e6f0f1d14` | `9e7aa5b8...50cad126b7e5` |
| `local_verification/replay_guard.py` | 아니오 | import 경로 수정+절대경로→`Path(__file__)` 상대화 | `c2f14e6f...8291f4c982610` | `d877a323...f84f8a5599ceb` |
| `local_verification/server_budget_guard.py` | 아니오 | import 경로 수정 | `234200c2...2eb15b56606718148` | `587704c3...a40df9a9c` |
| `local_verification/test_concurrent_http_driver_local.py` | 아니오 | import 경로 수정 | `a5285364...028ed20263afe788` | `2f074f2d...ec96e94b1cb` |
| `local_verification/test_dry_run_full_sequence.py` | 아니오 | import 경로 수정 | `d13b1b93...950dc4fdadc8057313` | `523592d9...1038ba97bf1666` |
| `local_verification/test_preflight_action_binding.py` | 아니오 | import 경로 수정 | `f339e102...a4dad090a0bdc270f` | `6988a79b...4f0f75070592` |
| `local_verification/test_replay_guard_local.py` | 아니오 | import 경로 수정 | `86735b97...b71501f8fc7efcb4a29f0` | `24bf13f1...2925be0986ead6086` |
| `local_verification/test_server_budget_guard.py` | 아니오 | import 경로 수정 | `879b36df...ffd7a672e63311a8dc23c` | `8f8ad142...2aac569e6a952ef14` |
| `local_verification/test_e2e_real_gas_code.py` | **예** | 배너 추가+import/Node서버 경로 수정 | `33947754...e07e9`(최초 배너 추가 시점) | `1613ea00...640aebd` |
| `local_verification/test_dry_run_v3_real_code.py` | **예** | 배너 추가+import/Node서버 경로 수정 | `87d3fac9...e46c2`(최초 배너 추가 시점) | `93a1a748...125e08` |
| `evidence/real_gas_execution_result_v3.json` | 아니오 | 없음(이름만) | `a74f35cd...da99` | 동일 |

모든 "저장소 후보 SHA-256"은 작업트리 재읽기가 아니라 `git show :<경로>`(실제 commit 대상이 될 staged blob)로 계산했다 — 이 저장소는 `core.autocrlf=true`이고 `.gitattributes`가 없어, 작업트리 파일을 직접 다시 읽으면 줄바꿈 정규화 때문에 동일 내용도 다른 해시로 보일 수 있기 때문이다. 표가 길어 해시를 일부 축약 표기했다(앞/뒤 일부 자리) — 전체 64자 값은 이 commit의 git 객체에서 `git show :<경로> | sha256sum`으로 언제든 재계산 가능하며, 별도의 임시 파일에 보관하지 않는다.

**실제 배포본과의 독립적 바이트 해시 비교는 이번에도 수행하지 않았다** — 배포 조회 API 권한 문제가 해소되지 않은 채로 유지되고 있어서다. 60건 응답이 기대값과 일치한 것은 로컬 코드와 실제 동작이 일치한다는 간접 증거일 뿐, 바이트 단위 확인은 아니다.

**초기화 래퍼 이력**: `function adminResetExperimentBudget() { adminResetExperimentBudget_(); }`은 사용자가 Apps Script 편집기 HEAD에 직접 붙여넣고 실행했다. 이 코드는 로컬 어떤 파일에도 저장되지 않았고(저장소 후보에도 없음), v3 배포(Web App 버전)에도 포함되지 않았다 — "실행" 기능은 항상 프로젝트 HEAD를 대상으로 하므로 배포 버전에 포함될 필요가 없었다.

## 4. 공개 배포 보관 처리

사용자 확인(2026-10-04): 활성 테스트 배포의 접근 권한 보관 처리 완료. 추가 HTTP 요청으로 재확인하지 않았다 — 사용자 진술을 그대로 사실로 기록한다.

## 5. 저장소 반영 후보 — 파일 목록·변경 요약 (commit/push 미수행)

경로: `tests/cross_validation/gas_replay_experiment/`(32개 파일, 아래 4개 종류로 분류) + 본 문서(`docs/`, 1개) = **총 33개**. (최초 지시에서는 "32개"로 표현됐으나, 실제 `git diff --cached --name-only` 기준 재확인 결과 본 문서를 포함해 33개임을 확인했다 — 이전 보고에서 `local_verification/`을 15개로 잘못 센 것이 원인이며, 아래에서 정정한다.)

### 5-1. GAS 후보 소스(`gas_candidate/`, 12개)
서버 측 doPost/doGet 진입점, 서명 검증, nonce 가드(A/B), 예산 가드, 자체 JSON 파서, 테스트 전용 KeyRegistry. 실제 격리 GAS 프로젝트에 수동으로 적용해 60건 실측에 쓰인 코드와 동일 로직(병합 과정에서 로직 변경 없음).

### 5-2. Node 테스트 하니스(`node_harness/`, 3개)
GAS 전용 서비스(Utilities/ContentService/CacheService/PropertiesService/LockService) 스텁, 실제 `doPost(e)`/`doGet(e)`를 호출하는 로컬 진입점 테스트(29개 검증), 그리고 기존 Python 드라이버가 실제 와이어 형식으로 때릴 수 있는 로컬 HTTP 서버. `node_gas_http_server.js`는 제외 대상인 병합 산출물(`concatenated_all_v2.js`)에 더 이상 의존하지 않도록 재작성했다(§3) — `gas_candidate/*.gs`를 직접 읽어 연결하므로, 저장소에 남는 소스와 실제로 실행되는 코드가 분리되지 않는다.

### 5-3. 로컬 드라이버·테스트(`local_verification/`, 16개)
Script Lock/Cache/Properties 시뮬레이션(3개), nonce TTL 경계 계산(1개), 서버 예산 가드(1개), 로컬 모의 서버(1개), 실제 동시 HTTP 드라이버(1개), 60건 실행 오케스트레이션(1개), 그리고 7개 pytest 테스트 파일(교차 파일 중복·전역 초기화 검증은 Node 쪽에 있어 여기서는 제외) = 9+7 = 16개. §3 재검증 결과 이 중 10개 파일(`concurrent_http_driver.py`, `local_mock_gas_server.py`, `real_execution_run.py`, `replay_guard.py`, `server_budget_guard.py`, `test_concurrent_http_driver_local.py`, `test_dry_run_full_sequence.py`, `test_preflight_action_binding.py`, `test_replay_guard_local.py`, `test_server_budget_guard.py`)는 이름만 바뀐 게 아니라 import 경로(`_new` 접미사 제거)와 일부는 절대 로컬 경로 수정이 추가로 반영됐다 — 바이트 단위로 완전히 동일한 것은 나머지 6개(`sim_cache_service.py`, `sim_properties_service.py`, `sim_script_lock.py`, `nonce_ttl_boundary.py`, 그리고 배너 2개 파일은 배너+경로수정이 함께 반영돼 별도 분류)뿐이다.

### 5-4. 실행 증적(`evidence/`, 1개)
실제 60건 실행의 원본 결과 JSON.

### 5-5. 제외한 것(이번에도 제외 유지)
- 병합용 단일 파일(v1/v2/v3 Code.gs 통합본) — 소스가 아니라 수동 적용 편의용 산출물.
- `concatenated_all*.js`, `full_entrypoint_test.js`, `test_combined.js`, `test_fixed.js`, `debug_combined.js` — 빌드/디버그 산출물.
- `debug_s7_timing.py`, `connectivity_check_*.py` — 1회성 디버그/연결확인 스크립트.
- `.clasp.json`, `~/.clasprc.json` — 프로젝트 식별자·인증 캐시.
- 실제(운영) secret·개인정보 — 존재하지 않음.

### 5-6. 합성 secret 포함 파일(4개) — 배너 추가 후 포함

다음 4개 파일에는 합성(synthetic) 테스트 secret 리터럴이 있으며, 각 파일 맨 위에 "테스트 전용·공개된 값·운영 재사용 금지" 배너를 추가했다:
```
gas_candidate/TestKeyRegistry.gs
node_harness/entrypoint_tests.js
local_verification/test_e2e_real_gas_code.py
local_verification/test_dry_run_v3_real_code.py
```
(원래 발견된 7개 중 3개— 빌드 산출물 2개, 디버그 파일 1개—는 §5-5에 따라 제외했다.)

### 5-7. 변경 요약(커밋 메시지 초안, 실행 안 함)

> Replay 격리 실험 격리 GAS A/B 실측: 누락된 parseJsonStrict_ 보완, 클라이언트 now/maxSkewSeconds 신뢰 제거(서버 시계·서버 상수만 사용), idempotency_key/key_id 필드명 수정, request.secret 의존 제거(서버 측 TestKeyRegistry 도입), 내부오류/입력오류 분류 추가. 로컬(Node/Python) 45건 이상 테스트 및 실제 격리 GAS 배포 대상 60건(exec 53+status 7, s1/s2/s4/s7) A/B 실측으로 검증 — 실제 검증 범위는 s1/s2/s4/s7로 한정되며, 캐시 유실 모사·장애 주입·서버 상한(80건) 초과 차단·운영 연동은 로컬 전용 또는 미검증 상태로 남음.

---

## 완료 보고 요약

- 60건(exec53+status7) 전부 원본 증적과 대조해 PASS, 실제 검증 범위는 s1/s2/s4/s7로 한정.
- 60(계획)과 80(서버 상한 하드코딩값)은 서로 다른 값으로만 기록 — 80의 사전 승인 여부는 미확인, 상한 차단 자체도 미검증.
- 실행에 쓰인 원본과 저장소 후보 파일의 SHA-256 추적 관계 유지(§3) — 이름만 바뀐 파일과 실제로 내용이 바뀐 파일(import/경로 수정 10개, 재작성 1개, 배너 추가 4개)을 구분해 기록.
- 공개 배포 보관 처리는 사용자 확인 사실로만 기록.
- 저장소 반영 후보 32개 파일 + 본 문서(1개) = 총 33개를 개발 worktree에 배치 완료.
- 원본 보호 파일(SSOT 문서 등)은 전혀 건드리지 않음.

**OFFICIAL PHASE 1 GATE = BLOCKED INPUT, 변경 없음.**
