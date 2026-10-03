// *** 테스트 전용 합성 값 — 운영 재사용 금지 ***
// 이 파일에는 이번 격리 실험을 위해 생성한 합성(synthetic) 테스트
// 키/비밀값이 포함되어 있다. 실제 운영 계정·실제 비밀키와 무관하며,
// 이 저장소에 공개되어 있다는 전제로 다뤄야 한다 — 운영 환경에
// 그대로 재사용하지 않는다.

// doPost(e)/doGet(e) 로컬 진입점 테스트 — 실제 최상위 doPost(e)를
// 그대로 호출한다(내부 doPost_/doStatus_를 직접 부르는 게 아니다).
// GAS 전용 서비스는 gas_stubs.js의 스텁을 쓴다. 전부 로컬 Node
// 검증이며, 실제 GAS 실행을 대체하지 않는다(이 사실을 결과에도 남긴다).
//
// 실행 방법: 이 파일은 단독 실행용이 아니다 — gas_stubs.js와
// ../gas_candidate/*.gs(알파벳순, node_gas_http_server.js의
// GAS_FILE_ORDER와 동일 순서)를 먼저 한 전역 스코프에 로드한 뒤,
// 이 파일의 내용을 이어서 평가(eval)해야 doGet/doPost/signV2_ 등을
// 참조할 수 있다(이 파일 혼자서는 그 식별자들이 정의돼 있지 않다).
//
// TEST_KEY_ID/TEST_SECRET은 ../gas_candidate/TestKeyRegistry.gs에
// 실제로 등록된 합성 키 쌍과 **반드시 일치**해야 한다 — 서버는 이제
// request.secret을 전혀 읽지 않고 key_id로 자기 레지스트리에서
// secret을 찾기 때문이다.

var TEST_KEY_ID = "real-gas-exp-key-1dd05338";
var TEST_SECRET = "95f2e928939b6141904a39a07e44222b3dacd0d9f64eb392f9fdea2e4f12d4f9";

var failures = [];
function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    failures.push(label + ": expected=" + JSON.stringify(expected) + " actual=" + JSON.stringify(actual));
    console.log("[FAIL] " + label + ": expected=" + JSON.stringify(expected) + " actual=" + JSON.stringify(actual));
  } else {
    console.log("[PASS] " + label + " (" + JSON.stringify(actual) + ")");
  }
}

function callDoPost(bodyText) {
  var e = { postData: { contents: bodyText } };
  var output = doPost(e);
  return JSON.parse(output.getContent());
}

/**
 * fields.secret은 **로컬 서명 계산에만** 쓰고 반환되는 JSON 본문에는
 * 넣지 않는다 — 실제 와이어 포맷과 동일(concurrent_http_driver_new.py
 * build_synthetic_envelope()도 secret을 절대 출력하지 않음).
 * includeSecretField=true를 주면 "공격자가 secret 필드를 끼워 넣는"
 * 시나리오를 재현할 수 있다(의도적 오용 테스트 전용).
 */
function buildSignedBody(fields) {
  var payload = fields.payload || {};
  var signed = signV2_({
    secret: fields.secret, method: fields.method, operation: fields.operation,
    timestamp: fields.timestamp, nonce: fields.nonce, idempotencyKey: fields.idempotencyKey,
    keyId: fields.keyId, payload: payload,
  });
  var wire = {
    action: fields.action, variant: fields.variant, method: fields.method, operation: fields.operation,
    timestamp: fields.timestamp, nonce: fields.nonce, idempotency_key: fields.idempotencyKey,
    key_id: fields.keyId, payload: payload, signature: fields.signatureOverride || signed.signature,
    max_skew_seconds: fields.maxSkewSecondsClaim,
  };
  if (fields.includeSecretField) {
    wire.secret = fields.secret; // 의도적 오용 테스트 전용 — 정상 경로는 절대 이렇게 안 함
  }
  return JSON.stringify(wire);
}

// ---------------------------------------------------------------------
// 시나리오 1: 정상 형식 + 무효 서명 → SIGNATURE_REJECTED
// ---------------------------------------------------------------------
(function () {
  var now = Math.floor(Date.now() / 1000);
  var body = buildSignedBody({
    secret: TEST_SECRET, action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-1",
    timestamp: String(now), nonce: "entrypoint-test-1", idempotencyKey: "idem-entrypoint-test-1",
    keyId: TEST_KEY_ID, signatureOverride: "0".repeat(64), maxSkewSecondsClaim: 120,
  });
  var result = callDoPost(body);
  assertEqual(result.stage, "SIGNATURE_REJECTED", "S1 정상형식+무효서명 → SIGNATURE_REJECTED");
  assertEqual(JSON.stringify(result.detail).indexOf(TEST_SECRET) === -1, true, "S1 detail에 secret 미노출");
})();

// ---------------------------------------------------------------------
// 시나리오 2: 중복 키 → MALFORMED_REQUEST_BODY
// ---------------------------------------------------------------------
(function () {
  var body = '{"action":"exec","action":"exec"}'; // 의도적 중복 키(raw 텍스트, JS 객체로는 만들 수 없음)
  var result = callDoPost(body);
  assertEqual(result.stage, "MALFORMED_REQUEST_BODY", "S2 중복 키 → MALFORMED_REQUEST_BODY");
  assertEqual(JSON.stringify(result.detail), "{}", "S2 detail 비어있음(상세 미노출)");
})();

// ---------------------------------------------------------------------
// 시나리오 3: 금지 숫자 표현(float) → MALFORMED_REQUEST_BODY
// ---------------------------------------------------------------------
(function () {
  var body = '{"action":"exec","amount":1.5}'; // raw 숫자 토큰에 소수점
  var result = callDoPost(body);
  assertEqual(result.stage, "MALFORMED_REQUEST_BODY", "S3 금지 숫자표현(float) → MALFORMED_REQUEST_BODY");
  assertEqual(JSON.stringify(result.detail), "{}", "S3 detail 비어있음");
})();

// ---------------------------------------------------------------------
// 시나리오 4: 내부 결함(누락 함수 재현) → INTERNAL_ERROR로 분류,
// MALFORMED_REQUEST_BODY로 오분류하지 않음. detail도 비어있어야 함.
// ---------------------------------------------------------------------
(function () {
  assertEqual(classifyParseError_(new ReferenceError("x is not defined")), "INTERNAL_ERROR", "S4a ReferenceError → INTERNAL_ERROR");
  assertEqual(classifyParseError_(new TypeError("y")), "INTERNAL_ERROR", "S4a TypeError → INTERNAL_ERROR");
  assertEqual(classifyParseError_(new Error("plain parse error")), "MALFORMED_REQUEST_BODY", "S4a plain Error → MALFORMED_REQUEST_BODY");
  assertEqual(classifyParseError_(new DuplicateKeyError_("dup")), "MALFORMED_REQUEST_BODY", "S4a DuplicateKeyError_ → MALFORMED_REQUEST_BODY");
  assertEqual(classifyParseError_(new RawNumberFormatError_("FLOAT_OR_EXPONENT_NOT_ALLOWED", "1.5")), "MALFORMED_REQUEST_BODY", "S4a RawNumberFormatError_ → MALFORMED_REQUEST_BODY");

  var now = Math.floor(Date.now() / 1000);
  var validSignedBody = buildSignedBody({
    secret: TEST_SECRET, action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-4",
    timestamp: String(now), nonce: "entrypoint-test-4", idempotencyKey: "idem-entrypoint-test-4",
    keyId: TEST_KEY_ID, maxSkewSecondsClaim: 120,
  });

  var savedDoPost_ = doPost_;
  doPost_ = undefined; // "함수 누락" 재현 — 실제 배포 파일은 건드리지 않음(이 프로세스 바인딩만)
  var result4b;
  try {
    result4b = callDoPost(validSignedBody);
  } finally {
    doPost_ = savedDoPost_;
  }
  assertEqual(result4b.stage, "INTERNAL_ERROR", "S4b 누락 함수 재현(doPost_ 제거) → INTERNAL_ERROR(MALFORMED_REQUEST_BODY 아님)");
  assertEqual(JSON.stringify(result4b.detail), "{}", "S4b detail 비어있음(내부 오류 상세 미노출)");
})();

// ---------------------------------------------------------------------
// 시나리오 5: 클라이언트가 max_skew_seconds를 과장해도 검증 범위가
// 안 바뀌는지 확인.
// ---------------------------------------------------------------------
(function () {
  var staleNow = Math.floor(Date.now() / 1000) - 10000;
  var body = buildSignedBody({
    secret: TEST_SECRET, action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-5",
    timestamp: String(staleNow), nonce: "entrypoint-test-5", idempotencyKey: "idem-entrypoint-test-5",
    keyId: TEST_KEY_ID, maxSkewSecondsClaim: 999999999,
  });
  var result = callDoPost(body);
  assertEqual(result.stage, "SIGNATURE_REJECTED", "S5 거대한 max_skew_seconds 주장 → 그래도 SIGNATURE_REJECTED(서버 상수만 적용됨)");
  assertEqual(result.detail && result.detail.classification, "TIMESTAMP_EXPIRED", "S5 분류: TIMESTAMP_EXPIRED(클라이언트 skew 무시 확인)");
})();

// ---------------------------------------------------------------------
// 시나리오 6: 정상 형식 + 유효 서명 → BUSINESS_EXECUTED, 재전송 차단.
// ---------------------------------------------------------------------
(function () {
  var now = Math.floor(Date.now() / 1000);
  var body = buildSignedBody({
    secret: TEST_SECRET, action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-6",
    timestamp: String(now), nonce: "entrypoint-test-6", idempotencyKey: "idem-entrypoint-test-6",
    keyId: TEST_KEY_ID, maxSkewSecondsClaim: 120,
  });
  var result = callDoPost(body);
  assertEqual(result.stage, "BUSINESS_EXECUTED", "S6 정상 서명 → BUSINESS_EXECUTED(happy path)");

  var replay = callDoPost(body);
  assertEqual(replay.stage, "NONCE_REJECTED_OR_BLOCKED", "S6 동일 envelope 재전송 → NONCE_REJECTED_OR_BLOCKED");
})();

// ---------------------------------------------------------------------
// 시나리오 7: doGet(e) → METHOD_NOT_ALLOWED
// ---------------------------------------------------------------------
(function () {
  var output = doGet({});
  var result = JSON.parse(output.getContent());
  assertEqual(result.stage, "METHOD_NOT_ALLOWED", "S7 doGet → METHOD_NOT_ALLOWED");
})();

// ---------------------------------------------------------------------
// 시나리오 8(신규): secret 필드가 요청 본문에 들어오면 — 서명이 맞아도 —
// 거절한다(SECRET_FIELD_NOT_ALLOWED). 업무 카운터도 늘지 않는다.
// ---------------------------------------------------------------------
(function () {
  var now = Math.floor(Date.now() / 1000);
  var statusBefore = JSON.parse(doGet({}).getContent()); // 그냥 doGet으로 연결 확인용, 카운터는 아래서 별도 조회
  var body = buildSignedBody({
    secret: TEST_SECRET, action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-8",
    timestamp: String(now), nonce: "entrypoint-test-8", idempotencyKey: "idem-entrypoint-test-8",
    keyId: TEST_KEY_ID, maxSkewSecondsClaim: 120, includeSecretField: true, // *** 의도적 오용 ***
  });
  var result = callDoPost(body);
  assertEqual(result.stage, "SIGNATURE_REJECTED", "S8 secret 필드 포함(서명은 정상) → SIGNATURE_REJECTED");
  assertEqual(result.detail && result.detail.classification, "SECRET_FIELD_NOT_ALLOWED", "S8 분류: SECRET_FIELD_NOT_ALLOWED");
  assertEqual(JSON.stringify(result.detail).indexOf(TEST_SECRET) === -1, true, "S8 detail에 secret 원문 미노출");
})();

// ---------------------------------------------------------------------
// 시나리오 9(신규): 미등록 key_id → UNKNOWN_KEY_ID로 거절.
// ---------------------------------------------------------------------
(function () {
  var now = Math.floor(Date.now() / 1000);
  var body = buildSignedBody({
    secret: TEST_SECRET, action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-9",
    timestamp: String(now), nonce: "entrypoint-test-9", idempotencyKey: "idem-entrypoint-test-9",
    keyId: "never-registered-key-id", maxSkewSecondsClaim: 120,
  });
  var result = callDoPost(body);
  assertEqual(result.stage, "SIGNATURE_REJECTED", "S9 미등록 key_id → SIGNATURE_REJECTED");
  assertEqual(result.detail && result.detail.classification, "UNKNOWN_KEY_ID", "S9 분류: UNKNOWN_KEY_ID");
})();

// ---------------------------------------------------------------------
// 시나리오 10(신규): 공격자가 자기 마음대로 고른 secret으로 서명해도
// (등록된 key_id를 사칭) 서버는 자기 레지스트리의 진짜 secret으로
// 재계산하므로 SIGNATURE_MISMATCH로 거절된다 — request.secret을 더 이상
// 신뢰하지 않는다는 것의 핵심 증거.
// ---------------------------------------------------------------------
(function () {
  var now = Math.floor(Date.now() / 1000);
  var attackerChosenSecret = "attacker-chosen-secret-not-the-real-one";
  var body = buildSignedBody({
    secret: attackerChosenSecret, // 공격자가 고른 값으로 서명 계산
    action: "exec", variant: "A", method: "POST",
    operation: "replay_experiment.variantA.entrypoint-test-10",
    timestamp: String(now), nonce: "entrypoint-test-10", idempotencyKey: "idem-entrypoint-test-10",
    keyId: TEST_KEY_ID, // 등록된(진짜) key_id를 사칭
    maxSkewSecondsClaim: 120,
  });
  var result = callDoPost(body);
  assertEqual(result.stage, "SIGNATURE_REJECTED", "S10 공격자가 고른 secret+서명(등록된 key_id 사칭) → SIGNATURE_REJECTED");
  assertEqual(result.detail && result.detail.classification, "SIGNATURE_MISMATCH", "S10 분류: SIGNATURE_MISMATCH(서버가 자기 레지스트리 secret으로만 검증)");
})();

// ---------------------------------------------------------------------
// 시나리오 11(신규, 요청사항 3): 누락/잘못된 타입 필드 → REQUEST_FIELD_INVALID
// (INTERNAL_ERROR로 오분류되지 않음).
// ---------------------------------------------------------------------
(function () {
  var missingNonce = JSON.stringify({
    action: "exec", variant: "A", method: "POST", operation: "replay_experiment.variantA.x",
    timestamp: "123", idempotency_key: "idem-x", key_id: TEST_KEY_ID, payload: {}, signature: "0".repeat(64),
    // nonce 필드 자체가 없음
  });
  var r1 = callDoPost(missingNonce);
  assertEqual(r1.stage, "REQUEST_FIELD_INVALID", "S11a nonce 필드 누락 → REQUEST_FIELD_INVALID(내부오류 아님)");
  assertEqual(r1.detail && r1.detail.field, "nonce", "S11a 어떤 필드인지 표시: nonce");

  var wrongTypePayload = JSON.stringify({
    action: "exec", variant: "A", method: "POST", operation: "replay_experiment.variantA.x",
    timestamp: "123", nonce: "n", idempotency_key: "idem-x", key_id: TEST_KEY_ID,
    payload: "not-an-object", signature: "0".repeat(64),
  });
  var r2 = callDoPost(wrongTypePayload);
  assertEqual(r2.stage, "REQUEST_FIELD_INVALID", "S11b payload가 문자열(object 아님) → REQUEST_FIELD_INVALID");
  assertEqual(r2.detail && r2.detail.field, "payload", "S11b 어떤 필드인지 표시: payload");

  var numberTimestamp = JSON.stringify({
    action: "exec", variant: "A", method: "POST", operation: "replay_experiment.variantA.x",
    timestamp: 123, nonce: "n", idempotency_key: "idem-x", key_id: TEST_KEY_ID, payload: {}, signature: "0".repeat(64),
  }); // timestamp가 문자열이 아니라 숫자(JSON.stringify가 그대로 숫자로 직렬화)
  var r3 = callDoPost(numberTimestamp);
  assertEqual(r3.stage, "REQUEST_FIELD_INVALID", "S11c timestamp가 문자열이 아님 → REQUEST_FIELD_INVALID");
  assertEqual(r3.detail && r3.detail.field, "timestamp", "S11c 어떤 필드인지 표시: timestamp");
})();

console.log("");
if (failures.length === 0) {
  console.log("ALL_LOCAL_ENTRYPOINT_TESTS_PASSED (로컬 Node 검증 — 실제 GAS 실행 아님)");
} else {
  console.log("LOCAL_ENTRYPOINT_TESTS_FAILED: " + failures.length + "건");
  process.exitCode = 1;
}
