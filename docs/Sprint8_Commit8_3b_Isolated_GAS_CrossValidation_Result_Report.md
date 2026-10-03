# Commit8-3b — 격리 GAS 교차검증 결과보고서

> **상태**: 이 보고서가 다루는 `protocolVersion="2"`(keyId 포함 9필드
> Canonical String)과 Option B(payload 정규화 가드: raw JSON 숫자
> 토큰·중복 키 검증, 요청별 스키마)는 **운영 ADR-017 개정이 확정되기
> 전까지는 운영 계약이 아닌 격리 개발 계약**이다. 이 보고서가 기록한
> PASS 결과는 "격리 테스트 프로젝트에서 합성 데이터로 수행한 검증"일
> 뿐, 운영 라우트·운영 Secret·운영 Sheets/CacheService와는 무관하다.
> **OFFICIAL PHASE 1 GATE = BLOCKED INPUT 유지.**
> 이 보고서와 재현용 코드·증적은 `tests/cross_validation/gas/`
> (재현용 6개 파일)와 `tests/cross_validation/gas/evidence/`(1회성
> 실행 증적 3개 파일)에 commit됐다. **push·main 병합·GAS 프로젝트
> 삭제·운영 연결·배포는 하지 않았다.**
> **작성일**: 2026-10-03

---

## 1. 실행 정보

| 항목 | 값 |
|---|---|
| 프로젝트명 | `CMC_HMAC_V2_ISOLATED_TEST` |
| Script ID | `1f8e3qCgMfd7vR5cq81Bqir_6RNf8Ux8pjTrD5-EhalIibO2OUCKXMXeD` |
| 실행 함수 | `runAllVectors`(`Main.gs`) |
| 실행 방식 | Apps Script 편집기에서 **사용자가 직접** 수동 실행(브라우저) — `clasp run`은 이전 시도에서 `Exception: ... Error code NOT_FOUND`로 실패해 중단했었고, 이번 결과는 그와 무관하게 편집기 수동 실행으로 얻은 것이다 |
| 실행 계정 | `smdwho4@gmail.com`(사전 확인 완료 — `clasp show-authorized-user`, 토큰 원문 미노출) |
| 실행 시각(사용자 보고) | 2026-10-03 13:31:28 KST |
| 사용 서비스 | `Utilities`, `Logger`만(업로드 전 `appsscript.json` `oauthScopes: []`, 코드 내 금지 서비스 호출 0건으로 확인 완료, 이전 턴 §2 재확인) |
| 권한 요청 여부 | 이번 실행에서 Sheets/Drive 등 계획 밖 권한 요청이 있었다는 보고 없음(사용자가 특이사항을 알리지 않음) |

## 2. 실행 로그 보존 — **전체 원문 확보 완료**(정정)

> **정정(이번 갱신)**: 이전 버전은 "요약만 확보, 전체 원문 미확보"
> 상태였다. 사용자가 Apps Script 실행 기록 화면의 **시작 줄부터
> 완료 줄까지 전체**(벡터 22개 개별 줄 포함)를 그대로 복사해
> 전달했고, 이를 `GAS_EXECUTION_RESULT_FULL_20261003.txt`에 한 글자도
> 수정하지 않고 보존했다. **"벡터별 원문을 받지 못함"이라는 이전
> 표현은 이제 사실이 아니므로 정정한다 — 전체 원문을 확보했다.**

**전체 로그 보존 파일**: `tests/cross_validation/gas/evidence/GAS_EXECUTION_RESULT_FULL_20261003.txt`
**SHA-256**: `728111b7394d0a5a0f4d577c99d7ca60b74f96b7b955567b04e8ebf9bc5c4213`(4,144 bytes) — 확인됨, 저장소 commit 전후 동일

전체 로그는 실행 시작 줄("실행이 시작됨"), 벡터 22개 개별
`Logger.log()` 줄(`[V01_ascii_normal] PASS [독립검증:OpenSSL]` 등),
`=== 요약 ===` 4줄, 완료 줄("실행이 완료됨")을 전부 포함한다. **V02
줄의 "[독립검증:OpenSSL]" 라벨도 원문 그대로 보존했다** — 이 라벨이
부정확하다는 설명은 로그 파일 자체에는 추가하지 않았고, 아래 §5에만
기록한다(사용자 지시 재확인 — 원문 보존과 오류 설명을 분리).

**참고(전체 로그에서 관찰된 사실, 추가 조사하지 않음)**: 요약 줄의
수치가 `12.0개`/`9.0개`/`1.0개`/`22.0개`/`0.0개`처럼 정수에 `.0`이
붙어 출력됐다 — 이전 턴의 Node 스텁 실행에서는 `12개`처럼 정수로
출력됐던 것과 다르다. 실제 GAS `Logger.log()`의 `%s` 치환이 숫자를
다루는 방식에서 비롯된 것으로 보이는 GAS 고유의 표시 특성으로
추정되며, 벡터별 PASS/FAIL 판정 자체에는 영향이 없다(22/22 PASS는
개별 줄 22개 전부가 "PASS"로 끝나는 것으로 직접 확인됨). 원인을
추가로 조사하지는 않았다.

**요약 파일(참고, commit 후보에서 제외됨)**: 이전에 받은 요약은
`GAS_EXECUTION_RESULT_SUMMARY_20261003.txt`에 그대로 남아 있으나,
전체 원문을 확보한 지금은 **중복 증적**이라 §8의 최종 commit
목록에서 제외했다(삭제하지 않고 scratchpad에는 남겨 둠).

## 3. 실제 GAS V8·Utilities 실행 결과 — 로컬 Node 스텁 결과와 구분

| 구분 | 실행 환경 | 결과 | 의미 |
|---|---|---|---|
| **이번 결과(§1~2)** | **실제 Google Apps Script V8 런타임**, 실제 `Utilities.computeHmacSha256Signature`/`computeDigest`/`JSON.stringify` | 22/22 PASS(사용자 직접 실행·보고) | **처음으로 실제 GAS Utilities가 Python/JS 교차검증 기대값과 바이트 단위로 일치함을 실측 확인**한 결과 |
| 이전 결과(참고용, 이전 턴) | `_gas_stub_harness.js` — Node `crypto`로 GAS Utilities를 **흉내 낸** 로컬 스텁(signed byte 변환까지 재현) | 22/22 PASS(로컬) | "포팅된 로직 자체가 논리적으로 올바른가"만 확인한 것 — 실제 GAS Utilities의 동작을 증명하지 않았음(이전 턴에 이미 명시) |

두 결과가 숫자(22/22)는 같지만 **완전히 다른 것을 증명한다** — 이번
결과가 나오기 전까지는 "실제 GAS V8이 Node/Python과 바이트 단위로
같다"는 것은 가설(§7의 실행계획 문서가 세운 가설)이었고, 이번이 그
가설을 실측으로 확인한 첫 결과다. 그렇다고 해도 이는 **이 22개
합성 벡터 범위 내의 확인**이며, GAS Utilities의 모든 입력 범위에서
Node/Python과 일치함을 일반적으로 증명하지는 않는다.

## 4. 검증 근거 구분 — MATCH(12) / 거절(9) / 필드거절(1)

| ID | 분류 | verificationBasis | 설명 |
|---|---|---|---|
| **V01** | MATCH | **INDEPENDENT_OPENSSL** | payloadHash `0928ae03...`·signature `8cab7d26...`가 Python/JS뿐 아니라 **제3자 도구(openssl CLI)로 독립 재계산**돼 일치 확인된 값(`CROSS_VALIDATION_REPORT.md` §2). **이번 GAS 실행 결과가 이 값과 일치했다는 것은 "GAS도 독립 검증된 정답과 일치"라고 말할 수 있는 유일한 벡터다.** |
| V03a, V03b, V05, V06, V08~V12, V14, V18(MATCH 나머지 11개) | MATCH | PYTHON_COMPARISON_ONLY | `python_output.json`에서 그대로 복사한 값과 GAS 결과가 일치 — "GAS가 Python 계산 결과와 같다"는 뜻, 독립 검증 아님 |
| **V02** | 거절(REJECT) | **PYTHON_COMPARISON_ONLY(정정)** | 아래 §5에서 별도로 상세히 다룬다 |
| V04, V13, V15~V17, V19~V21(거절 나머지 8개) | 거절(REJECT) | PYTHON_COMPARISON_ONLY | 거절 사유 코드가 Python 가드 결과와 일치 — 제어흐름(거절 여부)은 애초에 openssl 같은 크립토 도구로 독립 검증할 방법이 없음 |
| V07 | 필드거절 | PYTHON_COMPARISON_ONLY | `signV2_()`가 `FieldFormatError_`를 던지는지 확인 — 역시 제어흐름이라 독립 검증 대상 아님 |

**집계**: MATCH 12건 중 **독립 검증(OpenSSL) 1건(V01)** + Python 비교
11건, 거절 9건 전부 Python 비교, 필드거절 1건 Python 비교 — **총
22건 중 독립 검증은 V01 단 1건뿐**이다.

## 5. V02 라벨 오류 — 발견 경위와 정정

이전 턴에 준비한 `Expected.gs`에는 **V02가 (거절 카테고리임에도)
`verificationBasis: "INDEPENDENT_OPENSSL"`로 잘못 표기**되어 있었다.
이번 실제 GAS 실행 후 이 오류를 발견해 정정했다.

> **로그 원문과 이 설명의 관계(§2 재확인)**: `GAS_EXECUTION_RESULT_FULL_20261003.txt`의
> V02 줄은 실행 당시 그대로 `[V02_korean_unicode_payload] PASS
> [독립검증:OpenSSL] (reason=UNICODE_OR_INVALID_OBJECT_KEY)`로
> 보존되어 있다 — **이 로그 파일 자체는 수정하지 않았다.** 아래
> 설명은 "왜 그 라벨이 부정확한가"를 이 보고서에서만 다룬다.

- **왜 틀렸는가**: V02의 payloadHash/signature(한글 object key를
  포함한 payload를 서명했다고 가정했을 때의 크립토 값)는 과거
  (Option B 가드 도입 전) `CROSS_VALIDATION_REPORT.md` §2에서
  openssl로 독립 재계산해 확인한 적이 **있다**. 하지만 **지금
  `EXPECTED_REJECT`에서 실제로 검사하는 것은 그 크립토 값이 아니라
  "Option B 가드가 이 입력(한글 object key)을 거절하는가"라는 전혀
  다른 판정**이다. 거절/수용 같은 제어흐름은 openssl로 독립 검증할
  방법이 없다 — openssl은 "주어진 바이트에 대한 해시·서명이 맞는가"만
  계산할 수 있지, "이 코드가 이 입력을 거부하는가"는 검증할 수 없다.
- **정정 내용**: `Expected.gs`의 `EXPECTED_REJECT.V02_korean_unicode_payload.verificationBasis`를
  `"PYTHON_COMPARISON_ONLY"`로 수정했다(§8 "변경 파일" 참조). 이
  수정은 **코드를 재실행하지 않고** 정적 데이터 라벨만 고친 것이다.
- **결론**: **V02의 현재 결과("UNICODE_OR_INVALID_OBJECT_KEY 거절
  성공")는 OpenSSL 독립 검증 대상이 아니며, 그렇게 표시되어서도 안
  된다.** V02의 과거 크립토 값에 대한 OpenSSL 검증 자체는 여전히
  유효한 사실이지만, 이번 거절 판정과는 별개의 기록이다.

### 5-1. 실행본(AS_EXECUTED) 복구 및 diff 확인(이번 갱신)

2026-10-03 13:31:28 KST 실행 당시 GAS 프로젝트에 올라가 있던 코드는
**아직 덮어쓰지 않았으므로**(수정 후 재push하지 않음), `clasp pull`
(읽기 전용 다운로드, GAS 재실행 아님)로 그대로 복구할 수 있었다.

```
clasp pull (scriptId: 1f8e3qCgMfd7vR5cq81Bqir_6RNf8Ux8pjTrD5-EhalIibO2OUCKXMXeD)
→ appsscript.json, Code.js, Fixtures.js, Expected.js, Main.js 5개 파일 복구
```

**복구된 실행본의 SHA-256(해시는 실제 복구 결과에서 직접 계산, 추정
아님):**

| 파일 | 실행본(AS_EXECUTED) SHA-256 | 현재 로컬본과 동일? |
|---|---|---|
| `appsscript.json` | `ba2ddcd48af07ac4f8b9bd4efba4aee2c3aab7af1cb5806de8deeb1791f52885` | 동일(변경 없음) |
| `Code.gs` | `3bfcf50d8a9369eaec7c15e9f680213c883721552e6f55af5745e9781158ced4` | 동일(변경 없음) |
| `Fixtures.gs` | `86125fd42c40f269159509b94734ed621358d93f04d52be93bb42b760d01ecfd` | 동일(변경 없음) |
| `Main.gs` | `5bbea5929d70746b0f5c4ed6d1e080433e18990a4d557bf42686e66c819fe51d` | 동일(변경 없음) |
| **`Expected.gs`** | **`bcb4b11d40f43692eb34f2c61a8738d388e22096f18522dc4fdd991d58787e1f`**(11,332 bytes) | **다름** — 현재 라벨 정정본은 `f7bb2baa7a442919e4e0c2dcb44a44cda1d1951db1c059e965c1f7aec727a5af`(12,309 bytes) |

→ `Code.gs`/`Fixtures.gs`/`Main.gs`/`appsscript.json`은 실행 전후
**한 번도 수정하지 않았으므로** 해시가 동일함이 그대로 증명됐다.
**`Expected.gs`만 실행 후에 수정했다** — 실행 당시 버전(위 표의
`bcb4b11d...`)과 현재 라벨 정정본(`f7bb2baa...`)은 **서로 다른 파일로
구분 보존**했다. **현재 정정본의 해시를 실행 당시 해시로 기록하지
않는다** — 위 표가 두 값을 명확히 분리해 기록한다.

**diff 확인 결과**(`Expected_AS_EXECUTED_20261003.gs` ↔ 현재
`Expected.gs`): 변경은 정확히 두 곳뿐이었다 —
(1) 파일 상단 주석(기대값 원천 설명 보강, 실행에 영향 없는 주석),
(2) `EXPECTED_REJECT.V02_korean_unicode_payload.verificationBasis`
값 `"INDEPENDENT_OPENSSL"` → `"PYTHON_COMPARISON_ONLY"`. **그 외
어떤 줄도 변경되지 않았다** — `EXPECTED_MATCH`의 해시값들,
`EXPECTED_REJECT`의 reason 코드들, `EXPECTED_FIELD_REJECTION` 전부
한 글자도 바뀌지 않았다(diff 전체 출력에서 직접 확인). **이 수정은
라벨·근거 메타데이터뿐이며, GAS를 재실행하지 않았다.**

**보존 파일**: 실행본은
`tests/cross_validation/gas/evidence/Expected_AS_EXECUTED_20261003.gs`
(표시: "2026-10-03 13:31:28 KST 실행 당시 버전 — V02가
INDEPENDENT_OPENSSL로 잘못 표시됨")로, 정정본은
`tests/cross_validation/gas/Expected.gs`(표시: "실행 후 라벨 정정,
GAS 재실행하지 않음")로 구분 보존했다.

## 6. 이번 검증이 포함하지 않는 것(범위 밖, 재확인)

- **nonce 저장소(SQLite)·실제 GAS CacheService 검증**: 포함하지 않음.
  `FakeSecondaryNonceStore`가 실제 CacheService의 원자성·LRU
  eviction·TTL 특성과 얼마나 다른지는 PoC#2가 이미 지적한 별도
  과제이며, 이번 GAS 교차검증 범위 밖이다(실행계획 §9 재확인).
- **운영 예약 경로 검증**: 포함하지 않음. 이번 테스트 프로젝트는
  `Utilities`/`Logger`만 쓰는 standalone 스크립트이며, 어떤
  Spreadsheet·운영 예약 데이터에도 접근하지 않았다(`appsscript.json`
  `oauthScopes: []`, 코드 내 `SpreadsheetApp`/`DriveApp` 등 호출 0건,
  이전 턴 정적 검사로 확인).
- **실제 운영 Secret**: 사용하지 않음. `Fixtures.gs`의
  `SYNTHETIC_KEYS`는 `tests/cross_validation/keys_v2.json`과 동일한
  합성 테스트 Secret뿐이다.

## 7. protocolVersion=2 / Option B의 계약 지위(재확인)

이 보고서가 검증한 9필드 Canonical String(`protocolVersion="2"`,
keyId 포함)과 Option B의 payload 정규화 규칙(raw JSON 숫자 토큰·중복
키 검증, 요청별 스키마)은 **ADR-017의 공식 개정 전까지는 운영 계약이
아닌 격리 개발 계약**이다(`Commit8_3b_HMAC_Nonce_V2_Contract_Draft.md`,
`Commit8_3b_Payload_Normalization_Policy_Proposal.md` 재확인). 이번
GAS 실행 결과는 이 개발 계약의 **구현 충실도**를 확인한 것이지, 그
계약을 운영 계약으로 승격시키지 않는다.

## 8. 저장소에 보존한 파일 목록(commit 완료 — push는 하지 않음)

> 아래는 **실제로 commit된 최종 저장소 경로**다(출처: scratchpad의
> `gas_cross_validation_package/`). `.clasp.json`(scriptId가 포함된
> 프로젝트 연결 파일), clasp 인증 캐시(`~/.clasprc.json`), 실제
> secret은 **포함하지 않았다** — 전부 합성 데이터와 재현용 코드만
> 해당한다.

| 저장소 경로(최종) | SHA-256 |
|---|---|
| `tests/cross_validation/gas/appsscript.json` | `ba2ddcd48af07ac4f8b9bd4efba4aee2c3aab7af1cb5806de8deeb1791f52885` |
| `tests/cross_validation/gas/Code.gs` | `3bfcf50d8a9369eaec7c15e9f680213c883721552e6f55af5745e9781158ced4` |
| `tests/cross_validation/gas/Fixtures.gs` | `86125fd42c40f269159509b94734ed621358d93f04d52be93bb42b760d01ecfd` |
| `tests/cross_validation/gas/Expected.gs`(표시: "실행 후 라벨 정정, GAS 재실행하지 않음") | `f7bb2baa7a442919e4e0c2dcb44a44cda1d1951db1c059e965c1f7aec727a5af` |
| `tests/cross_validation/gas/Main.gs` | `5bbea5929d70746b0f5c4ed6d1e080433e18990a4d557bf42686e66c819fe51d` |
| `tests/cross_validation/gas/README.md` | (실행 절차 문서, 해시 생략 — 코드/fixture가 아님) |
| `tests/cross_validation/gas/evidence/Expected_AS_EXECUTED_20261003.gs`(표시: "2026-10-03 13:31:28 KST 실행 당시 버전 — V02가 INDEPENDENT_OPENSSL로 잘못 표시됨") | `bcb4b11d40f43692eb34f2c61a8738d388e22096f18522dc4fdd991d58787e1f` |
| `tests/cross_validation/gas/evidence/GAS_EXECUTION_RESULT_FULL_20261003.txt` | `728111b7394d0a5a0f4d577c99d7ca60b74f96b7b955567b04e8ebf9bc5c4213`(4,144 bytes) |
| `tests/cross_validation/gas/evidence/EXECUTION_LOG.md` | (프로젝트 생성·업로드·`clasp run` 실패·`clasp pull` 복구 기록, 해시 생략) |
| `docs/Sprint8_Commit8_3b_Isolated_GAS_CrossValidation_Result_Report.md` | 이 문서 |

**commit에서 제외**: `GAS_EXECUTION_RESULT_SUMMARY_20261003.txt`
(사용자 제공 요약 — 전체 원문 확보 후 **중복 증적**이 되어 제외.
scratchpad에는 남겨 둠, 저장소에는 넣지 않음). `.clasp.json`(scriptId
포함 프로젝트 연결 파일), clasp 인증 캐시(`~/.clasprc.json`), 실제
secret, `python_output.json`/`js_output.json`(자동 생성 재현 가능
출력) — 전부 제외.

**commit된 파일: 정확히 10개**(`appsscript.json`, `Code.gs`,
`Fixtures.gs`, `Expected.gs`, `Main.gs`, `README.md`,
`evidence/Expected_AS_EXECUTED_20261003.gs`,
`evidence/GAS_EXECUTION_RESULT_FULL_20261003.txt`,
`evidence/EXECUTION_LOG.md`, 이 결과보고서).

**기대값(`Expected.gs`)의 출처**: `EXPECTED_MATCH`/`EXPECTED_REJECT`/
`EXPECTED_FIELD_REJECTION`의 모든 값은 `tests/cross_validation/python_output.json`
(기존 Python/JS 교차검증 실행 결과, worktree에 존재하나 재현
가능하므로 비commit 대상)에서 transcribe한 것이며, 생성 스크립트는
`_gen_gas_package.py`(scratchpad에만 보관, 재현용·비commit 대상)다.
**V01 단 한 값만** 추가로 `openssl` CLI 독립 재계산을 거쳤다(§4~5).
`Fixtures.gs`의 22개 벡터는 `tests/cross_validation/fixtures_v2.json`/
`keys_v2.json`에서 그대로 옮긴 것이며 값 변경이 없다.

## 9. 남은 과제

1. `clasp run`(API 기반 원격 실행)이 `Error code NOT_FOUND`로 실패한
   원인 규명 — Apps Script API 사용자 설정 또는 전파 지연으로
   추정되나 확인하지 않았다(`EXECUTION_LOG.md` 재확인). 이번엔 편집기
   수동 실행으로 우회했다.
2. ~~벡터별 원문 Logger 출력 22줄을 포함한 전체 실행 로그 확보~~ —
   **완료**(§2, `GAS_EXECUTION_RESULT_FULL_20261003.txt`로 보존, 해시
   확인 완료).
3. ~~저장소 commit 여부·경로 승인~~ — **완료**(§8, 10개 파일 commit
   됨). Push·main 병합은 아직 별도 승인 필요(미수행).
4. §6 범위 밖 항목(CacheService·운영 예약 경로)의 검증은 별도
   PM 승인·별도 계획이 필요하다(기존 지적 재확인).
5. 요약 줄 수치의 `.0` 표시 현상(§2 "참고")은 추가 조사하지 않았다 —
   필요하면 별도로 확인할 수 있다.

---

**완료 조건 재확인**: §8의 10개 파일을 개발 브랜치에 commit했다.
프로젝트 삭제·push·main 병합·운영 연결·배포는 하지 않았다. 추가
GAS 실행·추가 Node 스텁 재실행을 하지 않았다(Expected.gs의 V02
수정은 정적 라벨 교정이며 크립토 재계산이 아니다). **OFFICIAL PHASE
1 GATE는 BLOCKED INPUT으로 유지된다.**
