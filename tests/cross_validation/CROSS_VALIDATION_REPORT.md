# Commit8-3b HMAC v2 — Python/JavaScript 교차검증 보고서

> **상태**: 격리 개발·로컬 전용 교차검증이다. 운영 라우트에 연결되지 않았고,
> 실제 GAS(Google Apps Script) Rhino/V8 런타임·CacheService·Sheets에
> 접근하지 않았다. 이 보고서의 PASS는 **"Node.js 표준 crypto 구현이
> Python 구현과 합치한다"**는 의미이며, **"GAS Utilities 서비스가
> 동일하게 동작함을 검증했다"는 의미가 아니다**(아래 "실제 GAS
> 교차검증에 남은 사항" 참조). OFFICIAL PHASE 1 GATE는 BLOCKED INPUT을
> 유지한다.
>
> **[3차 갱신] V04 해결 + 요청별 스키마 가드 + 서명 전 wrapper(§9 신설)**:
> JS 커스텀 토크나이저와 Python `json.loads(parse_int=/parse_float=)`
> 훅으로 **raw JSON 경로**를 추가해 숫자 토큰(소수점·지수 유무)을
> 원문 그대로 검사하도록 바꿨다. 그 결과 **V04도 RESOLVED_REJECTED로
> 전환**됐다 — 최종 **MATCH 13 / RESOLVED_REJECTED 9 / UNRESOLVED 0**.
> "이미 파싱된 객체 경로"만으로는 여전히 1과 1.0을 구분 못 한다는
> 한계 자체는 실측으로 재확인·유지했다(raw 경로를 먼저 거치면 문제
>없음). 요청별 스키마 가드(`request_payload_schemas.py`/`.js`)와
> 서명 전 wrapper(`signing_v2_guarded.py`/`.js`)를 추가했다 — 상세는
> §9.
>
> **[2차 갱신] Option B 가드 구현 결과(§8)**: `payload_schema_guard.py`/
> `.js`를 구현해 22개 벡터로 확장 재검증했던 중간 결과(MATCH 13 /
> RESOLVED_REJECTED 8 / UNRESOLVED 1 — V04)는 §9의 raw JSON 경로
> 도입으로 갱신됐다(위 참조).
>
> **[1차] 핵심 요약(과대 해석 방지)**: 최초 15개 벡터 중 DETERMINED
> 13개는 전부 MATCH, UNRESOLVED 2개(V04/V13)는 "예상대로 불일치
> 확인"이었다. 미확정 2건의 정책 결정은
> `docs/Commit8_3b_Payload_Normalization_Policy_Proposal.md`(별도
> 제안서)에서 다뤘다.
>
> **작성일**: 2026-10-03(최초) / 2026-10-03(명확화 보완) /
> 2026-10-03(Option B 가드 구현 결과 반영) /
> **기준 commit**: `c3ea4dd7d21970198225cd18e83cea9e89ef111f`(가드 구현
> 자체는 아직 commit되지 않음, 작업트리 상태)

---

## 1. 구성 파일

| 파일 | 역할 |
|---|---|
| `keys_v2.json` | 양쪽 언어가 공유하는 키 레지스트리(`key-active`/`key-grace`), `now`/`max_skew_seconds`. **여기 담긴 키 2개(`xval-cross-secret-active-0001`, `xval-cross-secret-grace-0002`)는 전부 이 교차검증 전용 합성 테스트 Secret이며, 운영 Secret이 아니다**(파일 자체의 `_comment` 필드에도 명시됨). |
| `fixtures_v2.json` | 15개 공유 입력 벡터. 기대값은 포함하지 않는다(한쪽 구현 출력을 기대값으로 자동 채택하지 않기 위함) |
| `reference_signing_v2.js` | `src/idempotency/signing_v2.py`와 동일 계약을 기준으로 독립 작성한 Node.js 참조 구현(Node 표준 `crypto`만 사용) |
| `run_python_side.py` | 실제 `signing_v2.py`를 호출해 `python_output.json` 생성 |
| `run_js_side.js` | `reference_signing_v2.js`를 호출해 `js_output.json` 생성 |
| `compare_outputs.py` | 두 출력을 필드별 비교, DETERMINED/UNRESOLVED 벡터를 구분해 판정 |

## 2. 기대값 산출 근거 — 어느 쪽 구현 출력도 "정답"으로 자동 채택하지 않음

**V01(ASCII)·V02(한글) 2개 벡터에 한정해** Python도 JS도 아닌 제3의
독립 도구(`openssl` CLI, 3.5.6)로 SHA-256/HMAC-SHA256을 직접
재계산해 두 구현의 출력과 모두 일치하는지 확인했다. **나머지 13개
벡터는 openssl 독립 재계산을 거치지 않았다** — 절차: Python 실행
결과에서 나온 `payloadUtf8Hex`/`canonicalUtf8Hex`(16진 문자열)를
`bytes.fromhex()`로 순수 디코딩(이 단계는 crypto 연산이 아니라 인코딩
변환일 뿐)해 이진 파일로 저장한 뒤, `openssl dgst -sha256`과
`openssl dgst -sha256 -hmac <secret>`으로 독립 재계산했다.

| 벡터 | 값 | Python/JS 구현 출력 | openssl 독립 재계산 | 일치 |
|---|---|---|---|---|
| V01 | payloadHash | `0928ae0342e9029315c5b7be4fc30c54a914b89aa9bc2d3152fb446ee4b64847` | 동일 | ✅ |
| V01 | signature | `8cab7d261ec5101917b2df75f260b7a18b16982e3d0eb995918a71c97aa193db` | 동일 | ✅ |
| V02 | payloadHash | `2e88ce2c9dd959a985328e628ebda17237e00a27f41717d293cc623d713751a3` | 동일 | ✅ |
| V02 | signature | `20a9f86ff8d5c965085060054e4453dc4ed909b5661ff9cde53728966947934c` | 동일 | ✅ |

**나머지 13개 벡터(V03~V14)는 "Python 구현 vs JS 참조구현"의 상호
일치로만 검증했다** — openssl 등 제3의 도구로 개별 재계산하지
않았다. V01/V02에서 확인한 신뢰(같은 알고리즘 경로가 제3자 도구와
일치)를 근거로 나머지 벡터까지 확장 추정한 것일 뿐, 13개 전부를
개별적으로 독립 재계산한 것은 아니라는 점을 명확히 한다. 검증용
스크래치 파일(`_v01_*.hex/.bin` 등)은 확인 직후 삭제했다 — 저장소에
남기지 않는다.

## 3. 벡터별 결과

`python3 tests/cross_validation/compare_outputs.py` 실행 결과(exit code 0):

| ID | 범주 | determinacy | 결과 |
|---|---|---|---|
| V01_ascii_normal | 정상 ASCII | DETERMINED | ✅ MATCH (ACCEPTED, openssl 교차확인) |
| V02_korean_unicode_payload | 한글·Unicode payload | DETERMINED | ✅ MATCH (ACCEPTED, openssl 교차확인) |
| V03a/V03b_payload_key_order | 객체 키 순서 | DETERMINED | ✅ MATCH (ACCEPTED, 양쪽 모두 동일 payloadHash) |
| V04_payload_number_type_ambiguity | 숫자 표현 | **UNRESOLVED** | ⚠️ 예상대로 불일치 확인(아래 §4) |
| V05_payload_whitespace_preserved | 문자열 공백 | DETERMINED | ✅ MATCH (ACCEPTED, 공백 보존 확인) |
| V06_payload_null_value | null 처리 | DETERMINED | ✅ MATCH (ACCEPTED) |
| V07_field_newline_injection_rejected | 개행 삽입 거절 | DETERMINED | ✅ MATCH (양쪽 모두 서명 단계에서 FieldFormatError) |
| V08_field_safe_token_chars_allowed | 안전 문자 허용 | DETERMINED | ✅ MATCH (ACCEPTED) |
| V09_keyid_tamper | keyId 변조 | DETERMINED | ✅ MATCH (SIGNATURE_MISMATCH) |
| V10_payload_tamper | payload 변조 | DETERMINED | ✅ MATCH (SIGNATURE_MISMATCH) |
| V11_signature_tamper | 서명 변조 | DETERMINED | ✅ MATCH (SIGNATURE_MISMATCH) |
| V12_protocol_version_mismatch_no_fallback | 버전 불일치 | DETERMINED | ✅ MATCH (PROTOCOL_VERSION_MISMATCH, fallback 코드경로 없음 확인) |
| V13_unicode_surrogate_key_sort_order | Unicode 키 정렬 | **UNRESOLVED** | ⚠️ 예상대로 불일치 확인(아래 §4) |
| V14_nfc_normalization_consistency | NFC 정규화 | DETERMINED | ✅ MATCH (ACCEPTED, NFD 입력이 정규화되어 정상 처리) |

**집계: 총 15개 벡터 — DETERMINED 13 MATCH / UNRESOLVED 2(예상대로
불일치 확인)**, 예상 밖 결과 0건.

> **"PASS"의 정확한 의미 재확인**: `compare_outputs.py`의 exit code 0은
> (a) DETERMINED로 분류한 13개 벡터가 전부 Python/JS 간 실제로
> 일치했고, (b) UNRESOLVED로 분류한 2개 벡터가 "예상대로" 불일치했음을
> 뜻할 뿐이다. **이 DETERMINED/UNRESOLVED 분류 자체가 이 구현의
> 판단**이며, ADR-017이나 제3의 표준 기구가 확정한 분류가 아니다.
> 따라서 exit 0 = "payload 정규화 계약 전체가 검증 완료"가 아니라,
> "이 보고서가 세운 현재 분류 기준을 충족했다"로 읽어야 한다.

## 4. 미확정(UNRESOLVED)으로 보고하는 2개 벡터 — 임의로 규칙을 정하지 않음

### V04 — JSON 숫자 리터럴의 int/float 구분
계약 초안(§3)은 `payloadHash` 직렬화 규칙(`sort_keys` + compact + NFC)만
정의했고, 숫자 리터럴의 언어 간 표현 방식은 정의하지 않았다. 입력
`{"count": 1.0}`에 대해:
- Python: `json.dumps`가 float `1.0`을 `"1.0"`으로 직렬화 → payloadHash가 Python 고유값
- JS: 숫자 타입이 하나뿐이라 `1.0`과 `1`을 구분하지 못하고 `"1"`로 직렬화 → payloadHash가 Python과 다름

**이 구현은 어느 쪽이 "맞는 정규화"인지 정하지 않았다.** 해결 방향은
별도 제안서 `docs/Commit8_3b_Payload_Normalization_Policy_Proposal.md`
참조(RFC 8785/JCS 1차 자료 확인 포함).

### V13 — 유니코드 키 정렬 시 코드포인트 vs UTF-16 코드 유닛
계약은 "유니코드 코드포인트순 정렬"이라고만 명시했다. Python의 `str`
비교는 실제 코드포인트 기준이지만, JS의 기본 문자열 비교(`<`)는 UTF-16
코드 유닛 기준이다. 입력 payload에 사용자 정의 영역 문자(U+E000)와
이모지(U+1F642, 😀)를 키로 함께 넣으면:
- Python: U+E000(코드포인트 57344)이 😀(코드포인트 128512)보다 작아 U+E000이 먼저 정렬됨
- JS: 😀의 선행 서로게이트 코드유닛(0xD83D=55357)이 U+E000(57344)보다 작아
  **반대로** 😀이 먼저 정렬됨

두 언어의 정렬 순서가 실제로 반대로 나옴을 실측으로 확인했다(실무에서는
드문 입력이지만, Private Use Area 문자나 특수기호를 payload 키로 쓰면
이론상 발생 가능). **이 구현은 "코드 유닛 기준"과 "진짜 코드포인트
기준" 중 어느 쪽을 계약으로 확정할지 임의로 정하지 않는다.** 해결
방향은 위와 동일하게 별도 제안서 참조(RFC 8785 §3.2.3은 **코드 유닛
기준**을 표준으로 명시함 — 제안서 §2-1 인용).

## 5. 생성 출력 파일 점검 — 로컬 경로·secret 노출 여부

`python_output.json`/`js_output.json`을 `cmcsh`(사용자 홈 디렉터리
흔적), `xval-cross-secret`(합성 Secret 원문), `C:\Users`(절대 로컬
경로) 패턴으로 검색한 결과 **어느 패턴도 검출되지 않았다** — 두
출력 파일에는 payload·canonical string·해시·서명 등 암호화 결과값과
벡터 식별자만 들어 있으며, 로컬 경로나 Secret 원문이 노출되지 않는다.
(harness 스크립트가 콘솔에 `print(f"wrote {out_path} ...")`로 절대
경로를 출력하지만, 이는 실행 로그일 뿐 파일 내용에는 포함되지 않는다.)

## 6. 테스트 명령·결과

```
# 교차검증 생성·비교
python3 tests/cross_validation/run_python_side.py   # 15 vectors -> python_output.json
node    tests/cross_validation/run_js_side.js        # 15 vectors -> js_output.json
python3 tests/cross_validation/compare_outputs.py    # exit 0 (DETERMINED 불일치 0, UNRESOLVED 미확인 0)

# 관련 회귀(기존 62개 — 교차검증 추가로 인한 영향 없음 확인)
python3 -m unittest tests.test_idempotency_store tests.test_gas_orchestration tests.test_signing_v2 tests.test_nonce_store
# -> Ran 62 tests ... OK
```

## 7. 실제 GAS 교차검증에 남은 사항(Open Question, 미해결)

이 교차검증이 **증명하지 않는** 것:
1. 실제 GAS(V8 런타임, 2026년 기준) `Utilities.computeHmacSha256Signature()`가
   Node.js `crypto.createHmac`과 바이트 단위로 동일하게 동작하는지 — 둘 다
   HMAC-SHA256 표준을 구현하지만, GAS 측 API의 입력/출력 인코딩 처리
   방식(Byte[] 배열 반환, 부호있는 byte 등 Apps Script 고유 이슈)은
   별도로 확인해야 한다.
2. GAS 서버(V8)의 `JSON.stringify` 키 순서·숫자 직렬화가 이 Node.js
   참조 구현과 동일한지 — V8 엔진 계열이라 유사할 가능성이 높지만
   실측하지 않았다.
3. 한글 등 Unicode 문자열에 대한 GAS의 내부 인코딩(Apps Script는 UTF-16
   기반 JavaScript 문자열을 쓰지만, Sheets/Properties 저장 시 추가
   변환이 있을 수 있음) — 미확인.
4. PoC#2가 이미 지적한 CacheService 원자성·LRU eviction 특성(nonce_store.py
   docstring 재확인) — 이번 교차검증 범위 밖.

→ 운영 통합 전, **별도 PM 승인 하에 격리 GAS 환경에서 PoC#2급 실측**이
필요하다(이 보고서의 PASS로 대체할 수 없음).

## 8. Option B 가드 구현 결과(제안서 승인 후 구현 — 본 갱신)

`docs/Commit8_3b_Payload_Normalization_Policy_Proposal.md`의 Option B
권고안을 실제 구현했다: `src/idempotency/payload_schema_guard.py`(Python,
신규 파일, `signing_v2.py` 미수정)와
`tests/cross_validation/payload_schema_guard.js`(JS 참조구현, 중복 키
탐지를 위한 자체 recursive-descent JSON 파서 포함). 기존 22개
벡터(V01~V14 + 신규 V15~V21)에 가드를 적용해 재검증했다.

### 8-1. 벡터별 MATCH / RESOLVED_REJECTED / UNRESOLVED

`python3 tests/cross_validation/compare_outputs.py` 실행 결과(exit code 1 — 아래 UNRESOLVED 1건 때문):

| ID | 결과 | 비고 |
|---|---|---|
| V01, V03a, V03b, V05, V06, V07, V08, V09, V10, V11, V12, V14, V18 | **MATCH**(13건) | 가드 통과 + 기존 해시/canonical/서명/검증 결과 전부 일치 |
| V02 | **RESOLVED_REJECTED** | 한글 object key → 가드가 양쪽 언어 모두 `UNICODE_OR_INVALID_OBJECT_KEY`로 거절(실제 스키마엔 Unicode 키가 없으므로 기능 영향 없음, V18이 "한글 값은 OK"를 별도 확인) |
| V13 | **RESOLVED_REJECTED** | surrogate pair 키 → 양쪽 언어 모두 `UNICODE_OR_INVALID_OBJECT_KEY`로 거절 — "어느 정렬이 맞는가"라는 질문 자체가 소멸 |
| V15(안전정수범위 초과) | **RESOLVED_REJECTED** | `INTEGER_OUT_OF_SAFE_RANGE` 양쪽 일치 |
| V16(중첩 배열 내 float) | **RESOLVED_REJECTED** | `FLOAT_NOT_ALLOWED` 양쪽 일치, 경로(`$.items[1].price`)까지 일치 |
| V17(중첩 객체 내 Unicode 키) | **RESOLVED_REJECTED** | `UNICODE_OR_INVALID_OBJECT_KEY` 양쪽 일치, 경로 일치 |
| V19(평면 중복 키), V20(중첩 중복 키) | **RESOLVED_REJECTED** | 원시 JSON 텍스트 단계에서 `DUPLICATE_KEY` 양쪽 일치(Python `object_pairs_hook`, JS 자체 토크나이저) |
| V21(최상위가 배열) | **RESOLVED_REJECTED** | `TOP_LEVEL_PAYLOAD_MUST_BE_OBJECT` 양쪽 일치 |
| **V04**(`{"count": 1.0}`) | **UNRESOLVED** | 아래 8-2 "구현이 막힌 지점" 참조 — 해결되지 않음 |

**집계: 총 22개 벡터 — MATCH 13 / RESOLVED_REJECTED 8 / UNRESOLVED 1.**

### 8-2. 구현이 막힌 지점(명시적으로 보고 — 임의로 규칙을 만들어 통과시키지 않음)

**파일**: `tests/cross_validation/payload_schema_guard.js`, 함수
`checkValue()`의 `FLOAT_NOT_ALLOWED` 분기(`!Number.isInteger(value)`).
**관련 조항**: 제안서(`Commit8_3b_Payload_Normalization_Policy_Proposal.md`)
§4의 가드 의사코드 — "숫자 값이 int가 아니면(float이면) 거절"이라는
설계가 JS에서는 구조적으로 재현 불가능한 부분이 있음을 구현 중 처음
발견했다.

- **막힌 항목**: `{"count": 1.0}`(V04)에서 Python 가드는
  `FLOAT_NOT_ALLOWED`로 정확히 거절하지만, JS 가드는 **통과(ACCEPTED)**
  시킨다.
- **왜 막혔는가**: JS에는 int/float이 구분된 타입으로 존재하지 않는다.
  `1.0`은 `JSON.parse()`를 통과하는 순간 `1`과 완전히 동일한 `Number`가
  되어(`Object.is(1.0, 1) === true`, `Number.isInteger(1.0) === true`),
  "원본 JSON 텍스트에 소수점이 있었는가"라는 정보 자체가 복구
  불가능하게 사라진다. 이미 파싱된 JS 값만 검사하는 한 코드를 아무리
  고쳐도 이 서브케이스는 걸러낼 수 없다 — **버그가 아니라 언어
  차원의 한계**다.
- **이 한계는 "숫자형 전체"가 아니라 "정수값을 가진 float"에만
  한정된다**: 소수부가 실제로 0이 아닌 float(예: V16의 `10.5`)은
  `Number.isInteger()`가 정확히 `false`를 반환해 **정상 거절되며,
  양쪽 언어가 일치함을 V16에서 실측 확인했다.**
- **가능한 해결 경로(이번 턴에 구현하지 않음)**: 모든 payload 수신
  지점에서 표준 `JSON.parse()`를 전혀 쓰지 않고, 이 모듈이 중복 키
  탐지에 쓰는 것과 같은 커스텀 토크나이저(숫자 리터럴의 원본 텍스트를
  보존)를 유일한 파싱 진입점으로 강제해야 한다. 이는 가드 함수 하나를
  고치는 수준을 넘어 **payload 수신 아키텍처 전체를 바꾸는 결정**이라
  이번 턴 범위를 벗어나며, 운영 정책으로 임의 확정하지 않는다(지시
  재확인). 결정은 ADR 개정 논의로 넘긴다.
- **결론(이번 갱신으로 해소 — §9 참조)**: 위 분석 당시에는 V04가
  **여전히 UNRESOLVED**로 남았으나, §9에서 raw JSON 경로를 추가해
  "이미 파싱된 값"이 아니라 **원시 토큰 문자열**을 직접 검사하도록
  바꾸면서 해결했다. `fixtures_v2.json`의 해당 벡터는 이제
  `knownImplementationBlocker`가 아니라 `rawJsonText`/
  `legacyParsedObjectPathStillUnresolved` 필드를 쓴다 — 아래 §9-1
  참조. 이 섹션(8-2)은 "왜 이전엔 안 됐는가"를 보여주는 역사적
  기록으로 남긴다.

### 8-3. 테스트 명령·결과(Option B 포함 전체 재실행)

```
python3 tests/cross_validation/run_python_side.py   # 22 vectors -> python_output.json
node    tests/cross_validation/run_js_side.js        # 22 vectors -> js_output.json
python3 tests/cross_validation/compare_outputs.py    # exit 1 (UNRESOLVED 1건: V04)

python3 -m unittest tests.test_idempotency_store tests.test_gas_orchestration \
  tests.test_signing_v2 tests.test_nonce_store tests.test_payload_schema_guard
# -> Ran 79 tests ... OK (기존 62 + 신규 가드 단위테스트 17)
```

### 8-4. 출력 파일 재점검

`python_output.json`/`js_output.json`(갱신판)을 다시
`cmcsh`/`xval-cross-secret`/`C:\Users` 패턴으로 검색한 결과 역시
검출되지 않았다 — §5의 점검 결과가 이번 갱신 후에도 유지된다.

## 9. V04 해결 + 요청별 스키마 가드 + 서명 전 wrapper(3차 갱신)

### 9-1. V04 해결 — raw JSON 경로 도입

**파일**: `src/idempotency/payload_schema_guard.py`(신규 `parse_json_strict`,
`_normalize_int_token`, `_reject_float_token`, `RawNumberFormatError`),
`tests/cross_validation/payload_schema_guard.js`(토크나이저의 숫자
브랜치 수정, `RawNumberFormatError` 추가, `parseJsonStrict` 신설).

- **Python**: `json.loads(raw, parse_int=..., parse_float=...)` 훅을
  사용했다 — Python 스캐너는 소수점·지수 표기가 있는 토큰에 대해서만
  `parse_float`를 호출하므로, 이 훅에서 무조건 거절하면 **원시 토큰
  문자열**(`"1.0"`)을 근거로 정확히 판정할 수 있다. `parse_int`는
  개발 계약(`-?(0|[1-9][0-9]*)`)을 재검증한 뒤 `int()`로 변환한다
  (`int("-0") == 0`이라 -0은 자동으로 정규화됨).
- **JS**: 커스텀 토크나이저의 숫자 브랜치에서 `.`/`e`/`E` 문자 존재
  여부를 토큰 문자열 단위로 직접 검사하도록 바꿨다(`isFloatOrExponent`
  플래그). 정수 토큰은 `/^-?(0|[1-9][0-9]*)$/`로 재검증한다. `-0`은
  `Object.is(value, -0)`로 명시적으로 걸러 `0`으로 정규화한다(JS는
  -0을 별도 값으로 보존하므로 Python과 달리 명시적 처리가 필요했다).
- **검증 결과**: `{"count": 1.0}`·`{"count": 1e0}` 모두 양쪽 언어가
  `FLOAT_OR_EXPONENT_NOT_ALLOWED`로 동일하게 거절 — **V04는 이제
  RESOLVED_REJECTED**(§3 표 갱신판은 아래 9-3 참조).
- **유지되는 제한**: "이미 파싱된 객체 경로"(`validate_payload_schema_interim`/
  `validatePayloadSchemaInterim`)만 단독으로 쓰면 여전히 1과 1.0을
  구분하지 못한다 — `python_output.json`/`js_output.json`의 V04
  항목에 `legacyParsedObjectPathGuardResult` 필드로 이 사실을 그대로
  남겨 실측 확인했다(Python은 여전히 거절, JS는 여전히 통과). **이
  제한 자체를 없앤 것이 아니라, raw JSON 경로를 먼저 거치도록 해서
  문제가 되는 경로를 피한 것**이다 — 운영 전체 수신 아키텍처는
  바꾸지 않았다(지시 재확인).

### 9-2. 요청별 스키마 확인·보완

**파일**: `src/idempotency/request_payload_schemas.py`(신규),
`tests/cross_validation/request_payload_schemas.js`(신규).

실제 Pydantic 모델(`src/api/api_server.py`, `src/api/routes_admin_portal.py`)
8종을 operation별로 등록했다: `reservation_create`, `reservation_cancel`,
`reservation_change`, `slot_generate`, `consultation_status_update`,
`reservation_reject`, `questionnaire_review`, `crm_notification`.
각 필드의 필수 여부·타입·null 허용은 실제 모델 정의를 그대로 옮겼다
— **모델이 범위를 명시하지 않은 필드(예: `SlotGenerateBody.capacity`)에
임의의 업무 범위를 추가하지 않았다.** 유일한 예외는
`RejectReservationBody.reason`으로, 실제 코드(`routes_admin_portal.py`
`_validate_reason`)가 길이 2~200자를 **이미 명시적으로 검증**하므로
그 값을 그대로 재사용했다(발명이 아니라 재확인). `ChatBody.context`/
`QSubmitBody.answers`(자유형 `dict`)는 레지스트리에 **등록하지
않았다** — 이번 서명 대상에서 제외. 레지스트리에 없는 operation은
`UNKNOWN_OPERATION`으로 거절한다(ASCII 키라는 이유만으로 임의 필드를
허용하지 않는다는 원칙 적용).

### 9-3. 서명 전 개발용 연결(wrapper)

**파일**: `src/idempotency/signing_v2_guarded.py`(신규),
`tests/cross_validation/signing_v2_guarded.js`(신규).

`validate_and_normalize_payload(raw_json_text, operation)` →
(1) `parse_json_strict` → (2) `validate_payload_schema_interim` →
(3) `validate_request_schema` → 전부 통과한 payload만
`signing_v2.compute_payload_hash()`/`sign_v2()`(**기존 함수, 미수정**)로
전달한다. `compute_payload_hash_guarded()`/`sign_v2_guarded()`로
감쌌다. Python/JS 양쪽에서 동일 입력에 대해 payloadHash·서명이
바이트 단위로 일치함을 실측 확인했다(아래 표).

| 값 | Python(`signing_v2_guarded.py`) | JS(`signing_v2_guarded.js`) |
|---|---|---|
| payloadHash(`reservation_create` 유효 입력) | `83618c6a741e9546b38a96bea5c60ef0677a4d4dbdb6ec2d38d0083fd58c0c28` | 동일 |
| signature(`consultation_status_update` 유효 입력) | `bcbb7d38ea05e656ce1c5eb391d017a97460fdb34f7b77d68b65c30e5a5dc326` | 동일 |

**기존 함수의 한계 명시(실측 확인)**: `tests/test_signing_v2_guarded.py`의
`ExistingFunctionLimitationTestCase`는 `signing_v2.compute_payload_hash()`를
wrapper 없이 직접 호출하면 float(`1.0`)·Unicode 키·미등록 필드 전부
**아무 예외 없이 그대로 해시가 계산됨**을 실측으로 보여준다 — wrapper를
거치지 않는 기존/향후 호출부는 이 보호를 전혀 받지 못한다.

### 9-4. 벡터별 MATCH / RESOLVED_REJECTED / UNRESOLVED(최종)

`python3 tests/cross_validation/compare_outputs.py` 재실행 결과(exit code 0):

**총 22개 벡터 — MATCH 13 / RESOLVED_REJECTED 9 / UNRESOLVED 0.**

8-1의 표에서 V04만 **UNRESOLVED → RESOLVED_REJECTED**로 바뀌었고 나머지
21개 벡터의 분류는 그대로다.

### 9-5. 테스트 명령·결과(최종 전체)

```
python3 tests/cross_validation/run_python_side.py   # 22 vectors
node    tests/cross_validation/run_js_side.js        # 22 vectors
python3 tests/cross_validation/compare_outputs.py    # exit 0 (UNRESOLVED 0건)

python3 -m unittest tests.test_idempotency_store tests.test_gas_orchestration \
  tests.test_signing_v2 tests.test_nonce_store tests.test_payload_schema_guard \
  tests.test_request_payload_schemas tests.test_signing_v2_guarded
# -> Ran 112 tests ... OK (기존 62 + 가드 25 + 요청스키마 13 + wrapper 12)
```

### 9-6. 남은 제한(완전 해소되지 않은 항목)

1. "이미 파싱된 객체 경로"만 단독으로 쓰면 1 vs 1.0을 여전히 구분
   못 한다(9-1 재확인) — raw JSON 경로를 거치는 것이 전제 조건이다.
2. 요청별 스키마 레지스트리는 현재 8개 operation만 다룬다. 새
   operation을 서명 대상에 추가하려면 레지스트리에 먼저 등록해야
   하며, 등록 전까지는 `UNKNOWN_OPERATION`으로 거절된다(의도된
   동작).
3. 원시 바디의 중복 키 검증을 FastAPI 수신 계층에 실제로 적용할지는
   여전히 결정 사항이다(제안서 §3 "계약 변경이 필요한 항목" 3번
   재확인) — 이번 턴도 운영 수신 계층은 변경하지 않았다.
4. §7의 실제 GAS 교차검증 미해결 사항(V8 `Utilities.computeHmacSha256Signature`
   실측 등)은 그대로 남아 있다.

---

**완료 조건 재확인**: 운영 Secret·실제 GAS/Sheets 접근 없음. 합성 키만
사용(`xval-cross-secret-*`, `synthetic-test-secret-guarded-*`, §1
재확인). `service_hmac.py`·`signing_v2.py`·`nonce_store.py`·기존 `.gs`
파일 수정 없음(`signing_v2_guarded.py`는 이들을 호출만 하는 별도
wrapper). Option B 가드·요청별 스키마·서명 전 wrapper 구현을 포함해
이번 턴의 모든 변경사항은 commit/push하지 않았다. 운영 라우트·운영
수신 계층 미배선·미변경.
