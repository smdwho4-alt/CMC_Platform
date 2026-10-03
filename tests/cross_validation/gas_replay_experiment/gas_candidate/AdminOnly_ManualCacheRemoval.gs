// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: AdminOnly_ManualCacheRemoval_new.gs — 캐시 제거 시험용 관리 함수
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// *** 경고: 이 파일의 함수는 어떤 라우트 테이블(ROUTES_ALLOWLIST_)에도
// 올리지 않는다. doPost(e)/doGet(e) 어디에서도 호출하지 않는다. 이 함수는
// Apps Script 편집기에서 소유자가 직접 선택해 "실행" 버튼으로만 실행하는
// 것을 전제로 작성했다 — 공개 Web App을 통해서는 어떤 경로로도 도달할
// 수 없어야 한다(요청사항 4-1: "공개 remove endpoint는 만들지 않는다"). ***
//
// 목적: 이전 턴(로컬 전용) 시나리오5/6 — "CacheService 항목을 시험
// 목적으로 명시적으로 제거한 뒤 재전송했을 때 실제 GAS에서도 동일한
// 결과(KNOWN_LIMITATION)가 나오는가" — 를 실제 GAS에서 확인하고 싶을
// 때만 쓴다.
//
// 수행 여부는 이번 턴에 결정하지 않는다 — 요청사항 4-3: "수행 여부는
// 실제 동시성 시험 결과 후 결정한다." 즉 시나리오2(동시 요청) 실측이
// 끝나고 문제가 없음을 확인한 뒤에야, 이 함수를 실제로 실행할지 별도로
// 판단한다. 이 파일은 "준비"일 뿐 "실행 승인"이 아니다.
//
// 이 함수를 실행하기 **전까지**, "실제 GAS CacheService가 TTL 만료 전에
// 조기 유실될 수 있다"는 것은 공식 문서상의 서술과 로컬 시뮬레이션
// 결과로만 뒷받침되며, **실제 GAS 환경에서 유실 거동 자체를 직접 관찰한
// 적은 없다** — 이 상태를 "미검증"으로 명시적으로 남긴다(요청사항 4-4).
// 이 함수의 실행은 "유실이 실제로 일어나는지"를 재현하는 것이 아니라,
// "유실이 일어났다고 가정했을 때 이후 재전송이 어떻게 처리되는가"를
// 명시적 제거로 모사하는 것이다(이전 턴과 동일한 구분 — 실제 조기 유실
// 재현이 아니라 명시적 remove를 통한 유실 모사).

/**
 * 합성 실험 nonce **하나만** 제거한다. 패턴 매치나 전체 플러시를 하지
 * 않는다 — 실수로 운영 관련 캐시 항목을 건드릴 가능성을 원천 차단하기
 * 위해, 호출부가 정확한 nonce 문자열을 알고 있어야만 동작한다.
 *
 * @param {string} nonce 제거할 합성 nonce(반드시 "syn-" 또는
 *   "driver-nonce-"로 시작해야 한다 — 이 접두사 검사가 안전장치다).
 * @param {string} variant "A"만 지원한다(Variant B는 PropertiesService라
 *   유실 시나리오 자체가 성립하지 않으므로 — Main_doPost_stub_new.gs 설계상
 *   이미 캐시를 쓰지 않는다).
 */
function adminRemoveSyntheticNonce_(nonce, variant) {
  if (typeof nonce !== "string" || (nonce.indexOf("syn-") !== 0 && nonce.indexOf("driver-nonce-") !== 0)) {
    throw new Error(
      "안전장치: 'syn-' 또는 'driver-nonce-'로 시작하는 합성 nonce만 제거할 수 있습니다. " +
      "받은 값: " + nonce
    );
  }
  if (variant !== "A") {
    throw new Error("이 함수는 Variant A(CacheService)에만 쓴다. 받은 variant: " + variant);
  }
  var cache = CacheService.getScriptCache();
  cache.remove(nonce);
  Logger.log("[ADMIN_ONLY] 합성 nonce 제거 완료: " + nonce + " (variant=" + variant + ")");
}
