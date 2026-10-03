# Commit8-3b — payload 정규화 계약 미확정 2건 해결 제안서 + 구현 결과

> **상태**: **Option B는 격리 개발 계약(이 worktree 안에서만 유효한
> 구현 전제)이다 — 운영 ADR-017 개정이 확정되기 전까지는 운영 계약이
> 아니다.** 아래 §1~§5는 최초 제안(권고안) 내용이고, **§6은 그
> 권고안을 실제로 구현해 격리 환경에서 검증한 결과**다(§6 신설,
> 이번 갱신). 구현은 기존 코드(`signing_v2.py`, `nonce_store.py`,
> `service_hmac.py`, `.gs` 파일 등)를 전혀 변경하지 않았다 — 전부 새
> 파일로만 추가했다. 운영 라우트·운영 수신 계층에 배선되지 않았다.
> **OFFICIAL PHASE 1 GATE는 BLOCKED INPUT을 유지한다.**
> **작성일**: 2026-10-03(최초 제안) / 2026-10-03(§6 구현 결과 추가) /
> **이전 commit**: `c3ea4dd7d21970198225cd18e83cea9e89ef111f`(§1~§5 제안
> 작성 시점) — §6의 구현 파일은 이 문서와 함께 이번 턴에 신규 commit된다.

---

## 1. 실제 요청 스키마 확인 결과

`src/api/`, `src/auth/` 내 Pydantic `BaseModel` 전수 확인(`grep -rn "class \w+(BaseModel):" src/` 기반, 개인정보·실제 예약자료는 읽지 않고 **모델 정의(필드명·타입)만** 확인):

| 모델 | 파일 | 필드 타입 | 비고 |
|---|---|---|---|
| `LoginBody` | `src/auth/routes_auth.py:177` | str × 2 | — |
| `ChatBody` | `src/api/routes_agents.py:53` | str, str, **`dict[str, Any]`** | AI 채팅 세션 context — 자유형 객체 |
| `VerifyBody` | `src/api/routes_agents.py:59` | str/Optional[str] × 4 | — |
| `QSubmitBody` | `src/api/routes_agents.py:66` | str, **`list[dict[str, Any]]`** | 문진 답변 — 자유형 객체 |
| `ConsultationStatusBody` | `src/api/routes_admin_portal.py:112` | str, Optional[str] | 관리자 쓰기 |
| `RejectReservationBody` | `src/api/routes_admin_portal.py:126` | str(+길이검증) | 관리자 쓰기 |
| `ReservationCreate` | `src/api/api_server.py:75` | str × 5, bool, Optional[str] | 관리자 쓰기 |
| `ReasonBody`/`ChangeBody` | `src/api/api_server.py:86,90` | str | 관리자 쓰기 |
| `SlotGenerateBody` | `src/api/api_server.py:97` | str × 2, str, **int(=6)** | 관리자 쓰기, 소형 정수 |
| `QuestionnaireItem`/`Start` | `src/api/api_server.py:104,111` | str 위주, 구조화된 list | — |
| `QReviewBody` | `src/api/api_server.py:119` | str × 2 | 관리자 쓰기 |
| `CrmNotificationBody` | `src/api/api_server.py:124` | str × 6(Optional 포함) | 관리자 쓰기 |

추가로 `grep -n ": float|: Decimal|: int" src/**/*.py` 결과, **`float`/`Decimal` 타입은 요청 바디 어디에도 없다** — `float` 사용처는 전부 내부 타임아웃/skew 값(`timeout: float = 60.0`, `signing_v2.verify_v2`의 `now: float` 등 와이어 payload가 아닌 함수 인자)이다. `int` 필드는 `capacity`, `retryCount`, `waitingCount`, `max_attempts`, `budget` 등 전부 **작은 범위의 경계 정수**이며 안전정수범위(§2 참조)를 벗어날 근거가 없다.

### 핵심 발견
1. **ADR-017 범위(관리자 쓰기 → GAS 서명 프록시 후보)에 해당하는 모델은 전부 `str`/`bool`/소형 `int`만 쓰며, `float`·`Decimal`·중첩 자유형 객체·Unicode object key가 없다.**
2. 자유형 `dict[str, Any]` 필드는 `ChatBody.context`, `QSubmitBody.answers` **2건뿐**이며, 둘 다 AI 상담/문진 세션 기능으로 **세션 인증 경로**를 쓰고 ADR-017 HMAC 서명 대상(관리자 GAS 쓰기 프록시)이 아니다. 즉 **현재 코드베이스에는 V04/V13이 실제로 발동할 입력 자체가 존재하지 않는다** — 이는 미확정 상태를 "운영상 급하지 않다"로 깎아내리는 근거가 아니라, **제약을 둬도 실제 기능을 해치지 않는다는 근거**다.
3. ADR-017 문서 자체는 `payload`의 값 타입 제약을 전혀 정의하지 않았다(검색 결과 無) — 이번 제안서가 처음으로 이 공백을 메우려는 시도다.

---

## 2. 정규화 방식 비교 — A(RFC 8785/JCS) vs B(제한된 명시적 직렬화)

### 2-1. RFC 8785(JCS) 1차 자료 확인 결과 (rfc-editor.org/rfc/rfc8785 직접 확인)

| 항목 | RFC 8785 원문 근거 |
|---|---|
| 숫자 직렬화 | §3.2.2.3: ECMAScript(IEEE 754 double) `Number::toString` 알고리즘(ECMA-262 §7.1.12.1) 그대로 적용 — **int/float 구분이 아예 존재하지 않음**(모든 숫자가 double) |
| 1 vs 1.0 | 같은 알고리즘으로 둘 다 `"1"` — 구분 불가(사양상 "구분 없음"이 곧 해결책) |
| -0 처리 | Appendix B: IEEE754 `8000000000000000`(음의 0) → `"0"`으로 직렬화(양의 0과 동일) |
| 지수표기 | 자동 적용 예시: `1E30`→`"1e+30"`, `1e-27` 등 — 사람이 쓴 지수표기도 알고리즘이 재정규화 |
| 안전정수범위 | Appendix B 주석(1): "참정수로 해석될 값은 -9007199254740991~9007199254740991 범위여야 함(**SHOULD**)" |
| NaN/Infinity | §3.2.2.3: "NaN 또는 Infinity 발생 시 준수 구현은 **반드시 오류로 종료**해야 함(MUST)" |
| 객체 키 정렬 | §3.2.3: **"UTF-16 코드 유닛 배열로 취급해 정렬"** — 코드포인트가 아니라 **코드 유닛** 기준(근거: "ECMAScript의 문자열 타입에 직접 대응하기 때문") |
| Unicode 문자열 값 정규화 | §3.1: **"JCS 준수 문자열 처리는 이를 고려하지 않는다. 즉 JCS에 의존하는 모든 구성요소는 Unicode 문자열 데이터를 '있는 그대로' 보존해야 한다(MUST)"** — **NFC 등 정규화를 요구하지 않을 뿐 아니라, 하지 말라는 쪽에 가깝다** |
| 중복 키 | §3.1: "JSON 객체는 중복된 property name을 가져서는 안 된다(MUST NOT)" — **정렬 알고리즘이 아니라 입력 전제조건**이며, Python `json.loads`/JS `JSON.parse` 모두 기본적으로 이를 강제하지 않는다(중복 시 마지막 값으로 조용히 덮어씀) — 별도 파싱 단계 검증이 필요 |
| 근거 알고리즘 | §1: ECMA-262(ECMAScript 2019) §7.1.12.1(숫자), §24.3.2.2(문자열)에 전적으로 의존 |

### 2-2. 비교표

| 검토 항목 | A. RFC 8785/JCS 전체 적용 | B. 요청 스키마 제한 + 명시적 직렬화 |
|---|---|---|
| Python 구현 가능성 | 가능하나 **직접 구현 필요**(표준 라이브러리에 JCS 구현 없음) — 특히 UTF-16 코드 유닛 정렬은 Python 기본 `sorted()`(코드포인트 기준)와 달라 **별도 변환 코드 필요** | 쉬움 — 기존 `_SAFE_TOKEN_RE` 패턴을 값 검증에도 재사용 가능, 이미 이 구현의 설계 철학과 일치 |
| JavaScript 구현 가능성 | 쉬움(네이티브 `JSON.stringify`+`Object.keys().sort()`가 사양과 거의 자연히 일치) | 쉬움 |
| GAS(Apps Script, V8) 구현 가능성 | JS와 동일 런타임 계열이라 이론상 쉬움 — **단, 실측 확인 안 됨**(§4 미해결 사항) | 쉬움(값 타입이 string/int/bool/null로 한정되므로 GAS 쪽 추가 로직 최소) |
| 1 vs 1.0 | **해결됨**(둘 다 `"1"`) — 단 Python이 보내는 측이라면 **애초에 float를 보내지 말아야** 한다는 운영 규율은 여전히 필요 | **원천 금지**(payload에 float 금지) — 모호성 자체가 발생 안 함 |
| -0 | `"0"`으로 정규화됨(해결) | 애초에 음수 0을 의미 있는 값으로 쓸 유스케이스가 없음 — 정수만 허용 시 자동 비해당 |
| 지수표기 | 자동 재정규화(해결) | 입력 시 거절(정수 리터럴만 허용) |
| 안전 정수 범위 | **SHOULD** 권고일 뿐 강제 아님 — 범위 밖 정수는 JCS로도 손실 위험 여전 | 스키마에서 안전정수범위를 **MUST**로 강제, 벗어나면 거절 |
| NaN/Infinity | 오류로 종료(해결, 단 JSON 자체가 애초에 리터럴로 안 받으므로 Python 쪽에서 `float('nan')` 객체를 직접 넣는 비정상 경로만 해당) | 숫자 타입을 정수로 한정하므로 비해당 |
| 중복 객체 키 | **JCS 자체는 해결 안 함** — 입력 전제조건일 뿐, 원시 JSON 텍스트 파싱 단계에서 별도 검증 필요(Python/JS 네이티브 파서 둘 다 미지원) | 동일하게 원시 텍스트 파싱 단계 검증 필요 — **A/B 무관하게 남는 공통 과제** |
| Unicode 키 정렬 | **UTF-16 코드 유닛 기준으로 확정**(V13 해결) — 단 Python 구현은 코드포인트 정렬이 아니라 **코드 유닛 정렬을 별도 구현**해야 사양 준수 | object key를 ASCII-only safe-token으로 제한 → BMP/surrogate 비교 자체가 발생 안 함(쟁점 소멸) |
| Unicode 값 정규화(NFC) | **JCS는 NFC를 요구하지 않는다** — 오히려 "있는 그대로 보존" 요구. 기존 ADR-017 §12/계약 초안 §3의 NFC 요구와 **충돌** — 순정 JCS를 쓰려면 기존 NFC 요구를 버리거나, "JCS + 커스텀 NFC 레이어"라는 **비표준 혼합**이 되고 이 혼합 자체도 어디서도 검증된 적 없음 | NFC 요구를 그대로 유지(기존 ADR-017 §12 계승, 아래 §2-3 참조) — 값에 비 ASCII 문자열이 들어오는 경우(실제로 있음, V02 한글 payload)에도 모순 없음 |
| 기존 payloadHash·HMAC 계약 영향 | **영향 큼** — `compute_payload_hash()`의 직렬화 알고리즘 자체를 JCS로 전면 교체해야 하며, 기존 `sort_keys=True`(코드포인트 정렬)를 코드 유닛 정렬로 바꿔야 하므로 **기존 계약 초안 §3을 개정**해야 함 | **영향 작음** — 기존 `sort_keys=True` 직렬화·NFC 유지, "입력 측 스키마 제약"만 추가(§3 문구에 "payload value 제약" 절만 신설) |

### 2-3. NFC 정규화가 "현재 계약의 명시적 요구"인지 확인

- **예, 명시적 요구다.** ADR-017 §12(채택 결정)의 Canonical String v1 스펙이 "UTF-8/LF/no-trailing-newline/**NFC-normalized**/sorted-JSON-keys/lowercase-hex-hash"를 이미 명시했고, `Commit8_3b_HMAC_Nonce_V2_Contract_Draft.md` §3은 이를 그대로 계승했다(ADR-017을 벗어난 이 구현의 새로운 발명이 아님).
- 다만 **RFC 8785는 NFC를 요구하지 않으며**, "Unicode 데이터를 있는 그대로 보존하라"는 정반대 요구를 명시한다(§3.1). 따라서 **"RFC 8785를 그대로 따른다" = "NFC 요구를 포기한다"**가 되어 기존 ADR-017 계약과 정면으로 충돌한다는 점을, 이번 조사로 처음 명확히 확인했다.

### 2-4. "두 언어가 일치한다"는 것의 의미 — 과대 해석 금지

`tests/cross_validation/compare_outputs.py`가 PASS(exit 0)를 낸 것은 **"Python과 JS 참조구현이 서로 합의한 임의의 규칙"**을 따른다는 뜻일 뿐, **그 규칙이 운영 계약으로 올바르다는 증명이 아니다.** 예컨대 V13을 이 구현의 두 참조 코드가 나란히 "코드포인트 정렬"로 통일해 구현했다면 둘 다 일치하겠지만, 그것이 RFC 8785가 요구하는 "코드 유닛 정렬"과는 다를 수 있다 — **일치 자체가 표준 준수를 보장하지 않는다.** 이번 제안서가 규칙을 "확정"이 아니라 "권고"로만 제시하는 이유다.

---

## 3. 권고안 — Option B(요청 스키마를 제한한 명시적 직렬화 규칙)

### 권고 근거(요약)
1. §1에서 확인했듯, ADR-017 범위의 실제 요청 스키마는 이미 B의 제약을 100% 만족한다 — **기능 손실이 없다.**
2. A(JCS)는 Python에 코드 유닛 정렬이라는 비표준(stdlib 미지원) 구현을 추가로 요구하고, 기존 NFC 요구와 충돌해 "순정 JCS"가 아닌 변형을 만들게 된다 — **표준을 표방하면서 표준이 아닌 것을 만드는 위험**이 있다.
3. B는 이 구현이 이미 쓰고 있는 설계 철학(`_SAFE_TOKEN_RE` 기반 명시적 필드 검증, 계약 초안 §2)을 payload 값에도 **그대로 연장**하는 것이라 일관성이 높고, 3개 런타임(Python/JS/GAS) 모두에서 정규식 기반 검증이라 구현 난이도가 낮다.

### 지원 입력(초안, 결정 전까지는 "제안"일 뿐)
- object key: 기존 `_SAFE_TOKEN_RE`(`^[A-Za-z0-9_.\-:]{1,200}$`)를 재사용해 **ASCII-only 식별자만** 허용(실제 스키마가 전부 이 형태).
- value: `string`(NFC 정규화 그대로 유지, 트리밍 없음 — V05 결과와 일관), `boolean`, `null`, **10진 정수 리터럴만**(지수표기·소수점 금지), 안전정수범위(`-9007199254740991`~`9007199254740991`, RFC 8785 Appendix B 권고값 재사용) 내로 제한, 배열·중첩 객체는 동일 규칙 재귀 적용.
- 숫자: **`float`/`Decimal`형 값은 payload에서 전면 금지**. 소수가 실제로 필요해지면(현재는 없음) 문자열로 인코딩(예: `"1900.50"`)하고 별도 safe-token류 정규식(`^\d+(\.\d{1,2})?$` 등)으로 검증하는 방식을 권고 — 숫자 모호성을 애초에 문자열 비교 문제로 바꿔 회피.

### 거절 입력
- `float`/`Decimal` 숫자 리터럴(정수가 아닌 모든 숫자) — 즉시 거절.
- 안전정수범위를 벗어난 정수 — 즉시 거절.
- `-0`(의미 있는 유스케이스 없음, 정수 전용 정책상 자동 거절).
- 비-ASCII(Unicode) object key — 즉시 거절(V13 쟁점 자체가 발생하지 않도록 원천 차단).
- 중복 object key — **A/B 공통 과제**(§2-2 표 참조). 원시 JSON 텍스트 수신 단계(예: FastAPI 요청 바디 파싱)에서 `object_pairs_hook`으로 중복을 감지해 거절하는 별도 검증이 필요하다. 이는 `compute_payload_hash()`가 이미 파싱된 dict를 받는 현재 구조상 **이 함수 내부에서는 원천적으로 복구 불가능한 정보**이므로, 더 앞단(요청 바디 역직렬화 계층)에 둬야 한다는 점을 설계 결정 사항으로 남긴다.
- `NaN`/`Infinity` — JSON 표준 자체가 리터럴로 금지하므로 보통 파싱 단계에서 걸러지지만, Python 쪽에서 `float('nan')` 객체를 payload dict에 직접 넣는 비정상 경로를 상정해 명시적으로 거절 목록에 포함.

### 계약 변경이 필요한 항목(결정 전까지는 미확정으로 유지)
1. `Commit8_3b_HMAC_Nonce_V2_Contract_Draft.md` §3에 "payload value 타입 제약"(위 "지원/거절 입력") 절 신설 필요.
2. ADR-017 §12(또는 그 개정판)에 NFC 정규화의 적용 범위가 "canonical string 전체"인지 "payload 직렬화 단계만"인지 재확인 필요(§2-3에서 현재는 "전체"로 해석해 왔음을 전제로 조사했으나, ADR 원문 자체가 명시적으로 이를 구분해 서술하지는 않았다 — Open Question으로 남김).
3. 중복 object key 거절을 어느 계층(FastAPI 요청 바디 파싱 vs `compute_payload_hash` 호출 직전 가드)에 둘지 설계 결정 필요.
4. (A를 채택할 경우에만 해당, 이번 권고안 채택 시 불필요) Python의 UTF-16 코드 유닛 정렬 구현, 기존 NFC 요구와의 충돌 해소 방안.

---

## 4. 미확정 입력이 서명 경로를 통과하지 못하도록 막는 개발용 차단 방안(제안·미구현)

> 아래는 **설계 제안**이며, 이번 턴에서 코드로 구현·배선하지 않았다(지시 "운영
> 정책으로 임의 확정하거나 기존 코드를 변경하지 않는다" 준수). `signing_v2.py`는
> 수정하지 않았다.

제안: `compute_payload_hash()`/`sign_v2()` 호출 **이전에** 선택적으로 삽입할 수
있는 독립 가드 함수 하나를 신설하는 것을 권고한다(의사코드):

```
def validate_payload_schema_interim(payload) -> None:
    """V04/V13 정책 확정 전까지, 모호한 입력이 서명 경로를 통과하지 못하도록
    막는 개발용 가드(제안, 미구현). signing_v2.py와 독립된 신규 함수로 추가하되
    compute_payload_hash() 자체는 변경하지 않는다 — 호출부가 선택적으로
    이 가드를 compute_payload_hash() 앞에 추가 호출하는 형태를 권고."""
    재귀적으로 payload를 순회하며:
      - dict 키: _SAFE_TOKEN_RE(ASCII-only)에 맞지 않으면 거절
      - 숫자 값: Python bool이 아닌 int가 아니면(즉 float/Decimal이면) 거절;
        안전정수범위(±9007199254740991) 밖이면 거절
      - 그 외 타입(string/bool/null/list/dict)은 재귀 허용
    (원시 JSON 텍스트 단계의 중복 키 검증은 이 함수의 책임 범위 밖 —
     §3 "계약 변경이 필요한 항목" 3번 참조)
```

이 가드는 "통과하면 ACCEPTED 보장"이 아니라 **"통과하지 못하면 모호한 입력이
서명 단계까지 가지 않는다"**는 최소 방어선이다. 실제 적용 여부·호출 위치는
ADR 개정 논의에서 결정해야 한다(이 제안서가 임의로 운영 코드에 배선하지 않는다).

---

## 5. 결정이 필요한 사항(요약 — 이 목록만 보면 됨)

1. Option A(JCS) vs **Option B(권고)** 채택 여부.
2. NFC 정규화 적용 범위를 ADR-017 §12에 명시적으로 재서술할지 여부.
3. 중복 object key 거절을 어느 계층에 둘지.
4. §4의 개발용 가드 함수를 실제로 추가·배선할지, 배선한다면 호출 위치.
5. (장기) `ChatBody.context`/`QSubmitBody.answers` 같은 자유형 객체가 추후 HMAC 서명 대상 경로에 포함될 가능성이 있는지 — 포함된다면 이 제안서의 전제("실제 스키마는 이미 B를 만족")가 무너지므로 재검토 필요.

## 6. 구현 결과(격리 계약, 운영 ADR 확정 전 — 이번 갱신 신설)

> 아래는 §3 권고안(Option B)을 실제로 구현해 격리 환경에서 검증한
> 결과다. **이 섹션의 내용은 "격리 개발 계약"일 뿐이며, 운영
> ADR-017 개정이 확정되기 전까지는 운영 계약으로 간주하지 않는다.**
> 상세 실행 로그·벡터별 결과는 `tests/cross_validation/CROSS_VALIDATION_REPORT.md`
> §8~§9를 1차 자료로 한다 — 이 절은 그 요약이다.

### 6-1. 등록 operation 8개와 스키마 근거

`src/idempotency/request_payload_schemas.py`(Python)/
`tests/cross_validation/request_payload_schemas.js`(JS 참조구현)에
아래 8개 operation을 등록했다. 각 필드의 필수 여부·타입·null 허용은
**실제 Pydantic 모델 정의를 그대로 옮긴 것**이며, 모델이 범위를
명시하지 않은 필드에는 임의의 업무 범위를 추가하지 않았다(§1 원칙
재확인).

| operation | 근거(실제 모델) | 비고 |
|---|---|---|
| `reservation_create` | `src/api/api_server.py:75 ReservationCreate` | — |
| `reservation_cancel` | `src/api/api_server.py:86 ReasonBody` | — |
| `reservation_change` | `src/api/api_server.py:90 ChangeBody` | — |
| `slot_generate` | `src/api/api_server.py:97 SlotGenerateBody` | `capacity`는 평범한 int, 코드에 범위 제약 없음 → 범위 발명 안 함 |
| `consultation_status_update` | `src/api/routes_admin_portal.py:112 ConsultationStatusBody` | — |
| `reservation_reject` | `src/api/routes_admin_portal.py:126 RejectReservationBody` | `reason` 길이 2~200자는 실제 코드(`_validate_reason`)의 기존 검증을 재확인한 것(발명 아님) |
| `questionnaire_review` | `src/api/api_server.py:119 QReviewBody` | `decision` 주석은 "REVIEWED\|REJECTED"를 언급하나 코드상 enum 강제 없음 → enum 제약 발명 안 함 |
| `crm_notification` | `src/api/api_server.py:124 CrmNotificationBody` | — |

**레지스트리에 등록하지 않은 것**: `ChatBody.context`(`dict[str, Any]`)와
`QSubmitBody.answers`(`list[dict[str, Any]]`) — 세션 인증 기반 AI
채팅/문진 기능이며 ADR-017 HMAC 서명 프록시 대상이 아니다(§1 핵심
발견 재확인). 레지스트리에 없는 operation은 `UNKNOWN_OPERATION`으로
거절한다(명시적 allow-list 원칙).

### 6-2. raw JSON 선행 검증 — 숫자 토큰·중복 키·-0 정규화·안전정수범위

**두 경로를 구분한다**(`src/idempotency/payload_schema_guard.py`/
`tests/cross_validation/payload_schema_guard.js` 모듈 docstring 재확인):

1. **raw JSON 경로**(`parse_json_strict`/`parseJsonStrict`) — 원시
   JSON **텍스트**를 입력으로 받아야만 가능한 검사:
   - **숫자 토큰 형식**: 정수 토큰만 허용(`-?(0|[1-9][0-9]*)`). 소수점
     또는 `e`/`E` 지수 표기가 있는 토큰(`1.0`, `1e0` 등)은
     `FLOAT_OR_EXPONENT_NOT_ALLOWED`로 즉시 거절 — Python은
     `json.loads(parse_int=, parse_float=)` 훅으로, JS는 커스텀
     토크나이저가 토큰 문자열 자체(`.`/`e`/`E` 존재 여부)를 검사해
     구현했다.
   - **`-0` → `0` 정규화**: Python은 `int("-0") == 0`이라 자동
     정규화되고, JS는 `Object.is(value, -0)`를 명시적으로 검사해
     `0`으로 바꾼다(JS는 -0을 별도 값으로 보존하므로 Python과 달리
     명시적 처리가 필요했다).
   - **중복 object key 거절**: 어느 중첩 레벨에서든 거절(RFC 8785
     §3.1 "MUST NOT" 재확인) — Python은 `object_pairs_hook`, JS는
     자체 recursive-descent 파서로 구현.
2. **이미 파싱된 객체 경로**(`validate_payload_schema_interim`/
   `validatePayloadSchemaInterim`) — ASCII-only object key, 안전정수범위
   (`-9007199254740991`~`9007199254740991`, RFC 8785 Appendix B 권고값
   재사용) 등 "값의 형태"를 검사한다.

### 6-3. "이미 파싱된 객체만으로는 원문 숫자 표현을 검증할 수 없다" — 유지되는 제한

**이 제한은 코드를 고쳐서 없앨 수 있는 것이 아니며, 문서에 그대로
유지한다.** JS는 `1.0`과 `1`이 `JSON.parse()`를 통과하는 순간 완전히
동일한 `Number`가 되어(`Object.is(1.0, 1) === true`) "원문에 소수점이
있었는가"라는 정보가 복구 불가능하게 사라진다 — "이미 파싱된 객체
경로"만 단독으로 쓰면 이 구분을 영원히 할 수 없다. §6-2의 raw JSON
경로는 이 문제를 "해결"한 것이 아니라, **원문 텍스트를 먼저 보는
경로를 추가해 그 문제가 발생하는 지점 자체를 피한 것**이다. raw
JSON 경로를 거치지 않고 이미 파싱된 dict/object를 직접 만들어
`validate_payload_schema_interim()`에만 넘기면(예: 코드에서
`payload={"count": 1.0}`처럼 직접 생성), 이 제한은 그대로 재현된다
— `tests/cross_validation/python_output.json`/`js_output.json`의 V04
항목에 `legacyParsedObjectPathGuardResult` 필드로 이를 실측 기록해
두었다(Python은 거절, JS는 통과 — 여전히 불일치).

### 6-4. NFC 정규화 적용 범위(재확인, 변경 없음)

ADR-017 §12가 이미 명시한 대로, NFC 정규화는 **canonical string
전체**(payload 직렬화 결과 포함)에 적용된다 — `signing_v2.py`의
`compute_payload_hash()`가 수행하며, 이번 Option B 구현(raw JSON
경로·공통 타입 가드·요청별 스키마 가드)은 NFC 처리 로직 자체를
변경하지 않았다. §2-3에서 확인한 대로 RFC 8785(JCS)는 NFC를
요구하지 않지만, Option B는 JCS를 그대로 채택하지 않으므로 이 충돌이
실제로 발생하지 않는다(§2-2 비교표 재확인).

### 6-5. 서명 전 개발용 연결(wrapper)

`src/idempotency/signing_v2_guarded.py`/
`tests/cross_validation/signing_v2_guarded.js` — raw JSON 경로 →
공통 타입 가드 → 요청별 스키마 가드를 통과한 payload만
`signing_v2.compute_payload_hash()`/`sign_v2()`(**기존 함수, 미수정**)로
전달하는 선택적 wrapper. `signing_v2.py` 공개 API와 운영 호출부는
변경하지 않았다. wrapper를 거치지 않고 `signing_v2.py`를 직접
호출하는 기존/향후 경로는 §6-3의 제한을 포함해 아무 보호도 받지
못한다 — `tests/test_signing_v2_guarded.py`의
`ExistingFunctionLimitationTestCase`가 이를 실측으로 확인한다.

### 6-6. 테스트·교차검증 결과

```
python3 -m unittest tests.test_idempotency_store tests.test_gas_orchestration \
  tests.test_signing_v2 tests.test_nonce_store tests.test_payload_schema_guard \
  tests.test_request_payload_schemas tests.test_signing_v2_guarded
# -> Ran 112 tests ... OK
```

교차검증 벡터(22개, `tests/cross_validation/compare_outputs.py`):
**MATCH 13 / RESOLVED_REJECTED 9 / UNRESOLVED 0.** V04(숫자 int/float
구분)·V13(Unicode 키 정렬)이 모두 RESOLVED_REJECTED로 전환됐다 —
Python/JS 양쪽이 동일 사유로 서명 경로 진입 전 일관되게 거절함을
확인했다는 뜻이며, "계약이 운영 정책으로 확정됐다"는 뜻이 아니다
(§5 "결정이 필요한 사항"은 여전히 미결).

### 6-7. Node 검증은 실제 GAS 검증을 대체하지 않는다(재확인, 변경 없음)

이번 구현·교차검증 전부 Node.js 표준 `crypto`/자체 파서로 수행했다.
**실제 GAS(Apps Script, V8 런타임) `Utilities.computeHmacSha256Signature()`·
`JSON.stringify` 동작, CacheService 원자성은 실측하지 않았다** —
`CROSS_VALIDATION_REPORT.md` §7 "실제 GAS 교차검증에 남은 사항"이
그대로 유지된다. Node crypto 통과를 GAS Utilities 검증 완료로
표현하지 않는다.

---

**완료 조건 재확인**: 운영 정책 확정 없음(§6 포함 전체가 격리 개발
계약), 기존 `signing_v2.py`/`nonce_store.py`/`service_hmac.py`/`.gs`
파일 변경 없음, 실제 GAS 접근 없음, 개인정보·실제 예약자료 열람
없음(모델 필드 정의만 확인). §1~§5는 제안, §6은 그 제안의 격리
구현·검증 결과다.
