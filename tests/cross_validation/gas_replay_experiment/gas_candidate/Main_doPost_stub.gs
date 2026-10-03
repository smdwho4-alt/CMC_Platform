// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: Main_doPost_stub_new.gs — 공개 시험 엔드포인트 스텁 + 업무 카운터
//
// *** 후보 코드 — 업로드·실행하지 않음. doPost 배포·Web App 접근 설정
//     변경은 이번 범위에서 수행하지 않는다. ***
//
// ============================================================================
// 공개 시험 엔드포인트 보호 설계 — 처리 순서(중요, 이번 보완의 핵심)
// ============================================================================
//
//   1) action 파싱("exec" | "status"만 허용, 그 외 즉시 거부)
//   2) 서명 검증(verifyV2_) — 실패 시 **nonce·업무 카운터·예산 카운터
//      전부 건드리지 않고 즉시 반환**(요청사항 1: "HMAC 검증 실패 요청은
//      nonce·업무 상태를 변경하지 않는다" — 예산 카운터도 같은 원칙으로
//      묶었다: 아래 3)이 2) 다음에 오므로, 서명이 틀리면 예산도 소모되지
//      않는다).
//   3) 예산·종료시각 가드(checkAndConsumeRequestBudget_, ServerBudgetGuard_new.gs)
//      — **서명이 유효한 요청만** 여기 도달한다. 즉 이 가드가 세는 숫자는
//      "인증된 요청 수"다(요청사항 1의 마지막 항목 — 비인증 noise까지는
//      막지 못한다는 한계를 ServerBudgetGuard_new.gs 상단에 명시).
//   4) action === "status" → 읽기 전용 응답(업무 카운터 증가 없음, nonce
//      가드 호출 안 함 — 요청사항 2).
//      action === "exec" → nonce 가드 → (통과 시에만) 업무 카운터 증가.
//
// (1) 서명에 묶이는 값
//     9필드 전부(method·operation·timestamp·nonce·idempotencyKey·keyId·
//     payloadHash) + **action과 variant를 operation 필드 값에 인코딩**해서
//     서명에 묶는다:
//       exec   → "replay_experiment.variantA.<scenario>" (기존과 동일)
//       status → "replay_experiment.status.variantA"
//     이렇게 하면 exec용으로 서명된 envelope를 status 경로로, 또는 그
//     반대로 재사용하는 것이 서명 불일치로 자동 거부된다.
//
// (2) status 경로도 서명 인증 요구(요청사항 2-1)
//     doStatus_()는 doPost_()와 똑같이 verifyV2_()를 먼저 통과해야
//     호출된다 — 더 약한 별도 인증 경로를 두지 않는다.
//
// (3) 상태 조회는 nonce를 소비하지 않는다(요청사항 2-3 "replay 처리" 명시)
//     읽기 전용이므로 같은 서명된 조회를 서명 유효기간 안에서 여러 번
//     반복해도 업무 상태에 영향이 없다 — 그래서 nonce 저장소를 전혀
//     건드리지 않는다(의도된 동작이지 결함이 아니다). 다만 **예산
//     카운터는 소비한다**(요청사항 2-3 "요청 예산 포함 여부" — 포함하기로
//     결정: status도 인증된 요청인 이상 서버 자원을 쓰므로 예산에 넣지
//     않으면 상태 조회로 예산 우회가 가능해진다).
//
// (4) 비인증 요청에는 카운터·설정 정보를 반환하지 않는다(요청사항 2-4)
//     서명 검증 실패 시 반환값은 {stage, classification}뿐이며
//     businessCounter·requestCount 등은 절대 포함하지 않는다.
//
// (5) remove/reset/cleanup은 여전히 공개 경로에 없다(이전 턴과 동일) —
//     ROUTES_ALLOWLIST_에 "exec"/"status" 둘뿐이다. 실험 예산 수동 초기화
//     (adminResetExperimentBudget_, ServerBudgetGuard_new.gs)와 합성 nonce
//     수동 제거(adminRemoveSyntheticNonce_, AdminOnly_ManualCacheRemoval_new.gs)는
//     전부 편집기 전용이며 이 디스패치 테이블에 올리지 않는다.
//
// (6) 실제 데이터·운영 키·운영 URL 미사용 — 이전과 동일.
//
// ============================================================================

var ACTIVE_VARIANT_VALUES_ = { A: true, B: true };

// 공개 진입점에서 호출 가능한 action은 이 테이블에 있는 것뿐이다.
var ROUTES_ALLOWLIST_ = {
  exec: "doPost_",
  status: "doStatus_",
};

function incrementBusinessCounter_(variant) {
  if (variant === "A") {
    var cache = CacheService.getScriptCache();
    var current = Number(cache.get("business_counter_A") || "0");
    cache.put("business_counter_A", String(current + 1), 21600);
    return current + 1;
  }
  if (variant === "B") {
    var props = PropertiesService.getScriptProperties();
    var current = Number(props.getProperty("business_counter_B") || "0");
    props.setProperty("business_counter_B", String(current + 1));
    return current + 1;
  }
  throw new Error("알 수 없는 variant: " + variant);
}

function readBusinessCounter_(variant) {
  if (variant === "A") {
    var cache = CacheService.getScriptCache();
    return Number(cache.get("business_counter_A") || "0");
  }
  if (variant === "B") {
    var props = PropertiesService.getScriptProperties();
    return Number(props.getProperty("business_counter_B") || "0");
  }
  throw new Error("알 수 없는 variant: " + variant);
}

function routeNonceGuard_(variant, nonce, nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds) {
  if (variant === "A") {
    return checkAndRecordNonce_VariantA_CacheLock_(nonce, nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds);
  }
  if (variant === "B") {
    return checkAndRecordNonce_VariantB_PropertiesLock_(nonce, nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds);
  }
  throw new Error("알 수 없는 variant: " + variant);
}

/**
 * 서버 자신의 현재 시각(초 단위). **요청 본문의 어떤 필드도 신뢰하지
 * 않는다** — 클라이언트가 보낸 "now" 값을 그대로 썼다면, 공격자가
 * 임의의 now를 주장해 서명 스큐 검사와 nonce TTL을 모두 무력화할 수
 * 있었다(이번 실행 전 드라이런에서 실제로 발견된 설계 결함 — 로컬
 * 모의 서버가 request["now"]를 그대로 신뢰해서, 실제 경과 시간과
 * 무관하게 서명이 계속 유효한 것처럼 검증됐다). 그래서 이 값은
 * **서버 코드 자신이 직접 계산**하며, 요청 본문에서 절대 읽지 않는다.
 */
function serverNowEpochSeconds_() {
  return Date.now() / 1000;
}

// 요청 본문에 반드시 있어야 하는 문자열 필드. 타입 검사만 한다(값의
// 의미는 각자 자리에서 검사) — 요청사항 3: "누락·잘못된 타입 등 입력
// 오류를 전부 INTERNAL_ERROR로 분류하지 않도록 명시적 입력 검증을
// 적용한다"를 지키기 위해, 뒤쪽 코드가 undefined/잘못된 타입에 걸려
// ReferenceError/TypeError를 내기 전에 여기서 먼저 걸러낸다.
var REQUIRED_STRING_FIELDS_ = [
  "action", "variant", "method", "operation", "timestamp",
  "nonce", "idempotency_key", "key_id", "signature",
];

/**
 * 입력 형태(타입)만 검사한다 — 값의 의미(등록된 key_id인지, action이
 * exec/status인지 등)는 검사하지 않는다. 실패 시 어떤 필드가 문제인지만
 * 돌려준다(필드 값 자체는 노출하지 않는다 — secret이 엉뚱한 필드에
 * 들어왔을 가능성 등을 고려해 이름만 노출).
 *
 * @return {{ok: true} | {ok: false, field: string}}
 */
function validateRequestShape_(request) {
  if (request === null || typeof request !== "object") {
    return { ok: false, field: "(root)" };
  }
  for (var i = 0; i < REQUIRED_STRING_FIELDS_.length; i++) {
    var f = REQUIRED_STRING_FIELDS_[i];
    if (typeof request[f] !== "string") {
      return { ok: false, field: f };
    }
  }
  if (request.payload === null || typeof request.payload !== "object" || Array.isArray(request.payload)) {
    return { ok: false, field: "payload" };
  }
  return { ok: true };
}

/**
 * 공통 전처리: 입력 형태 검증 → action/variant 유효성 → secret 필드
 * 거부 → key_id 조회 → 서명 검증 → 예산 가드. 어느 하나라도 실패하면
 * 거기서 멈추고, 호출부(doPost_/doStatus_)로 더 진행하지 않는다.
 * 성공 시 { ok:true, now } 형태로 돌려준다 — 이 now는 **서버가 직접
 * 계산한 값**이며, 호출부는 이 값을 재사용해야 한다(요청 본문의
 * request.now를 다시 쓰지 않는다 — 애초에 요청 본문에 now 필드가
 * 있어도 서버는 그 값을 읽지 않는다).
 *
 * @return {{ok: true, now: number} | {ok: false, stage: string, detail: Object}}
 */
function preprocessPublicRequest_(request, expectedAction, expectedActionPrefix) {
  var serverNow = serverNowEpochSeconds_();

  var shape = validateRequestShape_(request);
  if (!shape.ok) {
    return { ok: false, stage: "REQUEST_FIELD_INVALID", detail: { field: shape.field } };
  }

  if (request.action !== expectedAction) {
    // 경로(doPost_/doStatus_)와 본문의 action이 어긋나면 즉시 거부한다 —
    // "status 호출로 들어왔는데 본문은 exec를 주장" 같은 혼동을 차단.
    return { ok: false, stage: "ACTION_INVALID", detail: { action: request.action, expected: expectedAction } };
  }
  if (!ACTIVE_VARIANT_VALUES_[request.variant]) {
    return { ok: false, stage: "VARIANT_INVALID", detail: { variant: request.variant } };
  }

  // secret 필드는 **절대 받지 않는다** — 클라이언트가 자기 비밀키를
  // 요청 본문에 실어 보내는 것 자체를 거부한다(이전 설계는 이 필드를
  // 그대로 믿고 서명을 검증해, 공격자가 자기 secret+서명 쌍을 같이
  // 보내면 항상 통과하는 결함이 있었다 — 서명 검증이 사실상 무의미).
  if (Object.prototype.hasOwnProperty.call(request, "secret")) {
    return { ok: false, stage: "SIGNATURE_REJECTED", detail: { classification: "SECRET_FIELD_NOT_ALLOWED" } };
  }

  // key_id로 서버가 보유한 합성 테스트 레지스트리(TestKeyRegistry_new.gs)
  // 에서 secret을 조회한다. 등록되지 않은 key_id는 거부한다(다른 key로
  // 폴백하지 않음).
  var resolvedSecret = resolveTestKey_(request.key_id);
  if (resolvedSecret === null) {
    return { ok: false, stage: "SIGNATURE_REJECTED", detail: { classification: "UNKNOWN_KEY_ID", keyId: request.key_id } };
  }

  // 서명 검증 — 이 단계를 통과하지 못하면 이후(예산·nonce·카운터)
  // 전부 건드리지 않는다. now는 serverNow(서버 자신의 시계)를 쓴다.
  // secret은 request.secret이 아니라 resolvedSecret(서버가 조회한
  // 값)만 쓴다 — resolvedSecret은 이 함수 밖으로 반환되지 않고, 응답
  // detail에도 들어가지 않는다(키를 HTTP 응답·로그에 넣지 않음).
  //
  // maxSkewSeconds도 request.maxSkewSeconds(클라이언트 값)가 아니라
  // 서버 설정값 EXPERIMENT_MAX_SKEW_SECONDS만 쓴다(이전 턴에 고친
  // now와 동일한 이유). 필드명 주의: 요청 본문은 snake_case
  // (idempotency_key, key_id)이고 verifyV2_() 인자명은 camelCase다 —
  // 혼동해서 request.idempotencyKey/keyId로 읽으면 항상 undefined가
  // 되어 서명 검증이 전부 깨진다(이전 턴에 실측으로 발견·수정).
  var verifyResult = verifyV2_({
    secret: resolvedSecret,
    method: request.method,
    operation: request.operation,
    timestamp: request.timestamp,
    nonce: request.nonce,
    idempotencyKey: request.idempotency_key,
    keyId: request.key_id,
    payload: request.payload,
    signature: request.signature,
    now: serverNow,
    maxSkewSeconds: EXPERIMENT_MAX_SKEW_SECONDS,
  });
  if (verifyResult.classification !== "ACCEPTED") {
    return { ok: false, stage: "SIGNATURE_REJECTED", detail: verifyResult };
  }

  var expectedToken = expectedActionPrefix + request.variant;
  if (request.operation.indexOf(expectedToken) === -1) {
    return { ok: false, stage: "SIGNATURE_REJECTED", detail: { classification: "OPERATION_ACTION_VARIANT_MISMATCH" } };
  }

  // 2) 예산·종료시각 가드 — 서명이 유효한 요청만 여기 도달한다. 여기도
  //    serverNow를 쓴다(요청 본문의 now 아님).
  var budget = checkAndConsumeRequestBudget_(serverNow);
  if (budget.outcome !== "WITHIN_BUDGET") {
    return { ok: false, stage: "SERVER_LIMIT_" + budget.outcome, detail: budget };
  }

  return { ok: true, now: serverNow };
}

/**
 * @param {Object} request { action:"exec", variant, method, operation,
 *   timestamp, nonce, idempotency_key, key_id, payload, signature } —
 *   "secret" 필드는 **있으면 거부된다**(TestKeyRegistry_new.gs 참조).
 *   "now"/"max_skew_seconds" 필드가 있어도 서버는 읽지 않는다(상단 참조).
 * @return {{stage: string, detail: Object}}
 */
function doPost_(request) {
  var pre = preprocessPublicRequest_(request, "exec", "replay_experiment.variant");
  if (!pre.ok) {
    return { stage: pre.stage, detail: pre.detail };
  }

  // 여기도 request.maxSkewSeconds(클라이언트 값)가 아니라 서버 상수를
  // 쓴다 — nonce TTL 계산이 클라이언트가 불러준 skew에 좌우되면 안 된다.
  var nonceResult = routeNonceGuard_(
    request.variant, request.nonce, pre.now, parseFloat(request.timestamp), EXPERIMENT_MAX_SKEW_SECONDS
  );
  if (nonceResult.outcome !== "ACCEPTED") {
    return { stage: "NONCE_REJECTED_OR_BLOCKED", detail: nonceResult };
  }

  var counterValue = incrementBusinessCounter_(request.variant);
  return { stage: "BUSINESS_EXECUTED", detail: { nonce: request.nonce, businessCounter: counterValue } };
}

/**
 * 읽기 전용 상태 조회 — 서명 인증 필요(요청사항 2-1), nonce 소비 없음
 * (요청사항 2-3), 업무 카운터를 증가시키지 않는다(요청사항 2-2).
 *
 * @param {Object} request { action:"status", variant, method, operation,
 *   timestamp, nonce, idempotency_key, key_id, payload, signature } —
 *   "secret" 필드는 있으면 거부된다(doPost_와 동일).
 *   nonce 필드는 9필드 계약상 필수이지만 저장소에 기록되지 않는다 —
 *   아무 유효한 형식의 문자열이나 재사용해도 안전하다(본문 상단 (3) 참조).
 */
function doStatus_(request) {
  var pre = preprocessPublicRequest_(request, "status", "replay_experiment.status.variant");
  if (!pre.ok) {
    return { stage: pre.stage, detail: pre.detail };
  }

  return {
    stage: "STATUS_OK",
    detail: { variant: request.variant, businessCounter: readBusinessCounter_(request.variant) },
  };
}

// ----------------------------------------------------------------------------
// 실제 배포 시 doPost(e)는 대략 이런 형태가 될 것이다(참고용 주석,
// 실행 가능한 코드 아님):
//
//   function doPost(e) {
//     var body = parseJsonStrict_(e.postData.contents);
//     var handlerName = ROUTES_ALLOWLIST_[body.action];
//     if (!handlerName) { return ContentService.createTextOutput('{"stage":"ACTION_INVALID"}'); }
//     var result = this[handlerName](body); // doPost_ 또는 doStatus_만 가능
//     return ContentService.createTextOutput(JSON.stringify(result))
//       .setMimeType(ContentService.MimeType.JSON);
//   }
//
// exec/status 둘 다 POST로 통일한 이유: GET 쿼리 파라미터로 서명 필드를
// 받는 방식도 가능하지만, doPost_/doStatus_가 완전히 동일한 서명 검증
// 로직(preprocessPublicRequest_)을 공유하게 하려면 입력 형태(JSON 본문)를
// 통일하는 편이 중복·불일치 위험이 적다.
// ----------------------------------------------------------------------------
