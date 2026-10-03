# Commit8-3b 격리 GAS 교차검증 — 실행 패키지

> **상태**: 이 폴더는 **재사용 가능한 업로드 패키지**(이 디렉터리의
> 6개 파일)와 **1회성 실행 증적**(`evidence/`, 2026-10-03 13:31:28
> KST 실행 결과)을 함께 보관한다. **`evidence/`의 실행본
> (`Expected_AS_EXECUTED_20261003.gs`)은 과거 증적일 뿐, 업로드
> 대상이 아니다** — §4를 따라 **이 디렉터리의 6개 파일 중 5개
> 실행 파일만** 별도 폴더로 복사해 올려야 한다(아래 §4 재확인).
> 아래 §2의 로컬 검증은 **구문검사 + Node 스텁 기반 로직 검증**이고,
> §7은 **2026-10-03에 실제로 실행해 확보한 결과**다 — 둘을 구분해서
> 읽을 것. 재실행 시에도 로컬 검증 결과를 실제 GAS 실행 PASS로
> 표현하지 않는다. **OFFICIAL PHASE 1 GATE = BLOCKED INPUT 유지.**

## 1. 파일 구성(최종 저장소 경로)

```
tests/cross_validation/gas/
  appsscript.json     — GAS 매니페스트(V8, oauthScopes: [])
  Code.gs              — canonical string/payloadHash/HMAC + Option B 가드 포팅 로직
  Fixtures.gs          — tests/cross_validation/fixtures_v2.json·keys_v2.json 그대로 embed(22개 벡터, 전부 포함·제외 없음)
  Expected.gs          — 기대값(MATCH 12 + 거절 9 + 필드거절 1(V07) = 22, V02 라벨 정정본). 각 값에 verificationBasis(INDEPENDENT_OPENSSL/PYTHON_COMPARISON_ONLY) 명시 — §2-2/§2-5 참조
  Main.gs              — 실행 진입점 runAllVectors()
  README.md            — 이 문서
  evidence/             — 1회성 실행 증적 폴더. **이 안의 파일은 업로드하지 않는다(§4)**
    Expected_AS_EXECUTED_20261003.gs   — 2026-10-03 13:31:28 KST 실행 당시 버전(V02가 INDEPENDENT_OPENSSL로 잘못 표시된 상태, SHA-256 bcb4b11d...). 바이트 단위로 수정하지 않고 그대로 보존
    GAS_EXECUTION_RESULT_FULL_20261003.txt — 실행 로그 전체 원문(SHA-256 728111b7...)
    EXECUTION_LOG.md     — 프로젝트 생성·업로드·`clasp run` 실패·`clasp pull` 복구 기록
```

재현용 생성 스크립트(`_gen_gas_package.py`)와 로컬 스텁 하네스
(`_gas_stub_harness.js`)는 scratchpad에만 있으며 이 저장소에
commit하지 않았다(재현 도구일 뿐 증적 자체가 아님).

이 패키지는 **운영 `app/apps_script/*.gs` 파일을 전혀 수정하지
않았다** — 전부 새로 추가한 파일이다.

## 2. 로컬 검증 결과

### 2-1. 구문검사(`node --check`)

`Code.gs`/`Main.gs`/`Fixtures.gs`/`Expected.gs` 4개 파일을 각각
`.js` 확장자 임시 복사본으로 만들어 `node --check`를 실행했다 — **4개
전부 구문 오류 없음(SyntaxError 없음)**. 이는 "GAS 편집기에 붙여
넣었을 때 즉시 구문 오류가 나지는 않을 것"이라는 의미일 뿐, GAS
전용 전역(`Utilities`, `Logger`)의 실제 동작을 검증한 것은 아니다.

### 2-2. Node 스텁 기반 로직 검증(`_gas_stub_harness.js`) — 실제 GAS 아님

`Utilities.computeDigest`/`computeHmacSha256Signature`/`newBlob`를
**Node `crypto`로 흉내 낸 스텁**(GAS의 signed byte[](-128~127) 반환
방식까지 그대로 재현)으로 대체하고, `vm` 모듈로 4개 `.gs` 파일을
하나의 전역 스코프에 평가한 뒤 `runAllVectors()`를 실행했다:

```
최종: 22/22 PASS (로컬 스텁 기준 — 실제 GAS Utilities 검증 아님)
```

- MATCH 12개 전부 PASS(payloadUtf8Hex·payloadHash·canonicalUtf8Hex·
  signature 4필드 hex 완전 일치).
- 거절 9개 전부 PASS(동일 reason 코드로 거절).
- **V07(필드거절 1개)도 포함해 PASS** — §2-5 참조(이전 패키지 버전의
  제외는 정정됐다).
- **이 결과가 증명하는 것**: 포팅된 로직(`bytesToHex_`의 signed byte
  보정 포함)이 "Node crypto가 만드는 바이트와 같은 입력이 주어지면"
  Python/JS 교차검증 기대값과 정확히 일치한다는 것.
- **이 결과가 증명하지 않는 것**: 실제 GAS V8 런타임의
  `Utilities.computeDigest`/`computeHmacSha256Signature`가 Node
  crypto와 바이트 단위로 동일하게 동작하는지, GAS의 실제
  `JSON.stringify`/키 정렬·정규식 엔진이 이 포팅 코드와 동일하게
  동작하는지 — 이것이 바로 실제 GAS 실행이 필요한 이유다.

### 2-3. Logger 출력 육안 확인(secret·원문 payload 미노출)

스텁 하네스의 `Logger.log()` 출력 22줄을 전수 확인한 결과, 벡터
ID·"PASS"/"FAIL"·verificationBasis 라벨·(거절 벡터만) reason 코드
외에는 **아무 것도 출력되지 않았다** — `SYNTHETIC_KEYS`의 secret 값,
`payloadNormalizationResult` 같은 payload 원문은 어떤 로그 줄에도
나타나지 않는다(코드 레벨에서 애초에 그런 변수를 로그 인자로 넘기지
않도록 작성했다, `Main.gs` 참조).

### 2-4. 정적 검사(금지 토큰 grep)

`require\(|module\.exports|Buffer\.|SpreadsheetApp|DriveApp|UrlFetchApp|CacheService|PropertiesService|process\.|import\s`
패턴으로 패키지 전체를 검색한 결과, **실제 코드에서의 사용은 0건**이다
(검출된 것은 전부 "이런 걸 쓰지 않았다"는 주석/README 설명문 안에서만
등장). `cmcsh`/`C:\Users`/전화번호·주민등록번호 패턴도 0건.
`SYNTHETIC_KEYS`에 포함된 두 값은 `tests/cross_validation/keys_v2.json`에
이미 commit된 것과 동일한 합성 테스트 Secret이다(새로 만든 값 아님).

### 2-5. V07 — 목적, 재검토 결과, 포함 결정

- **벡터의 목적**: `signing_v2.py`의 필드 형식 검증(`SAFE_TOKEN_RE`)이
  nonce 필드에 삽입된 LF(개행)를 거절해, 구분자 삽입으로 Canonical
  String 경계가 조작되는 것을 막는지 확인하는 벡터다(payload
  `{"qty":1}` 자체는 정상 — 거절 지점은 nonce 필드).
- **이전 패키지 버전의 제외 사유**: "GAS crypto/직렬화와 무관한
  필드 형식 검증 벡터"라고 판단해 비교 대상에서 뺐다. **이 제외는
  사전에 승인된 것이 아니라 패키지 작성자(이 세션)의 자체 판단이었다
  — "계획대로 제외"라는 이전 표현은 부정확했다. 정정한다.**
  (실제로 `Sprint8_Commit8_3b_Isolated_GAS_CrossValidation_Execution_Plan.md`
  §0은 V07을 "이 계획이 제외한다"고 스스로 적어 두었을 뿐, PM이나
  사용자가 사전에 그 제외를 검토·승인한 기록은 없다.)
- **재검토 결과 — GAS에서 검증 가능**: `Code.gs`에 이미 포팅된
  `validateField_()`/`signV2_()`는 Python과 동일한 정규식
  (`SAFE_TOKEN_RE`)으로 nonce를 검증하므로, 추가 코드 없이
  `signV2_()` 호출만으로 `FieldFormatError_`가 던져지는지 바로
  확인할 수 있다. `_test_v07_portable.js`로 로컬 Node 스텁에서
  실제로 `FieldFormatError_`가 발생함을 먼저 확인한 뒤(§2-2와 별도
  사전 확인), 정식으로 패키지(`Expected.gs`의 `EXPECTED_FIELD_REJECTION`,
  `Main.gs`의 `runFieldRejectionVector_()`)에 포함했다.
- **verificationBasis**: `PYTHON_COMPARISON_ONLY` — "서명 시도 시
  `FieldFormatError_`가 던져져야 한다"는 기대 자체가
  `python_output.json`의 `signError` 필드에서 가져온 것이라, OpenSSL
  같은 제3자 도구로 "예외가 던져지는가"를 독립 검증할 방법은 없다
  (OpenSSL은 크립토 연산만 검증 가능, 제어흐름/예외는 검증 대상이
  아님). 이 한계는 V07만의 특수성이 아니라 "거절 계열" 벡터 전체에
  공통이다(§2-6 재확인).

### 2-6. Expected.gs — 기대값의 원천 구분(독립 검증 vs Python 결과 비교)

| verificationBasis | 해당 벡터 | 의미 |
|---|---|---|
| `INDEPENDENT_OPENSSL` | **EXPECTED_MATCH의 V01 단 1개뿐** | Python도 JS도 아닌 제3자 도구(`openssl` CLI)로 SHA-256/HMAC-SHA256을 **직접 재계산**해 확인한 값(`docs/`의 `CROSS_VALIDATION_REPORT.md` §2, 1차 자료 — `tests/cross_validation/CROSS_VALIDATION_REPORT.md`). GAS가 이 값과 일치하면 "독립적으로 검증된 정답과도 일치"라고 말할 수 있다. **(정정, §8 재확인)** 이전 버전은 거절 카테고리의 V02에도 이 라벨을 잘못 붙였었다 — 거절/수용 같은 제어흐름은 OpenSSL로 독립 검증할 수 없으므로 수정했다. |
| `PYTHON_COMPARISON_ONLY` | **나머지 21개**(MATCH 11 + 거절 9 + 필드거절 1, V02 포함) | `python_output.json`에서 **그대로 복사**한 값. GAS가 이 값과 일치해도 "GAS가 Python 결과와 같다"는 뜻일 뿐, 그 값 자체가 제3자 도구로 독립 검증됐다는 뜻은 아니다. **Python 결과를 복사해 비교하는 것을 독립 검증이라고 표현하지 않는다.** |

`Expected.gs` 파일 안에 이 구분을 주석과 각 벡터의 `verificationBasis`
필드로 명시했고, `Main.gs`의 모든 PASS/FAIL 로그 줄에
`[독립검증:OpenSSL]` 또는 `[Python 비교]` 라벨을 붙여 실행 로그
자체에서도 이 구분이 드러나게 했다(§2-2 실행 결과 참조 — 실제로
`[V01_ascii_normal] PASS [독립검증:OpenSSL]`처럼 출력됨).

## 3. 서비스·scope 점검 결과

| 항목 | 결과 |
|---|---|
| `appsscript.json`의 `oauthScopes` | `[]`(빈 배열, 명시적 선언) |
| `runtimeVersion` | `"V8"` |
| 코드에서 실제 호출하는 서비스 | `Utilities`, `Logger` **뿐** |
| `SpreadsheetApp`/`DriveApp`/`UrlFetchApp`/`CacheService`/`PropertiesService` 호출 | **0건**(§2-4 grep 확인) |

`Utilities`/`Logger`는 Google 사용자 데이터에 접근하지 않는 내장
서비스라 OAuth 동의 화면 자체가 뜨지 않거나, 뜨더라도 "이 앱이
귀하의 Google 계정에 연결하고자 합니다"류의 데이터 접근 권한 승인이
아닌 최소 수준이어야 한다(실제 생성 시 확인 필요 — §6 중단 조건).

## 4. 전용 프로젝트에 적용할 정확한 순서와 명령

> **핵심 주의**: 이 디렉터리(`tests/cross_validation/gas/`)에서
> 바로 `clasp push`를 실행하면 안 된다 — `evidence/` 하위 폴더의
> `.gs` 파일(`Expected_AS_EXECUTED_20261003.gs`)까지 clasp가
> 재귀적으로 인식해 함께 업로드될 위험이 있다(Apps Script는 폴더
> 구조가 없어 베이스네임만으로 별도 스크립트 파일이 생성됨 — 과거
> 증적이 라이브 테스트 프로젝트를 오염시키게 된다). **반드시 아래
> 0번처럼 실행 파일 5개만 별도의 빈 폴더로 복사한 뒤 그 폴더에서
> clasp 명령을 실행한다.**

```bash
# 0) 실행 파일 5개만 별도의 빈 작업 폴더로 복사(evidence/ 제외)
#    — 이 저장소 루트에서 실행한다고 가정.
UPLOAD_DIR=$(mktemp -d)
cp tests/cross_validation/gas/Code.gs \
   tests/cross_validation/gas/Fixtures.gs \
   tests/cross_validation/gas/Expected.gs \
   tests/cross_validation/gas/Main.gs \
   tests/cross_validation/gas/appsscript.json \
   "$UPLOAD_DIR/"
cd "$UPLOAD_DIR"
ls -la .clasp.json 2>/dev/null && echo "경고: 기존 .clasp.json 발견 — 중단" || echo "확인됨: .clasp.json 없음(신규 빈 폴더), 안전하게 신규 생성 가능"

# 1) clasp 로그인(전용 테스트 Google 계정으로 — 운영 계정 아님)
clasp login

# 2) 신규 Standalone Apps Script 프로젝트 생성
#    --type standalone이 핵심 — Sheet에 바인딩하지 않는다.
clasp create --type standalone --title "CMC_HMAC_V2_ISOLATED_TEST"
#    실행하면 이 작업 폴더에 새 .clasp.json이 생성된다(scriptId 포함).
#    clasp create가 로컬 appsscript.json을 Google 기본 매니페스트로
#    덮어쓸 수 있으니, push 전에 appsscript.json 내용이
#    V8/oauthScopes:[]인지 다시 확인한다(필요하면 위 0번에서 복사한
#    원본으로 재복사).
#    생성된 scriptId를 별도로 기록해 "격리 자원 목록"에 남긴다.

# 3) 작업 폴더(5개 파일만 있는 $UPLOAD_DIR)에서 push
clasp push

# 4) 브라우저에서 Apps Script 편집기 열기
clasp open

# 5) 편집기에서 runAllVectors 함수를 선택해 "실행"
#    최초 실행 시 OAuth 승인 화면이 뜨면 요청 scope를 확인한다
#    (§6 중단 조건 1번 — Sheets/Drive 등 예상 밖 scope면 승인하지 않고 중단).

# 6) 실행 로그(보기 > 실행 로그, 또는 Stackdriver)에서 PASS/FAIL 결과 확인
#    §7 비교 절차대로 22/22 PASS 여부를 기록한다. 전체 원문을
#    복사해 tests/cross_validation/gas/evidence/에 새 날짜로 보존한다
#    (기존 evidence/ 파일은 2026-10-03 실행분이므로 덮어쓰지 않는다).

# 7) 테스트 완료 후 자원 정리
clasp open  # 편집기에서 프로젝트 삭제, 또는:
#    Apps Script 홈(script.google.com) > 해당 프로젝트 > 휴지통으로 이동 > 완전 삭제
# 8) 임시 작업 폴더 정리
rm -rf "$UPLOAD_DIR"
```

## 5. 기존 `.clasp.json`이나 운영 프로젝트를 쓰지 않는지 확인하는 방법

1. **리포지토리 전체 검색**: `find . -iname ".clasp.json"` — 이번
   확인에서 **0건**(이 저장소에는 애초에 `.clasp.json`이 존재하지
   않는다). 즉 "기존 파일을 실수로 재사용"할 물리적 경로 자체가
   없다.
2. **작업 디렉터리 격리**: 위 §4의 모든 명령은 §4-0에서 새로 만든
   **임시 작업 폴더**(`mktemp -d` 결과, 리포지토리 밖)에서만
   실행한다 — `clasp create`가 만드는 `.clasp.json`이 리포지토리에
   섞여 들어갈 수 없고, `evidence/`의 과거 실행본과도 물리적으로
   분리된다.
3. **`clasp create` 자체가 신규 scriptId를 발급**한다 — 기존 scriptId를
   지정하는 `clasp clone <scriptId>`를 쓰지 않는 한 운영 프로젝트에
   연결될 수 없다. 이 계획은 `clasp create`만 사용하고 `clasp clone`은
   사용하지 않는다(실행 순서에 명시).
4. 생성 직후 `.clasp.json`의 `scriptId` 값을 PM에게 보고해, 운영
   프로젝트의 알려진 Script ID와 **다름을 상호 확인**한다(운영 Script
   ID 목록은 이 패키지에 포함하지 않았다 — 별도 보안 문서 참조 필요).

## 6. 실패 판정·중단 조건(실행계획 §9 재확인)

- MATCH 12개 중 하나라도 4필드(payloadUtf8Hex/payloadHash/
  canonicalUtf8Hex/signature) 불일치 → 해당 벡터 FAIL.
- 거절 9개 중 하나라도 거절하지 않거나 다른 reason → FAIL.
- 필드거절 1개(V07)에서 `FieldFormatError_`가 던져지지 않으면 FAIL.
- OAuth 승인 화면에 Sheets/Drive/Gmail 등 예상 밖 scope 등장,
  코드에 없던 실제 Sheet 접근 시도 발견, API 할당량 초과 반복 →
  **즉시 중단**.

## 7. 비교 절차(실제 GAS 실행 후)

1. Apps Script 실행 로그에서 각 벡터의 `PASS [독립검증:OpenSSL]`/
   `PASS [Python 비교]`/`FAIL ...` 줄을 그대로 복사한다(hex 값 자체를
   로그에 추가로 남기고 싶다면 `Main.gs`의 `Logger.log` 호출을
   일시적으로 확장할 수 있으나, 기본 패키지는 필드명만 남긴다 —
   §2-3 로깅 원칙 유지).
2. 22/22 PASS면 "GAS V8 실측 완료, Node 스텁 결과와 일치"로 기록하되,
   **MATCH의 V01 단 한 건만 "독립 검증(OpenSSL)과도 일치"**(V02는
   거절 카테고리라 OpenSSL 대상이 아니다 — §2-6/§8의 V02 라벨 오류
   정정 참조), 나머지 21개는 "Python 결과와 일치"라고 구분해서
   보고한다. 섞어서 "22개 전부 독립 검증됐다"고 표현하지 않는다.
3. 하나라도 FAIL이면, 해당 벡터의 `payloadHash`/`signature` 등 hex
   값만(여전히 secret·payload 원문 아님) 추가로 로그에 남겨 어느
   바이트 단계에서 달라지는지 분석한다 — 1차 의심 지점은 (a)
   `Utilities.newBlob(str).getBytes()`의 실제 UTF-8 인코딩 방식, (b)
   GAS `JSON.stringify`의 숫자 직렬화, (c) `computeHmacSha256Signature`의
   Charset 처리 순서, (d) V07이 FAIL이라면 GAS의 정규식 엔진이 제어
   문자 처리에서 Node와 다른지.

## 8. 2026-10-03 실제 실행 결과(완료, evidence/ 보존)

이 패키지는 이미 한 번 실행됐다 — 프로젝트 `CMC_HMAC_V2_ISOLATED_TEST`
(scriptId `1f8e3qCgMfd7vR5cq81Bqir_6RNf8Ux8pjTrD5-EhalIibO2OUCKXMXeD`),
2026-10-03 13:31:28 KST, 사용자가 Apps Script 편집기에서 수동 실행.
**결과: 22/22 PASS**(MATCH 12/12, 거절 9/9, 필드거절 1/1).

- 전체 로그 원문: `evidence/GAS_EXECUTION_RESULT_FULL_20261003.txt`
  (SHA-256 `728111b7394d0a5a0f4d577c99d7ca60b74f96b7b955567b04e8ebf9bc5c4213`)
- 실행 당시 `Expected.gs`(V02 라벨 오류 포함): `evidence/Expected_AS_EXECUTED_20261003.gs`
  (SHA-256 `bcb4b11d40f43692eb34f2c61a8738d388e22096f18522dc4fdd991d58787e1f`)
- 상세 분석·V02 라벨 오류 발견 경위·검증 근거 구분(독립검증 vs
  Python 비교): `docs/Sprint8_Commit8_3b_Isolated_GAS_CrossValidation_Result_Report.md`
- 실행 당시 사용한 `Code.gs`/`Fixtures.gs`/`Main.gs`/`appsscript.json`은
  **이 디렉터리의 현재 파일과 해시가 완전히 동일**하다(실행 후 수정한
  적 없음, `clasp pull`로 재확인 완료) — **`Expected.gs`만 실행 후
  라벨 정정**됐다(`evidence/Expected_AS_EXECUTED_20261003.gs`와의 diff
  참조, 결과보고서 §5-1).

**재실행 시 주의**: 위 scriptId의 라이브 프로젝트는 아직 삭제되지
않았을 수 있다(이 패키지 작성 시점 기준) — 같은 프로젝트에 재push할지,
새 프로젝트를 만들지는 PM 승인 사항이다.

---

**완료 조건 재확인**: 이 패키지는 §8에서 이미 1회 실제 GAS 실행을
완료했다(증적은 `evidence/`에 보존). 재실행이 필요하면 §4의 절차를
따르되, `evidence/`의 과거 실행본은 업로드 대상에서 제외한다. 로컬
구문검사·Node 스텁 검증 결과(§2)는 실제 GAS 실행 결과(§8)와 구분해서
표현한다. 운영 코드·운영 라우트에는 여전히 연결하지 않았다. **OFFICIAL
PHASE 1 GATE는 BLOCKED INPUT을 유지한다.**
