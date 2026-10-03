// Commit8-3b 격리 GAS 교차검증 패키지 — Main.gs
//
// 실행 진입점은 runAllVectors() 하나뿐이다. Apps Script 편집기에서
// 이 함수를 선택해 "실행"하면 Fixtures.gs의 22개 벡터 **전부**
// (MATCH 12개 + 거절 9개 + 필드거절 1개(V07) = 22개)를 비교해
// Logger에 PASS/FAIL을 출력한다. 제외되는 벡터는 없다 — V07을 이전
// 패키지 버전에서 "crypto/직렬화와 무관"이라는 이유로 제외했던 것은
// 사전 승인된 제외가 아니라 작성자의 자체 판단이었고, 재검토 결과
// 이미 포팅된 validateField_()/signV2_()로 그대로 검증 가능함을
// 확인해 이번 갱신에서 포함했다(Expected.gs 참조).
//
// 기대값 원천 표기(Expected.gs의 verificationBasis 재확인): 각 PASS
// 로그 줄에 "[독립검증:OpenSSL]"(V01·V02) 또는 "[Python 비교]"(나머지
// 전부)를 함께 출력한다 — Python 결과를 복사해 비교한 것을 독립
// 검증이라고 표현하지 않기 위함이다.
//
// 로깅 원칙(엄수): secret 원문(SYNTHETIC_KEYS의 값)과 payload
// 원문(payloadNormalizationResult 등 평문 내용)은 어떤 Logger.log()
// 호출에도 절대 포함하지 않는다. 실패 시에도 "어떤 필드가
// 불일치했는가"(필드 이름)와 hex 값(해시·서명 — 되돌릴 수 없는 값)만
// 출력한다.

function basisLabel_(basis) {
  return basis === "INDEPENDENT_OPENSSL" ? "독립검증:OpenSSL" : "Python 비교";
}

function findVector_(vid) {
  for (var i = 0; i < FIXTURES.vectors.length; i++) {
    if (FIXTURES.vectors[i].id === vid) return FIXTURES.vectors[i];
  }
  throw new Error("벡터를 찾을 수 없음: " + vid);
}

function runGuardOnPayload_(payload) {
  try {
    validatePayloadSchemaInterim_(payload);
    return { accepted: true };
  } catch (e) {
    if (e instanceof PayloadSchemaUnresolvedError_) {
      return { accepted: false, reason: e.reason, path: e.path };
    }
    throw e;
  }
}

function runRawGuard_(rawJsonText) {
  try {
    var parsed = parseJsonStrict_(rawJsonText);
    return { accepted: true, parsed: parsed };
  } catch (e) {
    if (e instanceof DuplicateKeyError_) {
      return { accepted: false, reason: "DUPLICATE_KEY" };
    }
    if (e instanceof RawNumberFormatError_) {
      return { accepted: false, reason: e.reason };
    }
    throw e;
  }
}

function runMatchVector_(vid) {
  var vec = findVector_(vid);
  var expected = EXPECTED_MATCH[vid];
  var secret = SYNTHETIC_KEYS[vec.sign.secretKeyId]; // 로그에 출력 금지 — 비교에만 사용
  var signOut = signV2_({
    secret: secret,
    method: vec.sign.method,
    operation: vec.sign.operation,
    timestamp: vec.sign.timestamp,
    nonce: vec.sign.nonce,
    idempotencyKey: vec.sign.idempotencyKey,
    keyId: vec.sign.keyId,
    payload: vec.sign.payload,
  });

  var mismatches = [];
  if (signOut.sortedJsonUtf8Hex !== expected.payloadUtf8Hex) mismatches.push("payloadUtf8Hex");
  if (signOut.payloadHash !== expected.payloadHash) mismatches.push("payloadHash");
  if (signOut.canonicalUtf8Hex !== expected.canonicalUtf8Hex) mismatches.push("canonicalUtf8Hex");
  if (signOut.signature !== expected.signature) mismatches.push("signature");

  var pass = mismatches.length === 0;
  if (pass) {
    Logger.log("[%s] PASS [%s]", vid, basisLabel_(expected.verificationBasis));
  } else {
    // 불일치 필드명만 출력 — 값 자체(해시/서명 hex)는 되돌릴 수 없는
    // 값이라 secret·payload 노출이 아니지만, 그래도 기본은 필드명만
    // 남기고 상세 hex 비교는 필요 시 수동으로 한다(로그 최소화 원칙).
    Logger.log("[%s] FAIL [%s] - mismatched fields: %s", vid, basisLabel_(expected.verificationBasis), mismatches.join(","));
  }
  return pass;
}

function runRejectVector_(vid) {
  var vec = findVector_(vid);
  var expected = EXPECTED_REJECT[vid];
  var actual;

  if (vec.rawJsonDuplicateCheck || Object.prototype.hasOwnProperty.call(vec, "rawJsonText")) {
    actual = runRawGuard_(vec.rawJsonText);
  } else if (Object.prototype.hasOwnProperty.call(vec, "guardDirectPayload")) {
    actual = runGuardOnPayload_(vec.guardDirectPayload);
  } else {
    actual = runGuardOnPayload_(vec.sign.payload);
  }

  var pass = actual.accepted === false && actual.reason === expected.reason;
  if (pass) {
    Logger.log("[%s] PASS [%s] (reason=%s)", vid, basisLabel_(expected.verificationBasis), actual.reason);
  } else {
    Logger.log("[%s] FAIL [%s] - expected reason=%s, actual accepted=%s reason=%s", vid, basisLabel_(expected.verificationBasis), expected.reason, actual.accepted, actual.reason);
  }
  return pass;
}

function runFieldRejectionVector_(vid) {
  var vec = findVector_(vid);
  var expected = EXPECTED_FIELD_REJECTION[vid];
  var secret = SYNTHETIC_KEYS[vec.sign.secretKeyId]; // 로그 출력 금지

  var threwExpected = false;
  var actualErrorName = null;
  try {
    signV2_({
      secret: secret,
      method: vec.sign.method,
      operation: vec.sign.operation,
      timestamp: vec.sign.timestamp,
      nonce: vec.sign.nonce,
      idempotencyKey: vec.sign.idempotencyKey,
      keyId: vec.sign.keyId,
      payload: vec.sign.payload,
    });
  } catch (e) {
    actualErrorName = e.name || "Error";
    threwExpected = e instanceof FieldFormatError_;
  }

  var pass = threwExpected;
  if (pass) {
    Logger.log("[%s] PASS [%s] (signV2_가 FieldFormatError_를 정상적으로 던짐 — nonce LF 삽입 거절 확인)", vid, basisLabel_(expected.verificationBasis));
  } else {
    Logger.log("[%s] FAIL [%s] - FieldFormatError_ 기대했으나 실제: %s", vid, basisLabel_(expected.verificationBasis), actualErrorName || "(예외 없이 통과함)");
  }
  return pass;
}

/**
 * 유일한 실행 진입점. Apps Script 편집기에서 직접 선택해 실행한다.
 * (이 패키지 작성 시점에는 아직 실행하지 않았다 — README.md 참조.)
 */
function runAllVectors() {
  var matchIds = Object.keys(EXPECTED_MATCH);
  var rejectIds = Object.keys(EXPECTED_REJECT);
  var fieldRejectionIds = Object.keys(EXPECTED_FIELD_REJECTION);

  var matchPass = 0;
  matchIds.forEach(function (vid) {
    if (runMatchVector_(vid)) matchPass++;
  });

  var rejectPass = 0;
  rejectIds.forEach(function (vid) {
    if (runRejectVector_(vid)) rejectPass++;
  });

  var fieldRejectionPass = 0;
  fieldRejectionIds.forEach(function (vid) {
    if (runFieldRejectionVector_(vid)) fieldRejectionPass++;
  });

  var totalPass = matchPass + rejectPass + fieldRejectionPass;
  var totalCount = matchIds.length + rejectIds.length + fieldRejectionIds.length;
  Logger.log("=== 요약 ===");
  Logger.log("MATCH 대상 %s개 중 PASS %s개", matchIds.length, matchPass);
  Logger.log("거절 대상 %s개 중 PASS %s개", rejectIds.length, rejectPass);
  Logger.log("필드거절 대상 %s개 중 PASS %s개(V07)", fieldRejectionIds.length, fieldRejectionPass);
  Logger.log("전체 %s개 중 PASS %s개, FAIL %s개 — 22개 벡터 전부 포함, 제외 없음", totalCount, totalPass, totalCount - totalPass);

  return {
    matchPass: matchPass, matchTotal: matchIds.length,
    rejectPass: rejectPass, rejectTotal: rejectIds.length,
    fieldRejectionPass: fieldRejectionPass, fieldRejectionTotal: fieldRejectionIds.length,
  };
}
