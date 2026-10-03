// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: VariantA_CacheLock_new.gs — CacheService + Script Lock
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// 공통 전제(요청사항 그대로):
//  - 이 함수는 서명 검증(verifyV2_, SignatureV2Port_new.gs)이 "ACCEPTED"를
//    반환한 뒤에만 호출되어야 한다 — 서명 검증 → nonce 소비 → 업무 실행
//    순서를 이 파일 혼자서는 강제하지 않는다(호출부 책임, Main_doPost_stub_new.gs 참조).
//  - 같은 스크립트의 수신 경로는 전부 동일한 Script Lock(getScriptLock())을
//    사용해야 한다 — User/Document Lock은 사용하지 않는다(설계 문서 §1-1 근거:
//    Script Lock만 "사용자 신원과 무관하게" 전역 상호배제를 제공함).
//  - 잠금 획득 실패(타임아웃) 또는 저장소 오류 시 업무 실행을 차단한다(fail-closed).
//  - 잠금 해제는 finally에서 수행한다.
//
// CacheService 관련 공식 확인 사실(2026-10-03 WebFetch, 설계 문서 §1-1):
//  - get/put/remove만 존재, 원자적 check-and-set 없음 → 그래서 Script Lock이 필요함.
//  - "The data you write to the cache is not guaranteed to persist until its
//    expiration time. You must be prepared to get back null from all reads."
//    → 이 비영속성 때문에, TTL 안에서도 캐시가 사라지면 replay가 통과할 수
//    있다(알려진 보안 한계, 검증 시나리오 §6 참조). 이 파일은 그 위험을
//    해소하지 않으며, 해소를 주장하지도 않는다.
//  - TTL 허용 범위 1~21600초. 아래 함수가 계산하는 동적 TTL은
//    NonceTtlBoundary_new.gs의 computeNonceTtlSeconds_()가 이 범위를
//    벗어나면 스스로 예외를 던지므로, 이 파일에서 별도로 다시 검사하지 않는다.
//
// 이번 보완(nonce 만료 경계): TTL을 고정 상수로 쓰지 않고, **이 요청의
// 실제 signed timestamp**로부터 매번 계산한다(NonceTtlBoundary_new.gs).
// 계산 직후 assertNonceOutlivesSignatureWindow_()로 "서명이 아직 허용되는
// 시점에 nonce가 먼저 만료되지 않는가"를 실제로 검증하고, 실패하면
// BLOCKED_STORE_ERROR로 분류해 업무 실행을 차단한다(fail-closed).

/**
 * @param {string} nonce 합성 테스트 nonce (운영 데이터 아님)
 * @param {number} nowEpochSeconds 호출(=서명 검증 통과) 시각(Unix epoch 초)
 * @param {number} signedTimestampEpochSeconds 이 envelope의 서명 대상 timestamp
 * @param {number} maxSkewSeconds 이 요청에 적용된 서명 스큐 허용치
 * @return {{outcome: string, error: (string|undefined)}}
 *   outcome: "ACCEPTED" | "REJECTED_REPLAY" | "BLOCKED_LOCK_TIMEOUT" | "BLOCKED_STORE_ERROR"
 */
function checkAndRecordNonce_VariantA_CacheLock_(nonce, nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds) {
  var lock = LockService.getScriptLock();
  var acquired = false;
  try {
    acquired = lock.tryLock(LOCK_WAIT_TIMEOUT_MS);
    if (!acquired) {
      // waitLock()이 아닌 tryLock()을 쓴 이유: waitLock()은 타임아웃 시
      // 예외를 던지므로(§SignatureV2Port_new.gs 상단 주석 참조 — 공식 문서,
      // "throws an exception ... instead of returning false") 호출부에서
      // outcome 값으로 일관되게 분기하려면 예외 대신 boolean을 받는
      // tryLock()이 더 다루기 쉽다고 판단했다(실험 설계 선택, 필수 아님).
      return { outcome: "BLOCKED_LOCK_TIMEOUT" };
    }

    var cache = CacheService.getScriptCache(); // 모든 사용자 공용 스코프 — User/Document 캐시 아님
    var existing;
    try {
      existing = cache.get(nonce);
    } catch (e) {
      return { outcome: "BLOCKED_STORE_ERROR", error: String(e) };
    }

    if (existing !== null) {
      return { outcome: "REJECTED_REPLAY" };
    }

    try {
      var signatureAllowedEnd = computeSignatureAllowedEndTime_(signedTimestampEpochSeconds, maxSkewSeconds);
      var ttlSeconds = computeNonceTtlSeconds_(
        nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds, EXPERIMENT_TTL_MARGIN_SECONDS
      );
      assertNonceOutlivesSignatureWindow_(nowEpochSeconds, ttlSeconds, signatureAllowedEnd);
      cache.put(nonce, String(nowEpochSeconds), ttlSeconds);
    } catch (e) {
      // TTL 계산 오류·불변식 위반·CacheService 쓰기 실패를 전부
      // 같은 fail-closed 경로로 묶는다 — 어느 쪽이든 nonce를 신뢰할 수
      // 없는 상태로 기록하느니 업무 실행을 막는 쪽이 안전하다.
      return { outcome: "BLOCKED_STORE_ERROR", error: String(e) };
    }

    return { outcome: "ACCEPTED" };
  } finally {
    if (acquired) {
      lock.releaseLock();
    }
  }
}
