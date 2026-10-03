// *** 테스트 전용 합성 값 — 운영 재사용 금지 ***
// 이 파일에는 이번 격리 실험을 위해 생성한 합성(synthetic) 테스트
// 키/비밀값이 포함되어 있다. 실제 운영 계정·실제 비밀키와 무관하며,
// 이 저장소에 공개되어 있다는 전제로 다뤄야 한다 — 운영 환경에
// 그대로 재사용하지 않는다.

// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: TestKeyRegistry_new.gs — 서버 측 합성 테스트 키 레지스트리
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// 이전 설계(request.secret을 요청 본문에서 그대로 받음)는 "클라이언트가
// 자기 비밀키를 서버에 보내준다"는 것과 같아 서명 검증이 사실상
// 무의미했다(공격자가 자기 secret과 그에 맞는 서명을 같이 보내면
// 항상 통과). 이번 수정으로 **서버가 key_id → secret 매핑을 직접
// 들고 있고, 요청 본문의 secret은 아예 받지 않는다.**
//
// 이 파일의 값은 합성 테스트 전용이며, 로컬 드라이버
// (concurrent_http_driver_new.py)가 쓰는 값과 반드시 일치해야 한다 —
// 어긋나면 모든 서명이 SIGNATURE_MISMATCH로 거부된다(정상 동작,
// 보안 결함 아님). 운영 키·예약자료는 어디에도 없다.

var TEST_KEY_REGISTRY_ = {
  // key_id: secret — 합성 전용. 실제 실행 전 로컬 드라이버의 값과
  // 대조해서 맞춰야 한다(이 파일만 고친다고 끝나는 게 아니다).
  "real-gas-exp-key-1dd05338": "95f2e928939b6141904a39a07e44222b3dacd0d9f64eb392f9fdea2e4f12d4f9",
};

/**
 * key_id로 등록된 secret을 찾는다. 다른 key로 폴백하지 않는다 —
 * 정확히 요청된 key_id 하나만 조회하고, 없으면 null을 반환한다
 * (signing_v2.py KeyRegistry.resolve()와 동일한 "폴백 없음" 원칙).
 *
 * @param {string} keyId
 * @return {string|null}
 */
function resolveTestKey_(keyId) {
  if (typeof keyId !== "string") return null;
  if (!Object.prototype.hasOwnProperty.call(TEST_KEY_REGISTRY_, keyId)) {
    return null;
  }
  return TEST_KEY_REGISTRY_[keyId];
}
