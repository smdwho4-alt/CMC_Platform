// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: VariantB_PropertiesLock_new.gs — Script Properties + Script Lock
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
// *** 이 변형(B)은 운영 채택안이 아니다. 소량 합성 데이터로 A와 비교하기
//     위한 실험 전용 코드다. ***
//
// PropertiesService 관련 공식 확인 사실(2026-10-03 WebFetch, 설계 문서 §1-1):
//  - Script/User/Document 3종, "Properties cannot be shared between scripts."
//  - 전체 저장 한도 500KB/스토어, 값 최대 9KB/건(PROPERTIES_TOTAL_LIMIT_BYTES/
//    PROPERTIES_MAX_VALUE_BYTES, ExperimentConfig_new.gs) — 이 한도를 넘기면
//    setProperty()가 실패한다고 추정되나, 정확한 예외 종류는 이번 조사에서
//    확인하지 못했다(공백) — 운영 배포 전 반드시 실측 필요.
//  - 원자적 set-if-absent 없음(get/set/delete만 확인) → CacheService와
//    동일하게 Script Lock이 필요하다.
//  - CacheService의 `put(key, value, expirationInSeconds)`와 달리
//    **자동 TTL 만료가 없다** → 값에 기록 시각을 직접 저장하고, 이 함수가
//    매 호출마다 수동으로 TTL 경과 여부를 계산해야 한다.
//  - 명시적 영속성 보장 문구는 이번 조사에서 확인하지 못했다(공백).
//    CacheService 같은 비영속 경고가 없다는 사실만으로 "영속이 보장된다"고
//    단정하지 않는다 — 단지 CacheService의 명시적 비영속 경고가 여기에는
//    없다는 사실만 기록한다.
//
// 정리(cleanup) 비용: 자동 만료가 없으므로, 이 변형을 실제로 오래 운영하면
// 만료된 레코드가 Properties에 계속 쌓여 500KB 한도에 점진적으로 도달한다.
// 이 파일은 정리 배치(예: 시간 기반 트리거로 오래된 키를 주기적으로 삭제)를
// 구현하지 않는다 — 별도 설계·배포 결정 사항이다(실행계획 문서 참조).
//
// 장애 처리 제한: setProperty 실패(quota 초과 등) 시 이 함수는 업무 실행을
// 차단한다(fail-closed) — CacheService 변형과 동일한 정책이지만, 발생
// 원인(일시적 네트워크 문제 vs 영구적 quota 소진)을 구분하지 않는다는
// 한계가 있다. quota 소진은 일시적 오류와 달리 재시도로 해소되지 않으므로,
// 운영 채택 시에는 이 두 원인을 구분해 알림을 분리해야 한다(Open Question).
//
// 이번 보완(nonce 만료 경계): Cache 변형과 **동일한 expiresAt 경계 규약**을
// 쓴다 — expiresAt = recordTime + ttlSeconds, "now >= expiresAt"일 때만
// 만료로 판정한다(이전 버전의 "elapsed < ttl" 식과 수학적으로는 같지만,
// 변수명을 Cache 변형·NonceTtlBoundary_new.gs와 맞춰 두 저장소가 서로
// 다른 경계 규칙을 쓰는 것처럼 보이지 않게 했다 — 향후 정리(cleanup)
// 배치도 이 동일한 expiresAt 규약을 그대로 써야 한다). 값은
// "recordTime:ttlSeconds" 형식으로 저장해 recordTime과 ttlSeconds를
// 모두 보존한다(둘 다 있어야 expiresAt을 재계산할 수 있고, 또한
// 디버깅·정리 배치가 "언제 기록됐는지"를 알 수 있다).

/**
 * @param {string} nonce 합성 테스트 nonce (운영 데이터 아님)
 * @param {number} nowEpochSeconds 호출(=서명 검증 통과) 시각(Unix epoch 초)
 * @param {number} signedTimestampEpochSeconds 이 envelope의 서명 대상 timestamp
 * @param {number} maxSkewSeconds 이 요청에 적용된 서명 스큐 허용치
 * @return {{outcome: string, error: (string|undefined)}}
 *   outcome: "ACCEPTED" | "REJECTED_REPLAY" | "BLOCKED_LOCK_TIMEOUT" | "BLOCKED_STORE_ERROR"
 */
function checkAndRecordNonce_VariantB_PropertiesLock_(nonce, nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds) {
  var lock = LockService.getScriptLock();
  var acquired = false;
  try {
    acquired = lock.tryLock(LOCK_WAIT_TIMEOUT_MS);
    if (!acquired) {
      return { outcome: "BLOCKED_LOCK_TIMEOUT" };
    }

    var props = PropertiesService.getScriptProperties();
    var key = "nonce_" + nonce;
    var existingRaw;
    try {
      existingRaw = props.getProperty(key);
    } catch (e) {
      return { outcome: "BLOCKED_STORE_ERROR", error: String(e) };
    }

    if (existingRaw !== null) {
      var parts = existingRaw.split(":");
      var existingRecordTime = Number(parts[0]);
      var existingTtl = Number(parts[1]);
      var existingExpiresAt = existingRecordTime + existingTtl;
      if (nowEpochSeconds < existingExpiresAt) {
        return { outcome: "REJECTED_REPLAY" };
      }
      // now >= existingExpiresAt: Cache가 TTL 경과 시 자동으로 null을
      // 반환하는 것과 동일한 경계에서, 여기서는 "덮어쓰기 허용"으로
      // 같은 효과를 낸다 — 단 레코드 자체는 지워지지 않으므로 별도
      // 정리(cleanup) 작업이 이 동일한 expiresAt 규약으로 삭제해야 한다.
    }

    try {
      var signatureAllowedEnd = computeSignatureAllowedEndTime_(signedTimestampEpochSeconds, maxSkewSeconds);
      var ttlSeconds = computeNonceTtlSeconds_(
        nowEpochSeconds, signedTimestampEpochSeconds, maxSkewSeconds, EXPERIMENT_TTL_MARGIN_SECONDS
      );
      assertNonceOutlivesSignatureWindow_(nowEpochSeconds, ttlSeconds, signatureAllowedEnd);
      props.setProperty(key, nowEpochSeconds + ":" + ttlSeconds);
    } catch (e) {
      // 500KB/9KB 한도 초과, TTL 계산/불변식 오류 등 — 원인 불문 fail-closed.
      return { outcome: "BLOCKED_STORE_ERROR", error: String(e) };
    }

    return { outcome: "ACCEPTED" };
  } finally {
    if (acquired) {
      lock.releaseLock();
    }
  }
}
