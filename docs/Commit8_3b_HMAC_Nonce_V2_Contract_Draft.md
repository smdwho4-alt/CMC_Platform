# Commit8-3b — HMAC Canonical String v2(keyId 포함) 계약 초안

> **상태**: **격리 개발용 제안 계약 초안이다 — ADR-017의 공식 개정이 아니다.**
> ADR-017 §12는 `protocolVersion="1"`(8필드, keyId 없음)만 확정했다. 이 문서가
> 정의하는 `protocolVersion="2"`는 `src/idempotency/signing_v2.py`의 격리
> 구현·테스트를 위한 **제안**이며, PM/아키텍처가 ADR-017을 실제로 개정하기
> 전까지는 운영 계약으로 간주하지 않는다. 운영 라우트에 연결되지 않았다.
> **작성일**: 2026-10-03
> **기준 commit**: `13dab1d60290b3249e5a566e3f7a020cb659b57c`

---

## 1. Canonical String v2 — 필드·순서·구분자

```
CMC-HMAC-SHA256
2
<HTTP Method>
<operation>
<timestamp>
<nonce>
<idempotencyKey>
<keyId>
<payloadHash>
```

- **9개 필드**(v1의 8필드 + `keyId` 1개 삽입). v1(`protocolVersion="1"`) 대비 변경점은 `keyId`가 `idempotencyKey`와 `payloadHash` 사이에 삽입된 것과 버전 리터럴이 `"1"`→`"2"`로 바뀐 것뿐 — 나머지 7개 필드의 의미·순서는 v1과 동일하다.
- **구분자**: LF(`\n`)로 9개 줄을 결합, 트레일링 개행 없음(v1과 동일 관행).
- **인코딩**: 전체 문자열을 UTF-8로 인코딩한 뒤 HMAC-SHA256 계산.
- **keyId는 서명 대상에 포함된다**(이전 제안서의 "서명 대상 밖" 대안을 이번 작업 지시에 따라 철회하고, 서명 대상 포함안으로 전환했다).

## 2. 필드 형식 검증 — Canonical String 모호성 방지

구분자(`\n`)가 필드 값 안에 섞여 들어가면 서로 다른 (method, operation, …) 조합이 동일한 Canonical String으로 합쳐질 수 있다(경계 모호성). 이를 막기 위해 **각 필드를 join하기 전에 반드시 형식을 검증**하며, 하나라도 실패하면 `FIELD_FORMAT_INVALID`로 즉시 거부한다(서명 계산 자체를 시도하지 않음):

| 필드 | 형식 규칙 |
|---|---|
| `method` | `{"GET","POST","PUT","PATCH","DELETE"}` 중 하나(대문자 고정) |
| `operation` | `^[A-Za-z0-9_.\-:]{1,200}$`(idempotency key와 동일 safe-token 정규식 재사용) |
| `timestamp` | `^\d+(\.\d+)?$`(음수·지수표기·공백 불허) |
| `nonce` | `^[A-Za-z0-9_.\-:]{1,200}$` |
| `idempotencyKey` | `^[A-Za-z0-9_.\-:]{1,200}$` |
| `keyId` | `^[A-Za-z0-9_.\-:]{1,200}$` |
| `payloadHash` | `^[0-9a-f]{64}$`(SHA-256 hex, 정확히 64자 소문자) |

이 정규식들은 전부 `\n`을 비롯한 제어문자를 원천적으로 허용하지 않으므로, 어떤 필드 값도 구분자를 삽입해 Canonical String의 줄 수·경계를 바꿀 수 없다. **모든 필드는 필수다 — 누락값(`None`)은 허용하지 않고 즉시 오류로 거부한다**(빈 문자열로 치환하지 않음 — 빈 문자열 치환은 "진짜 빈 값"과 "누락"을 구분 못 하게 만드는 또 다른 모호성이므로).

## 3. timestamp 단위·payloadHash 계산 규칙(v1과 동일, 재확인)

- `timestamp`: Unix epoch **초**, 문자열로 직렬화(기존 `service_hmac.py` 관행 유지 — ADR-017 §12가 단위를 명시하지 않아 기존 코드에서 추정한 관행임을 재확인).
- `payloadHash`: payload(JSON 객체)를 **키를 유니코드 코드포인트순 정렬 후 compact 직렬화**(`json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`) → **Unicode NFC 정규화** → UTF-8 인코딩 → SHA-256 → 소문자 hex.

## 4. 이전 형식 자동 fallback 금지(재확인)

검증자는 수신한 `protocolVersion`이 `"2"`가 아니면(예: `"1"` 또는 미지원 값) **즉시 `PROTOCOL_VERSION_MISMATCH`로 거부**하고, v1이나 기존 5필드 레거시 형식으로 재시도하지 않는다. `src/auth/service_hmac.py`(5필드, 운영 호출부 0건)는 이번 구현에서 전혀 import하지 않으며 수정하지도 않는다.

## 5. 오류 분류 — 내부용, HTTP 계약 확정 아님

아래 분류는 `src/idempotency/signing_v2.py`의 **내부 반환값**일 뿐이며, 실제 HTTP 오류 응답 스키마(상태코드·JSON 형식)는 이 문서가 확정하지 않는다. `UNKNOWN_KEY_ID`/`SIGNATURE_MISMATCH`/`TIMESTAMP_EXPIRED`/`TIMESTAMP_FUTURE`/`PROTOCOL_VERSION_MISMATCH`는 API Contract §12가 이미 제안한 19종 오류코드 이름을 그대로 재사용했다. `KEY_REVOKED`/`KEY_GRACE_EXPIRED`/`FIELD_FORMAT_INVALID`는 **그 19종에 없는, 이번 격리 구현이 임시로 도입한 내부 분류**이며 운영 오류코드 체계에 그대로 채택될지는 미확정(Open Question, 이전 계약 정합성 보완안 §3-2 재확인).

---

**완료 조건 재확인**: 이 문서는 ADR-017을 개정하지 않으며 운영 계약을 확정하지 않는다. 실제 키·Secret을 포함하지 않는다. `service_hmac.py`를 수정하지 않는다.
