// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: ExperimentConfig_new.gs
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// 아래 값은 모두 "실험 설정값"이다. 운영 확정값이 아니며, 이 파일 어디에도
// 운영 Secret·운영 키ID·운영 예약자료를 담지 않는다(합성 데이터 전용).

// signing_v2.py TEST_DEFAULT_MAX_SKEW_SECONDS(120)와 동일하게 맞춘 실험값.
// 운영 max_skew_seconds는 아직 미확정이다(ADR 미확정 사항, 별도 결정 필요).
var EXPERIMENT_MAX_SKEW_SECONDS = 120;

// --- nonce 보존기간(TTL) 유도 ---
// signing_v2.py verify_v2()의 검사식: delta = now - timestamp
//   통과 조건: -maxSkew <= delta <= maxSkew   (즉 timestamp ∈ [now-maxSkew, now+maxSkew])
//
// 공격자가 "미래 timestamp"를 최대한도까지 채워 넣은 서명된 envelope를 포획했다고 하자.
// 최초 처리 시각을 T0이라 하면, 그 요청이 최초에 통과하려면
//   delta0 = T0 - timestamp >= -maxSkew  →  timestamp <= T0 + maxSkew
// 즉 timestamp는 최대 T0+maxSkew까지 미래로 설정되어도 최초 통과가 가능하다(경계 포함).
//
// 이 envelope(동일 timestamp, 동일 서명, 동일 nonce)를 나중 시각 now'에 재전송하면
//   now' - timestamp <= maxSkew  →  now' <= timestamp + maxSkew <= (T0+maxSkew) + maxSkew = T0 + 2*maxSkew
// 따라서 "이 envelope가 서명 검증을 통과할 수 있는 가장 늦은 시각"은 T0 + 2*maxSkew이다.
//
// 결론: nonce 보존기간(TTL)은 nonce가 최초 기록된 시각(T0) 기준으로
//   TTL >= 2 * EXPERIMENT_MAX_SKEW_SECONDS
// 이어야, "서명은 아직 유효한데 nonce 기록은 이미 사라진" 구간이 생기지 않는다.
// 이 경계식은 추정이 아니라 signing_v2.py verify_v2()의 실제 delta 비교 코드
// (lines 294-299, if delta > max_skew: EXPIRED / if delta < -max_skew: FUTURE)에서
// 직접 유도한 것이다.
var EXPERIMENT_NONCE_TTL_SECONDS = 2 * EXPERIMENT_MAX_SKEW_SECONDS; // = 240초(이론적 최소값, 참고용)
// 위 값은 유도식의 "최소값"이며 처리 지연 여유가 0이다. 기존 ADR 재사용값인
// Secondary TTL=300초(nonce_store.py)는 240초보다 60초 여유가 있어 이 불변식을
// 만족하지만, 이는 "최악의 미래 timestamp" 가정 하의 고정값일 뿐 매 요청마다
// 검증된 값은 아니었다.
//
// 이번 보완: NonceTtlBoundary_new.gs의 computeNonceTtlSeconds_()가
// **매 요청의 실제 timestamp 기준으로** TTL을 동적으로 계산하고,
// assertNonceOutlivesSignatureWindow_()가 그 결과를 매 호출마다 검증한다.
// 아래 고정 상수는 이제 "참고용 상한 비교값"으로만 쓰고, VariantA/B의
// 실제 TTL 계산에는 더 이상 쓰지 않는다(ExperimentConfig_new.gs 자체는
// 상수만 선언하고, 계산 로직은 NonceTtlBoundary_new.gs에 둔다 — 중복 유도 방지).
var EXPERIMENT_NONCE_TTL_SECONDS_WITH_MARGIN = 300; // 참고/비교용 — 동적 계산의 "고정값이었다면" 대조군

// 동적 TTL 계산에 더하는 처리 지연 여유분(실험 설정값, 공식 문서에서
// 유도된 값이 아니다 — 순전히 이번 실험이 고른 보수적 버퍼).
var EXPERIMENT_TTL_MARGIN_SECONDS = 30;

// LockService 대기 한도. 공식 문서에 LockService quota/보유시간 상한이
// 게재되어 있지 않아(미조사 공백), 이 값은 순전히 실험 설계자가 고른
// 타임아웃이며 GAS 플랫폼 제약에서 유도된 값이 아니다.
var LOCK_WAIT_TIMEOUT_MS = 5000;

// Variant B(PropertiesService) 전용 — 공식 Quotas 문서(2026-10-03 조회) 확인값.
var PROPERTIES_TOTAL_LIMIT_BYTES = 500 * 1024; // "500 KB / property store"
var PROPERTIES_MAX_VALUE_BYTES = 9 * 1024;     // "9 KB / val"

// --------------------------------------------------------------------------
// 서버 측 실험 예산(요청 상한·종료시각) — ServerBudgetGuard_new.gs가 이 값을
// 쓴다. 실행계획 보고서(Execution_Readiness_Report_v3_new.md) §3에서 계산한
// "실제 계획 요청 수(60건)"보다 여유를 둔 상한이다 — 정상 실행에서는 절대
// 도달하지 않을 것으로 예상하되, 재시도·점검 호출 몇 건 정도의 여유만 둔다
// (여유를 크게 두면 상한 자체가 무의미해진다).
// --------------------------------------------------------------------------
var EXPERIMENT_DEADLINE_SECONDS = 900;   // 15분
var EXPERIMENT_REQUEST_CAP = 80;         // 계획된 60건 + 소폭 여유(재시도 대비)
