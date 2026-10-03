// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: NonceTtlBoundary_new.gs — nonce 만료 경계 계산(공통, A/B 둘 다 사용)
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// 목적: "서명은 아직 유효한데 nonce 기록은 이미 사라진" 구간이 생기지
// 않도록, 매 요청마다 **그 요청의 실제 timestamp 기준으로** nonce TTL을
// 계산한다(고정 상수 300초를 그대로 믿지 않는다 — 고정값은 설계상
// 최소 유도값(240초)보다는 크지만, "왜 충분한지"를 매 요청마다 증명하지는
// 않았다. 이 파일은 그 증명을 매 요청 실행 시점에 수행한다).
//
// 근거: signing_v2.py verify_v2()의 delta 판정식(경계 포함):
//   delta = now - timestamp
//   accepted ⟺ -maxSkew <= delta <= maxSkew
//   ⟺ timestamp - maxSkew <= now <= timestamp + maxSkew
// 즉 이 envelope(고정된 timestamp)가 서명 검증을 통과할 수 있는
// 가장 늦은 시각(서명 허용 종료시각)은 **timestamp + maxSkewSeconds**이고,
// 이 경계값 자체도 포함된다(delta == maxSkew는 "> maxSkew"가 아니므로 거부되지 않음).

/**
 * 서명 허용 종료시각 = signed timestamp + max_skew_seconds.
 * @param {number} signedTimestampEpochSeconds
 * @param {number} maxSkewSeconds
 * @return {number}
 */
function computeSignatureAllowedEndTime_(signedTimestampEpochSeconds, maxSkewSeconds) {
  return signedTimestampEpochSeconds + maxSkewSeconds;
}

/**
 * 현재 검증 시각(now) 기준으로, 이 envelope가 서명 검증을 통과할 수 있는
 * 시간이 얼마나 남았는지 계산한다. now가 이미 서명 허용 범위 안이라고
 * 전제한다(이 함수 호출 시점은 verifyV2_가 ACCEPTED를 반환한 직후이므로
 * now는 항상 [timestamp-maxSkew, timestamp+maxSkew] 안에 있다 — 음수가
 * 나오면 호출 순서가 잘못된 것이다).
 *
 * @param {number} nowEpochSeconds
 * @param {number} signedTimestampEpochSeconds
 * @param {number} maxSkewSeconds
 * @return {number} 남은 보존시간(초). 0 이상이어야 한다(경계 포함이므로
 *   0도 유효한 값 — "지금 이 순간이 서명 허용의 마지막 순간"이라는 뜻).
 */
function computeRemainingSignatureRetentionSeconds_(nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds) {
  var allowedEnd = computeSignatureAllowedEndTime_(signedTimestampEpochSeconds, maxSkewSeconds);
  var remaining = allowedEnd - nowEpochSeconds;
  if (remaining < 0) {
    // 호출 순서 오류(서명이 이미 거부됐어야 할 envelope로 nonce TTL을
    // 계산하려 한 것) — fail-closed, 조용히 0으로 깎지 않고 알린다.
    throw new Error(
      "computeRemainingSignatureRetentionSeconds_: 음수(" + remaining + ") — " +
      "서명이 이미 만료된 envelope에 대해 호출됨. verifyV2_ 통과 여부를 먼저 확인했는지 점검할 것."
    );
  }
  return remaining;
}

/**
 * 최종 nonce TTL(초, 정수, CacheService put()에 바로 쓸 수 있는 단위).
 *  - 남은 보존시간 + 여유분(margin)을 더한 뒤 **올림(ceil)** 한다
 *    (CacheService TTL은 정수초 단위이므로, 내림/버림하면 0.x초만큼
 *    보존기간이 모자랄 수 있다 — 반드시 올림해야 안전 쪽으로 치우친다).
 *  - CacheService TTL 최소값(1초)보다 작아지지 않도록 하한을 둔다
 *    (남은 보존시간이 0에 가까워도 TTL 0은 CacheService가 거부한다).
 *  - 비정상적으로 큰 값(설정 오류로 margin이 과도하게 큰 경우 등)은
 *    CacheService TTL 상한(21600초)을 넘지 않는지 확인하고, 넘으면
 *    조용히 자르지 않고 에러를 던진다(설정 오류를 숨기지 않기 위함).
 *
 * @param {number} nowEpochSeconds
 * @param {number} signedTimestampEpochSeconds
 * @param {number} maxSkewSeconds
 * @param {number} marginSeconds 처리 지연 여유분(실험 설정값, 플랫폼 유도값 아님)
 * @return {number}
 */
function computeNonceTtlSeconds_(nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds, marginSeconds) {
  var remaining = computeRemainingSignatureRetentionSeconds_(nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds);
  var rawTtl = remaining + marginSeconds;
  var ttl = Math.ceil(rawTtl);
  if (ttl < 1) ttl = 1; // CacheService put() 최소 TTL(공식 문서, 설계 문서 §1-1)
  if (ttl > 21600) {
    throw new Error(
      "computeNonceTtlSeconds_: 계산된 TTL(" + ttl + "초)이 CacheService 상한(21600초)을 초과함 — " +
      "maxSkewSeconds 또는 marginSeconds 설정을 재검토할 것(조용히 자르지 않음)."
    );
  }
  return ttl;
}

/**
 * 방어적 검증: "서명이 아직 허용되는 시점에 nonce 기록이 먼저 만료되지
 * 않는가"를 매 호출마다 실제로 확인한다. 수학적으로는
 * computeNonceTtlSeconds_()가 이미 이 불변식을 만족하도록 설계됐지만,
 * 이 함수는 그 보장을 "주장"이 아니라 "매 호출 시점의 실제 검사"로
 * 바꾼다 — 요청사항의 "검증한다"를 코드 수준에서 지키기 위함.
 *
 * @param {number} recordTimeEpochSeconds nonce를 기록하는 시각(= now)
 * @param {number} ttlSeconds
 * @param {number} signatureAllowedEndEpochSeconds
 * @throws {Error} 불변식이 깨지면 예외를 던진다(호출부는 이를
 *   BLOCKED_STORE_ERROR로 분류해 업무 실행을 차단해야 한다 — fail-closed).
 */
function assertNonceOutlivesSignatureWindow_(recordTimeEpochSeconds, ttlSeconds, signatureAllowedEndEpochSeconds) {
  var nonceExpiresAt = recordTimeEpochSeconds + ttlSeconds;
  if (nonceExpiresAt < signatureAllowedEndEpochSeconds) {
    throw new Error(
      "NONCE_TTL_INVARIANT_VIOLATED: nonce 만료시각(" + nonceExpiresAt + ")이 " +
      "서명 허용 종료시각(" + signatureAllowedEndEpochSeconds + ")보다 이르다 — " +
      "이 요청은 절대 통과시키면 안 된다."
    );
  }
}

// --------------------------------------------------------------------------
// 중요: 위 세 함수는 "TTL 숫자를 올바르게 계산하는 문제"만 해결한다.
// CacheService의 비영속성(공식 문서: "not guaranteed to persist until its
// expiration time")은 TTL 계산과 **완전히 별개의 위험**이며, 이 파일의
// 어떤 계산으로도 해소되지 않는다. 즉 TTL을 아무리 정확히 계산해도,
// 캐시가 그 TTL이 끝나기 전에 인프라 사유로 사라지면 replay가 통과할
// 수 있다(이전 설계 문서 §3 대안 A 잔존 위험, 로컬 검증 시나리오5
// KNOWN_LIMITATION). 이 파일은 그 위험을 "해소했다"고 주장하지 않는다.
// --------------------------------------------------------------------------

// Properties 변형(B)에서도 동일한 expiresAt 경계 규약을 쓴다:
//   expiresAt = recordTime + ttlSeconds
//   now < expiresAt  → 아직 유효(REJECTED_REPLAY)
//   now >= expiresAt → 만료(Cache가 자동 삭제하는 것과 동일한 경계를 수동 판정)
// 정리(cleanup) 작업도 이 동일한 expiresAt 규약으로 "삭제 가능" 여부를
// 판단해야 한다 — 별도의 더 느슨하거나 더 엄격한 기준을 두지 않는다.
