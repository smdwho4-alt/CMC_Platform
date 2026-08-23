/**
 * Sprint8 DR-B-01 PoC#2 — GAS CacheService Eviction 격리 Harness
 *
 * 근거: ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md §13/§29,
 *       docs/Sprint8_Security_Architecture_Design.md §23,
 *       docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md §40,
 *       docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Test_Plan.md (P2-01~P2-12)
 *
 * 이 파일은 Pre-Implementation Harness다(ADR-017 §29). Commit8-3b Production
 * 코드가 아니며, 운영 GAS(app/apps_script/sheets_api_v3_final.gs)의 어떤 코드도
 * 재사용하지 않는다. 독립형(Standalone) Apps Script 프로젝트에서 실행하도록
 * 작성되었다 — Spreadsheet 바인딩을 요구하지 않는다.
 *
 * 절대 금지(이 파일 전체에 적용):
 *   - SpreadsheetApp 사용 금지
 *   - UrlFetchApp 사용 금지(외부 네트워크 호출 금지)
 *   - 실제 운영 script ID·URL·HMAC Secret·예약자/수검자 정보 포함 금지
 *   - 실제 nonce 포함 금지 — 모든 key/value는 합성(synthetic) 문자열만 사용
 *   - PropertiesService를 "결과 저장용"으로 사용하지 않음
 *     (Phase A/B 연결은 함수 반환값의 runId를 사용자가 다시 입력하는 방식이 기본이며,
 *     Sprint8 Pre-G1-B-E2 승인에 따라 §4.1의 handoff 메타데이터 저장에 한해 예외로 사용)
 *
 * Scenario Registry (P2-01~P2-12 ↔ 함수 매핑):
 *   P2-01  put 후 즉시 get 기본 동작              -> poc2_putAndGet()
 *   P2-02  동일 key overwrite                      -> poc2_overwrite()
 *   P2-03  remove 후 miss 확인                     -> poc2_remove()
 *   P2-04  TTL 이전 조회(Phase A: put + 기록)      -> poc2_beforeTtl()
 *          (편집기 수동 실행용 무인자 어댑터: poc2_beforeTtlManual(), §4.1)
 *   P2-05  TTL 이후 조회(Phase B: 별도 시점 실행)  -> poc2_afterTtl(runId, startedAtMs)
 *          (편집기 수동 실행용 무인자 어댑터: poc2_afterTtlManual(), §4.1)
 *   P2-06  다수 key 잔존율 측정                    -> poc2_bulkRetention()
 *   P2-07  용량 압박 조기 eviction 관측             -> poc2_pressureEviction()
 *   P2-08  반복 실행별 잔존율 편차                  -> poc2_repeatVariance()
 *   P2-09  LockService 적용/미적용 비교(구조적)     -> poc2_lockComparison()
 *   P2-10  Fail-Closed 근거자료 산출                -> poc2_failClosedEvidence(priorResults)
 *   P2-11  quota/실행시간 제한 중단 처리            -> poc2_quotaStopHandling()
 *                                                     (+ 전 시나리오에 내장된 poc2__timeGuard)
 *   P2-12  테스트 리소스 정리·검증                  -> poc2_cleanup(keys) / poc2_verifyCleanup(keys)
 *          (handoff property 부재 확인 포함)
 *
 * 진입점:
 *   runPoc2Scenario(scenarioId, args)  — 단일 시나리오 수동 실행(Apps Script 편집기에서 함수 선택 후 실행)
 *   runPoc2All()                       — 단일 실행에서 안전하게 완결 가능한 시나리오 일괄 실행 + 항상 P2-12로 마무리
 *
 * 알려진 구조적 한계(정직하게 명시, §19/§30 원문 취지 재인용):
 *   - GAS Script Cache는 전체 key 목록 조회 API를 제공하지 않는다. 이 harness의
 *     정리·검증은 "각 실행이 자신이 생성한 key만 추적"하는 방식으로만 동작한다.
 *     실행이 비정상 중단되면 잔여 key는 TTL 자연만료로만 해소된다(§25).
 *   - Apps Script 단일 실행은 본질적으로 순차 처리다. P2-09는 Lock 有/無의
 *     "코드 경로" 차이만 비교하며, 실제 동시 요청 경합은 재현하지 않는다.
 *   - P2-11은 실제 GAS quota 초과를 인위적으로 유발하지 않는다. 대신 동일한
 *     내부 안전시간 가드(poc2__timeGuard)를 의도적으로 짧은 한도로 호출해
 *     "중단 후 부분결과 보존 + cleanup" 절차 자체가 동작함을 검증한다.
 */

/**
 * §4.1 P2-04/P2-05 TTL 수동 실행 어댑터 — 실행순서(Sprint8 Pre-G1-B-E2 승인)
 *
 * Apps Script 편집기의 "함수 선택" 드롭다운은 인자 없이(0-arg) 함수만 실행할 수 있다.
 * poc2_afterTtl(runId, startedAtMs)는 필수 인자가 있어 이 방식으로 직접 실행할 수 없으므로,
 * Script Properties를 결과 저장소가 아니라 P2-04→P2-05 사이의 일회성 합성 handoff
 * 메타데이터 전달 통로로만 사용하는 무인자 어댑터
 * poc2_beforeTtlManual()/poc2_afterTtlManual()을 추가한다.
 * 정확한 수동 실행순서는 다음과 같다.
 *
 *   1) runPoc2All()            — P2-01/02/03/04(Phase A)/06/07/08/09/10/11/12 일괄 실행
 *   2) poc2_beforeTtlManual()  — P2-04 TTL 수동 사이클 시작, handoff를 Script Properties에 저장
 *   3) 최소 TTL_SECONDS 경과 대기 — 현재 PROPOSED INITIAL VALUE는 300초이며,
 *      Utilities.sleep을 사용하지 않고 실제 시간 경과를 기다린다
 *   4) poc2_afterTtlManual()   — TTL 경과 확인 후 P2-05 최종 판정을 수행하고 handoff를 삭제한다
 *
 * runPoc2All() 내부에서 자동 실행되는 P2-04(Phase A)는 참고용 스모크 테스트일 뿐이며,
 * 최종 P2-04/P2-05 TTL 판정 증적은 반드시 2)~4)의 별도 수동 사이클을 사용한다.
 *
 * 실행 제한: poc2_beforeTtlManual() 실행 후 poc2_afterTtlManual()이 완료되기 전까지는
 * runPoc2All()이나 다른 P2 시나리오를 실행하지 않는다. 잘못되었거나 잔존한 handoff를
 * 복구해야 할 때만 poc2_clearTtlHandoffManual()을 별도로 실행한다.
 */

/* ───────────────────────── 0. 설정값 (전부 잠정값) ───────────────────────── */

/**
 * 모든 수치는 PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY.
 * 계획서(§17/§14/§18) 원칙: 최종값은 이 문서에서 확정하지 않으며 실행 승인 단계에서 결정한다.
 */
function poc2_config() {
  return {
    // 합성 key 접두사. 운영 nonce/예약번호 형식(YYYYMMDD-NNNN)을 흉내 내지 않는다(§11).
    KEY_PREFIX: 'poc2test_',

    // TTL(초). ADR-017 §13 채택값을 PROPOSED INITIAL VALUE로만 사용(§14).
    TTL_SECONDS: 300, // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY

    // P2-06 잔존율 측정용 key 투입 수(§17: 50~200개 구간의 하한 근처).
    BULK_KEY_COUNT: 50, // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY

    // P2-07 용량 압박용 추가 key 최대 투입 수(§17: 상한 근처, 공식 1,000항목 상한 대비 20%).
    PRESSURE_KEY_COUNT_MAX: 200, // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY

    // P2-08 반복 횟수(§17: SQLite PoC 20회 대비 대폭 축소).
    REPEAT_COUNT: 3, // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY

    // LockService 대기시간(ms). 운영 코드(_actionCreate 등)의 10000ms보다
    // 보수적으로 짧게 설정 — harness 실행시간 안전 확보 목적.
    LOCK_WAIT_MS: 3000, // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY

    // 이 harness 전체(runPoc2All 기준) 안전 중단 시간(ms).
    // 공식 실행시간 상한(6분=360000ms, §18)에 대한 여유버퍼로 4분을 잠정 채택.
    // 공식 상한 자체는 EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED(§18)이며
    // 이 값은 그 불확실성에 대비한 PROPOSED INITIAL VALUE일 뿐이다.
    SAFE_EXECUTION_TIME_LIMIT_MS: 240000, // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY

    // cache.removeAll()/getAll() 배치 크기. 공식 상한 미확인(§18과 동일 사유)이므로
    // 보수적으로 작게 나눠 호출한다.
    BATCH_CHUNK_SIZE: 50 // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY
  };
}

/* ───────────────────────── 1. 내부 헬퍼(비공개 규약: poc2__ 접두사) ───────────────────────── */

function poc2__now() {
  return new Date().getTime();
}

function poc2__nowIso() {
  return new Date().toISOString();
}

/** 안전시간 한도 도달 여부. 모든 반복 루프는 이 가드를 통해서만 조기 종료한다(P2-11). */
function poc2__timeGuard(startMs, limitMs) {
  return (poc2__now() - startMs) >= limitMs;
}

/** 오류 메시지에서 URL·긴 토큰(스크립트ID·시크릿 등으로 오인될 수 있는 값)을 제거한다(§26). */
function poc2__sanitizeError(err) {
  var msg = (err && err.message) ? String(err.message) : String(err);
  msg = msg.replace(/https?:\/\/\S+/g, '[URL-REDACTED]');
  msg = msg.replace(/[A-Za-z0-9_-]{25,}/g, '[TOKEN-REDACTED]');
  return msg;
}

/** §23 실패 분류표 그대로 사용. 패턴 매칭 실패 시 UNEXPECTED_API_BEHAVIOR로 분류. */
function poc2__classifyError(err) {
  var msg = (err && err.message) ? String(err.message).toLowerCase() : '';
  if (msg.indexOf('quota') !== -1 || msg.indexOf('exceeded') !== -1 || msg.indexOf('time') !== -1 && msg.indexOf('limit') !== -1) {
    return 'ENVIRONMENT_LIMIT';
  }
  if (msg.indexOf('lock') !== -1) {
    return 'ENVIRONMENT_LIMIT';
  }
  return 'UNEXPECTED_API_BEHAVIOR';
}

/** 표준 결과 object 골격(스펙 §7 필드 그대로). */
function poc2__baseResult(scenario, runId) {
  return {
    scenario: scenario,
    runId: runId,
    startedAt: poc2__nowIso(),
    finishedAt: null,
    status: 'NOT_RUN',
    observations: {},
    counts: {},
    errorType: null,
    errorMessageSafe: null,
    cleanup: { performed: false, remaining: null },
    notes: []
  };
}

function poc2__log(result) {
  // 구조화된 console 로그로만 결과를 제공한다(PropertiesService 미사용, §7 요구사항).
  console.log(JSON.stringify(result));
}

/* ───────────────────────── 2. runId·key 생성 ───────────────────────── */

/** 실행별 고유 runId. 실제 nonce·예약번호가 아닌 합성 식별자만 생성한다. */
function poc2_newRunId() {
  return 'poc2-run-' + Utilities.getUuid();
}

/** 합성 key 생성. 접두사·runId·scenario·index만으로 구성되며 PII를 포함하지 않는다. */
function poc2_key(runId, scenario, index) {
  var idx = (index === undefined || index === null) ? '0' : String(index);
  var cfg = poc2_config();
  return cfg.KEY_PREFIX + runId + '_' + scenario + '_' + idx;
}

/* ───────────────────────── 3. P2-01~P2-03: 기본 동작 ───────────────────────── */

/** P2-01: put 후 즉시 get 기본 동작 확인. */
function poc2_putAndGet(runId) {
  runId = runId || poc2_newRunId();
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-01', runId);
  var createdKeys = [];
  try {
    var key = poc2_key(runId, 'P2-01', 0);
    var value = 'poc2-value-' + runId;
    createdKeys.push(key);

    cache.put(key, value, cfg.TTL_SECONDS);
    var got = cache.get(key);

    result.observations = { valueMatched: (got === value) };
    result.counts = { keysCreated: 1 };
    result.status = (got === value) ? 'PASS' : 'FAIL';
    if (got !== value) {
      result.notes.push('put 직후 get 값 불일치 — 기본 동작 자체가 기대와 다름(§19 P2-01)');
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/** P2-02: 동일 key overwrite 동작 확인. */
function poc2_overwrite(runId) {
  runId = runId || poc2_newRunId();
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-02', runId);
  var createdKeys = [];
  try {
    var key = poc2_key(runId, 'P2-02', 0);
    createdKeys.push(key);

    cache.put(key, 'v1-' + runId, cfg.TTL_SECONDS);
    cache.put(key, 'v2-' + runId, cfg.TTL_SECONDS);
    var got = cache.get(key);
    var expected = 'v2-' + runId;

    result.observations = { finalValue: got, overwriteSucceeded: (got === expected) };
    result.counts = { keysCreated: 1 };
    result.status = (got === expected) ? 'PASS' : 'FAIL';
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/** P2-03: remove 후 miss 확인. */
function poc2_remove(runId) {
  runId = runId || poc2_newRunId();
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-03', runId);
  var createdKeys = [];
  try {
    var key = poc2_key(runId, 'P2-03', 0);
    createdKeys.push(key);

    cache.put(key, 'to-be-removed-' + runId, cfg.TTL_SECONDS);
    cache.remove(key);
    var got = cache.get(key);

    result.observations = { nullAfterRemove: (got === null) };
    result.counts = { keysCreated: 1 };
    result.status = (got === null) ? 'PASS' : 'FAIL';
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    // remove()로 이미 제거된 key라도 방어적으로 cleanup을 한 번 더 호출한다.
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 4. P2-04/P2-05: TTL 전/후 (Phase A/B) ───────────────────────── */

/**
 * P2-04 (Phase A): TTL 이전 조회 기준선. put 직후 즉시 get하여 값 보존을 확인하고,
 * Phase B(poc2_afterTtl)에서 재사용할 runId·key·시작시각·TTL을 반환값으로 넘긴다.
 * PropertiesService를 쓰지 않으므로, 이 반환값(runId, startedAtMs)을 호출자가
 * 별도 시점에 poc2_afterTtl(runId, startedAtMs)로 그대로 다시 넘겨야 한다.
 */
function poc2_beforeTtl(runId) {
  runId = runId || poc2_newRunId();
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-04', runId);
  var createdKeys = [];
  var startedAtMs = poc2__now();
  try {
    var key = poc2_key(runId, 'P2-04', 0);
    var value = 'poc2-ttl-value-' + runId;
    createdKeys.push(key);

    cache.put(key, value, cfg.TTL_SECONDS);
    var got = cache.get(key);

    result.observations = {
      valueMatched: (got === value),
      phaseAHandoff: {
        runId: runId,
        key: key,
        startedAtMs: startedAtMs,
        ttlSeconds: cfg.TTL_SECONDS
      }
    };
    result.counts = { keysCreated: 1 };
    result.status = (got === value) ? 'PASS' : 'FAIL';
    result.notes.push('Phase B는 TTL(' + cfg.TTL_SECONDS + '초) 경과 후 poc2_afterTtl(runId, startedAtMs)를 별도 시점에 수동 실행해야 한다.');
    // 이 시나리오는 Phase B가 완료될 때까지 key를 남겨두어야 하므로 여기서는 cleanup하지 않는다.
    result.cleanup = { performed: false, remaining: null };
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
    result.cleanup = poc2_cleanup(createdKeys);
  } finally {
    result.finishedAt = poc2__nowIso();
    poc2__log(result);
  }
  return result;
}

/**
 * P2-05 (Phase B): TTL 이후 조회. poc2_beforeTtl()이 반환한 runId·startedAtMs를
 * 그대로 넘겨 호출해야 한다. TTL이 실제로 경과하지 않았으면 DEFERRED를 반환하고
 * (가짜로 300초를 sleep하지 않음), 경과했으면 get() 결과를 §16 기준으로 분류한다.
 */
function poc2_afterTtl(runId, startedAtMs) {
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-05', runId || 'unknown');
  var createdKeys = [];
  try {
    if (!runId || !startedAtMs) {
      result.status = 'DEFERRED';
      result.notes.push('poc2_beforeTtl()의 반환값(runId, startedAtMs)이 필요합니다. 단독 호출 불가.');
      return result;
    }

    var key = poc2_key(runId, 'P2-04', 0); // Phase A와 동일한 key 규칙(P2-04 namespace)을 재구성
    createdKeys.push(key);
    var elapsedMs = poc2__now() - startedAtMs;
    var ttlMs = cfg.TTL_SECONDS * 1000;

    if (elapsedMs < ttlMs) {
      result.status = 'DEFERRED';
      result.observations = { elapsedMs: elapsedMs, ttlMs: ttlMs, remainingMs: (ttlMs - elapsedMs) };
      result.notes.push('TTL 미경과 — 재호출 필요(§19 P2-05는 TTL 경과 후 조회만 유효).');
      return result;
    }

    var got = cache.get(key);
    result.observations = { elapsedMs: elapsedMs, ttlMs: ttlMs, nullAfterTtl: (got === null) };
    result.counts = { keysChecked: 1 };
    // §16: TTL 경과 후 miss는 "정상 만료"로 분류한다(eviction 판정 아님).
    result.status = (got === null) ? 'PASS' : 'FAIL';
    result.notes.push('§16 기준: TTL 경과 후 null은 정상 만료로 분류하며 eviction으로 집계하지 않는다.');
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 4.1 P2-04/P2-05 TTL 수동 실행 handoff (Sprint8 Pre-G1-B-E2) ───────────────────────── */

/**
 * TTL Phase A→P2-05 수동 실행 handoff 전용 Script Properties key. 결과 저장용이 아니라
 * 일회성 합성 메타데이터(runId/key/startedAtMs/ttlSeconds/createdAt) 전달 통로로만 사용한다.
 */
var POC2_HANDOFF_PROPERTY_KEY = 'poc2test_ttl_handoff_v1'; // PROPOSED TEST-ONLY VALUE — NOT PRODUCTION POLICY

/**
 * handoff를 저장한다. 기존 handoff가 있으면 절대 덮어쓰지 않고 Fail-Closed로 거부한다.
 * "존재확인~기록" 구간은 Production 코드(_actionCreate 등, ADR-017 §13 설계 원칙)와 동일한
 * LockService.getScriptLock() 패턴(poc2_lockComparison과 동일 형태)으로 감싸 두 번의
 * poc2_beforeTtlManual() 호출이 겹칠 때의 check-then-write 경합을 방지한다. Lock 획득 실패 시에도
 * 저장하지 않는다(무한 재시도 없음, LOCK_WAIT_MS 1회 대기 후 포기).
 */
function poc2__saveHandoff(handoffRecord) {
  var cfg = poc2_config();
  var props = PropertiesService.getScriptProperties();
  var lock = LockService.getScriptLock();
  var lockAcquired = false;
  try {
    lockAcquired = lock.tryLock(cfg.LOCK_WAIT_MS);
    if (!lockAcquired) {
      return { ok: false, errorMessageSafe: 'lock not acquired for handoff save' };
    }
    var existing = props.getProperty(POC2_HANDOFF_PROPERTY_KEY);
    if (existing) {
      return { ok: false, alreadyExists: true, errorMessageSafe: 'handoff already exists, not overwritten' };
    }
    props.setProperty(POC2_HANDOFF_PROPERTY_KEY, JSON.stringify(handoffRecord));
    return { ok: true };
  } catch (e) {
    return { ok: false, errorMessageSafe: poc2__sanitizeError(e) };
  } finally {
    if (lockAcquired) lock.releaseLock();
  }
}

/**
 * handoff를 읽고 검증한다(Fail-Closed: 하나라도 실패하면 ok:false를 반환하고 호출자는
 * Phase B를 진행하지 않는다). ttlSeconds는 이번 실행의 cfg.TTL_SECONDS와의 정확한 일치만
 * 검증하며, GAS 공식 TTL 범위(§18 EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED)는 이
 * harness에서 새로 확정하지 않는다. key는 poc2_key(runId, 'P2-04', 0)으로 항상 정확히
 * 재구성 가능한 구조이므로(poc2_beforeTtl()이 이 형식으로만 생성) 엄격 일치 비교만 사용하고,
 * 느슨한 prefix/포함 검사로 완화하지 않는다.
 */
function poc2__loadHandoff() {
  var cfg = poc2_config();
  var raw = PropertiesService.getScriptProperties().getProperty(POC2_HANDOFF_PROPERTY_KEY);
  if (!raw) {
    return { ok: false, present: false, errorMessageSafe: 'handoff property not found' };
  }

  var parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    return { ok: false, present: true, errorMessageSafe: 'handoff property is not valid JSON' };
  }

  if (typeof parsed.runId !== 'string' || parsed.runId.length === 0) {
    return { ok: false, present: true, errorMessageSafe: 'handoff runId missing or invalid' };
  }
  if (typeof parsed.key !== 'string' || parsed.key.length === 0) {
    return { ok: false, present: true, errorMessageSafe: 'handoff key missing or invalid' };
  }
  if (typeof parsed.startedAtMs !== 'number' || !isFinite(parsed.startedAtMs) || parsed.startedAtMs <= 0 || Math.floor(parsed.startedAtMs) !== parsed.startedAtMs) {
    return { ok: false, present: true, errorMessageSafe: 'handoff startedAtMs missing or invalid' };
  }
  if (typeof parsed.createdAt !== 'number' || !isFinite(parsed.createdAt) || parsed.createdAt <= 0 || Math.floor(parsed.createdAt) !== parsed.createdAt) {
    return { ok: false, present: true, errorMessageSafe: 'handoff createdAt missing or invalid' };
  }
  if (parsed.createdAt < parsed.startedAtMs) {
    return { ok: false, present: true, errorMessageSafe: 'handoff createdAt precedes startedAtMs' };
  }
  if (typeof parsed.ttlSeconds !== 'number' || parsed.ttlSeconds !== cfg.TTL_SECONDS) {
    return { ok: false, present: true, errorMessageSafe: 'handoff ttlSeconds does not match current config' };
  }
  var expectedKey = poc2_key(parsed.runId, 'P2-04', 0);
  if (parsed.key !== expectedKey) {
    return { ok: false, present: true, errorMessageSafe: 'handoff key does not match expected reconstruction' };
  }

  return { ok: true, present: true, handoff: parsed };
}

/** handoff property 1건만 삭제하고 삭제 후 부재를 재확인한다. Cache에는 접근하지 않는다. */
function poc2__deleteHandoff() {
  var cfg = poc2_config();
  var lock = LockService.getScriptLock();
  var lockAcquired = false;
  try {
    lockAcquired = lock.tryLock(cfg.LOCK_WAIT_MS);
    if (!lockAcquired) {
      return { ok: false, errorMessageSafe: 'lock not acquired for handoff delete' };
    }

    var props = PropertiesService.getScriptProperties();
    props.deleteProperty(POC2_HANDOFF_PROPERTY_KEY);
    var stillPresent = !!props.getProperty(POC2_HANDOFF_PROPERTY_KEY);

    if (stillPresent) {
      return { ok: false, errorMessageSafe: 'handoff property still present after delete' };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, errorMessageSafe: poc2__sanitizeError(e) };
  } finally {
    if (lockAcquired) {
      lock.releaseLock();
    }
  }
}

/**
 * P2-04 TTL 수동 사이클 시작(무인자, 편집기 Run 대상). 이미 저장된 handoff가 있으면
 * 유효성과 무관하게 덮어쓰지 않고 DEFERRED를 반환하며, 이 경우 poc2_beforeTtl()을
 * 아예 호출하지 않는다(불필요한 cache key 생성 방지). handoff가 없을 때만
 * poc2_beforeTtl()을 실행하고, 그 실제 성공 판정(status==='PASS')일 때만
 * phaseAHandoff({runId, key, startedAtMs, ttlSeconds})와 createdAt을 저장한다.
 */
function poc2_beforeTtlManual() {
  var result = poc2__baseResult('P2-04-MANUAL', 'pending');
  try {
    var precheck = poc2__loadHandoff();
    if (precheck.present) {
      result.status = 'DEFERRED';
      result.observations = { handoffAlreadyPresent: true };
      result.notes.push('이미 저장된 handoff가 있어 poc2_beforeTtl()을 실행하지 않았습니다. 먼저 poc2_afterTtlManual()로 완료하거나, 필요 시 poc2_clearTtlHandoffManual()로 정리한 뒤 다시 실행하십시오.');
      result.finishedAt = poc2__nowIso();
      poc2__log(result);
      return result;
    }

    var phaseA = poc2_beforeTtl();
    result.runId = phaseA.runId;

    var handoffSaved = false;
    var saveOutcome = null;
    if (phaseA.status === 'PASS' && phaseA.observations && phaseA.observations.phaseAHandoff) {
      var h = phaseA.observations.phaseAHandoff;
      var handoffRecord = {
        runId: h.runId,
        key: h.key,
        startedAtMs: h.startedAtMs,
        ttlSeconds: h.ttlSeconds,
        createdAt: poc2__now()
      };
      saveOutcome = poc2__saveHandoff(handoffRecord);
      handoffSaved = saveOutcome.ok;
    }

    result.observations = {
      phaseAStatus: phaseA.status,
      handoffSaved: handoffSaved,
      saveErrorMessageSafe: (saveOutcome && saveOutcome.errorMessageSafe) || null
    };
    result.counts = phaseA.counts;
    result.status = (phaseA.status === 'PASS' && handoffSaved) ? 'PASS_WITH_CONDITIONS' : 'FAIL';
    if (phaseA.status === 'PASS' && !handoffSaved) {
      result.notes.push('Phase A는 성공했으나 handoff 저장에 실패했습니다(경쟁 또는 lock 실패 가능) — Phase A가 생성한 cache key는 자연 TTL 만료로만 해소됩니다.');
    }
    result.notes.push('poc2_afterTtlManual()을 TTL(' + poc2_config().TTL_SECONDS + '초) 경과 후 별도로 무인자 실행하십시오.');
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    poc2__log(result);
  }
  return result;
}

/**
 * P2-05 TTL 수동 판정(무인자, 편집기 Run 대상). handoff를 읽고 검증한 뒤 TTL 경과
 * 여부를 실제 startedAtMs 기준으로 계산한다. 검증 실패·TTL 미경과 시에는 Phase B를
 * 실행하지 않고 handoff를 보존한다. TTL 경과 시에만 기존 poc2_afterTtl(runId,
 * startedAtMs)를 재사용해 Phase B를 수행하고, 그 결과를 먼저 변수에 완전히 보존한
 * 뒤에만 handoff 삭제를 시도한다. 삭제 실패는 Phase B 결과를 유실·덮어쓰지 않고
 * observations.cleanup에 별도로 기록한다.
 */
function poc2_afterTtlManual() {
  var result = poc2__baseResult('P2-05-MANUAL', 'pending');
  try {
    var loaded = poc2__loadHandoff();

    if (!loaded.present) {
      result.status = 'DEFERRED';
      result.notes.push('저장된 handoff가 없습니다. 먼저 poc2_beforeTtlManual()을 실행하십시오.');
      result.finishedAt = poc2__nowIso();
      poc2__log(result);
      return result;
    }

    if (!loaded.ok) {
      result.status = 'FAIL';
      result.errorType = 'OBSERVATION_LOGIC_FAILURE';
      result.errorMessageSafe = loaded.errorMessageSafe;
      result.notes.push('Fail-Closed: handoff 검증 실패로 Phase B를 실행하지 않았습니다. property는 보존됩니다.');
      result.finishedAt = poc2__nowIso();
      poc2__log(result);
      return result;
    }

    var h = loaded.handoff;
    result.runId = h.runId;
    var elapsedMs = poc2__now() - h.startedAtMs;
    var requiredMs = h.ttlSeconds * 1000;

    if (elapsedMs < requiredMs) {
      result.status = 'DEFERRED';
      result.observations = { elapsedMs: elapsedMs, requiredMs: requiredMs, remainingMs: (requiredMs - elapsedMs) };
      result.notes.push('TTL 미경과 — handoff를 삭제하지 않고 보존합니다. 나중에 다시 실행하십시오.');
      result.finishedAt = poc2__nowIso();
      poc2__log(result);
      return result;
    }

    // TTL 경과 — 기존 poc2_afterTtl(runId, startedAtMs)을 재사용해 실제 Phase B를 수행한다.
    // 이 결과를 먼저 변수에 완전히 보존한 뒤에만 handoff 삭제를 시도한다(유실 방지).
    var innerResult = poc2_afterTtl(h.runId, h.startedAtMs);

    var deleteOutcome;
    try {
      deleteOutcome = poc2__deleteHandoff();
    } catch (delErr) {
      deleteOutcome = { ok: false, errorMessageSafe: poc2__sanitizeError(delErr) };
    }

    result.observations = { innerStatus: innerResult.status, innerObservations: innerResult.observations };
    result.counts = innerResult.counts;
    result.errorType = innerResult.errorType;
    result.errorMessageSafe = innerResult.errorMessageSafe;

    if (!deleteOutcome.ok) {
      result.observations.cleanup = { handoffDeleted: false, errorMessageSafe: deleteOutcome.errorMessageSafe || 'handoff deletion failed' };
      result.status = 'FAIL';
      result.errorType = 'CLEANUP_FAILURE';
      result.notes.push('Phase B 판정(' + innerResult.status + ')은 확보되었으나 handoff 삭제에 실패했습니다 — 수동 정리 필요(poc2_clearTtlHandoffManual()).');
    } else {
      result.observations.cleanup = { handoffDeleted: true };
      result.status = innerResult.status;
      result.notes.push('Phase B 완료 후 handoff를 정상 삭제했습니다.');
    }
    result.cleanup = { performed: deleteOutcome.ok, remaining: deleteOutcome.ok ? 0 : null, handoffDeleted: deleteOutcome.ok };
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    poc2__log(result);
  }
  return result;
}

/**
 * TTL handoff 전용 수동 복구 함수(무인자). handoff property 1건만 삭제하며 다른
 * Script Properties나 Cache key에는 접근하지 않는다. runPoc2All()·자동 실행 경로에는
 * 포함하지 않으며, 잘못되었거나 잔존한 handoff를 복구할 때만 별도로 실행한다.
 */
function poc2_clearTtlHandoffManual() {
  var result = poc2__baseResult('POC2-HANDOFF-CLEAR', 'n/a');
  try {
    var deleteOutcome = poc2__deleteHandoff();
    result.status = deleteOutcome.ok ? 'PASS' : 'FAIL';
    if (!deleteOutcome.ok) {
      result.errorType = 'CLEANUP_FAILURE';
      result.errorMessageSafe = deleteOutcome.errorMessageSafe || 'handoff deletion failed';
    } else {
      result.notes.push('handoff property를 정상 삭제하고 부재를 확인했습니다.');
    }
    result.cleanup = { performed: deleteOutcome.ok, remaining: deleteOutcome.ok ? 0 : null, handoffDeleted: deleteOutcome.ok };
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 5. P2-06/P2-07/P2-08: 규모·압박·반복 ───────────────────────── */

/**
 * P2-06: 다수 key 입력 후 잔존율 측정. 사전 pass/fail 기준 없음(§19: "실측 기록 목적").
 * overrides.timeLimitMs를 짧게 넣으면 P2-11 자기검증(poc2_quotaStopHandling)에서
 * 조기 중단 경로를 강제로 재현하는 데 사용한다.
 */
function poc2_bulkRetention(overrides) {
  var cfg = poc2_config();
  var runId = (overrides && overrides.runId) || poc2_newRunId();
  var keyCount = (overrides && overrides.keyCount) || cfg.BULK_KEY_COUNT;
  var timeLimitMs = (overrides && overrides.timeLimitMs) || cfg.SAFE_EXECUTION_TIME_LIMIT_MS;
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-06', runId);
  var createdKeys = [];
  var start = poc2__now();
  var stopped = false;
  try {
    for (var i = 0; i < keyCount; i++) {
      if (poc2__timeGuard(start, timeLimitMs)) { stopped = true; break; }
      var key = poc2_key(runId, 'P2-06', i);
      cache.put(key, 'bulk-' + i, cfg.TTL_SECONDS);
      createdKeys.push(key);
    }

    var retained = poc2__countRetained(cache, createdKeys, cfg.BATCH_CHUNK_SIZE);

    result.counts = { requested: keyCount, created: createdKeys.length, retained: retained };
    result.observations = {
      retentionRate: createdKeys.length ? (retained / createdKeys.length) : null
    };
    result.status = stopped ? 'STOPPED' : 'PASS_WITH_CONDITIONS';
    result.notes.push('관측목적 시나리오(§19 P2-06: 사전 pass 기준 없음) — 이 상태는 "정상 실행 완료" 여부만 의미하며 잔존율 자체의 pass/fail 판정이 아니다.');
    if (stopped) {
      result.errorType = 'ENVIRONMENT_LIMIT';
      result.notes.push('안전시간 한도(' + timeLimitMs + 'ms) 도달로 조기 중단(P2-11).');
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/**
 * P2-07: 용량 압박 조건에서 초기 투입 key의 조기 eviction 관측.
 * 사전 pass/fail 기준 없음(§19: "실측 기록 목적, 발생 여부 자체가 미지").
 */
function poc2_pressureEviction(overrides) {
  var cfg = poc2_config();
  var runId = (overrides && overrides.runId) || poc2_newRunId();
  var pressureCount = (overrides && overrides.pressureCount) || cfg.PRESSURE_KEY_COUNT_MAX;
  var timeLimitMs = (overrides && overrides.timeLimitMs) || cfg.SAFE_EXECUTION_TIME_LIMIT_MS;
  var markerCount = 5; // PROPOSED INITIAL VALUE — NOT PRODUCTION POLICY (초기 marker key 수, 소규모 고정)
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-07', runId);
  var createdKeys = [];
  var start = poc2__now();
  var stopped = false;
  try {
    var markerKeys = [];
    for (var m = 0; m < markerCount; m++) {
      var mk = poc2_key(runId, 'P2-07-marker', m);
      cache.put(mk, 'marker-' + m, cfg.TTL_SECONDS);
      markerKeys.push(mk);
      createdKeys.push(mk);
    }

    var pressureCreated = 0;
    for (var p = 0; p < pressureCount; p++) {
      if (poc2__timeGuard(start, timeLimitMs)) { stopped = true; break; }
      var pk = poc2_key(runId, 'P2-07-pressure', p);
      cache.put(pk, 'pressure-' + p, cfg.TTL_SECONDS);
      createdKeys.push(pk);
      pressureCreated++;
    }

    // TTL 미경과 시점의 marker miss만 eviction으로 집계한다(§15/§16).
    var markerRetained = poc2__countRetained(cache, markerKeys, cfg.BATCH_CHUNK_SIZE);
    var earlyEvictionCount = markerKeys.length - markerRetained;

    result.counts = {
      markerKeys: markerKeys.length,
      pressureKeysRequested: pressureCount,
      pressureKeysCreated: pressureCreated,
      markerRetained: markerRetained,
      earlyEvictionCandidates: earlyEvictionCount
    };
    result.observations = {
      note: 'earlyEvictionCandidates는 TTL 미경과 시점의 marker miss 수(§15 정의). 0이면 이 실행 규모에서 조기 eviction이 관측되지 않았음을 의미할 뿐, 미발생을 일반화하지 않는다(§19).'
    };
    result.status = stopped ? 'STOPPED' : 'PASS_WITH_CONDITIONS';
    result.notes.push('관측목적 시나리오(§19 P2-07: 사전 pass 기준 없음).');
    if (stopped) {
      result.errorType = 'ENVIRONMENT_LIMIT';
      result.notes.push('안전시간 한도(' + timeLimitMs + 'ms) 도달로 조기 중단(P2-11).');
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/** P2-08: P2-06 패턴을 REPEAT_COUNT회 반복해 잔존율 편차를 수집. */
function poc2_repeatVariance(overrides) {
  var cfg = poc2_config();
  var runId = (overrides && overrides.runId) || poc2_newRunId();
  var repeatCount = (overrides && overrides.repeatCount) || cfg.REPEAT_COUNT;
  var keyCountPerRun = (overrides && overrides.keyCountPerRun) || Math.min(cfg.BULK_KEY_COUNT, 20);
  var timeLimitMs = (overrides && overrides.timeLimitMs) || cfg.SAFE_EXECUTION_TIME_LIMIT_MS;
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-08', runId);
  var createdKeys = [];
  var start = poc2__now();
  var stopped = false;
  var rates = [];
  try {
    for (var r = 0; r < repeatCount; r++) {
      if (poc2__timeGuard(start, timeLimitMs)) { stopped = true; break; }
      var iterKeys = [];
      for (var i = 0; i < keyCountPerRun; i++) {
        if (poc2__timeGuard(start, timeLimitMs)) { stopped = true; break; }
        var key = poc2_key(runId, 'P2-08-r' + r, i);
        cache.put(key, 'v-' + r + '-' + i, cfg.TTL_SECONDS);
        iterKeys.push(key);
        createdKeys.push(key);
      }
      if (iterKeys.length > 0) {
        var retained = poc2__countRetained(cache, iterKeys, cfg.BATCH_CHUNK_SIZE);
        rates.push(retained / iterKeys.length);
      }
      if (stopped) break;
    }

    var min = rates.length ? Math.min.apply(null, rates) : null;
    var max = rates.length ? Math.max.apply(null, rates) : null;
    var avg = rates.length ? (rates.reduce(function (a, b) { return a + b; }, 0) / rates.length) : null;

    result.counts = { iterationsRequested: repeatCount, iterationsCompleted: rates.length, keysCreated: createdKeys.length };
    result.observations = { retentionRates: rates, min: min, max: max, avg: avg };
    result.status = stopped ? 'STOPPED' : 'PASS_WITH_CONDITIONS';
    result.notes.push('관측목적 시나리오(§19 P2-08: 사전 pass 기준 없음, 편차 크기 자체가 관측 대상).');
    if (stopped) {
      result.errorType = 'ENVIRONMENT_LIMIT';
      result.notes.push('안전시간 한도(' + timeLimitMs + 'ms) 도달로 조기 중단(P2-11).');
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 6. P2-09: LockService 비교 ───────────────────────── */

/**
 * P2-09: LockService 적용/미적용의 "코드 경로" 비교.
 * 주의(구조적 한계): Apps Script 단일 실행은 순차 처리이므로 실제 동시 경합은
 * 재현하지 않는다. Lock 有/無 각각 동일 key에 순차 put 2회 후 최종값만 비교한다.
 */
function poc2_lockComparison(runId) {
  runId = runId || poc2_newRunId();
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-09', runId);
  var createdKeys = [];
  try {
    var keyLocked = poc2_key(runId, 'P2-09-locked', 0);
    var keyUnlocked = poc2_key(runId, 'P2-09-unlocked', 0);
    createdKeys.push(keyLocked, keyUnlocked);

    var lock = LockService.getScriptLock();
    var lockAcquired = false;
    try {
      lockAcquired = lock.tryLock(cfg.LOCK_WAIT_MS);
      if (lockAcquired) {
        cache.put(keyLocked, 'v1', cfg.TTL_SECONDS);
        cache.put(keyLocked, 'v2', cfg.TTL_SECONDS);
      }
    } finally {
      if (lockAcquired) lock.releaseLock();
    }
    var lockedFinal = cache.get(keyLocked);

    cache.put(keyUnlocked, 'v1', cfg.TTL_SECONDS);
    cache.put(keyUnlocked, 'v2', cfg.TTL_SECONDS);
    var unlockedFinal = cache.get(keyUnlocked);

    result.observations = {
      lockAcquired: lockAcquired,
      lockedFinalValue: lockedFinal,
      unlockedFinalValue: unlockedFinal
    };
    result.counts = { keysCreated: createdKeys.length };
    result.status = (lockAcquired && lockedFinal === 'v2' && unlockedFinal === 'v2') ? 'PASS_WITH_CONDITIONS' : 'FAIL';
    result.notes.push('구조적 한계: 단일 실행 내 순차 비교이며 실제 동시 접근 경합은 검증하지 않는다(§13 원문 취지, 이 harness로는 진짜 동시성 재현 불가).');
    if (!lockAcquired) {
      result.notes.push('Lock 획득 실패(LOCK_WAIT_MS=' + cfg.LOCK_WAIT_MS + 'ms 초과) — 단일 실행 환경에서는 이례적이며 재실행 권장.');
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    result.cleanup = poc2_cleanup(createdKeys);
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 7. P2-10: Fail-Closed 근거자료 ───────────────────────── */

/**
 * P2-10: P2-07/P2-08 결과를 입력으로 받아 miss 발생률·조건을 정리한다(§19: 자료 산출용,
 * ADR-017 §13 Fail-Closed 설계의 근거자료일 뿐 정책 자체를 확정하지 않음).
 * priorResults가 없으면 DEFERRED — 이 시나리오는 단독으로 완결되지 않는다.
 */
function poc2_failClosedEvidence(priorResults, runId) {
  runId = runId || (priorResults && priorResults.length && priorResults[0].runId) || poc2_newRunId();
  var result = poc2__baseResult('P2-10', runId);
  try {
    if (!priorResults || !priorResults.length) {
      result.status = 'DEFERRED';
      result.notes.push('P2-07/P2-08 결과 object 배열이 필요합니다(예: [poc2_pressureEviction(), poc2_repeatVariance()] 결과). 단독 호출 불가.');
      result.finishedAt = poc2__nowIso();
      poc2__log(result);
      return result;
    }

    var evidence = [];
    priorResults.forEach(function (r) {
      if (!r) return;
      evidence.push({
        scenario: r.scenario,
        status: r.status,
        counts: r.counts,
        observations: r.observations
      });
    });

    result.observations = { evidenceCount: evidence.length, evidence: evidence };
    result.counts = { inputsConsidered: priorResults.length, evidenceCollected: evidence.length };
    result.status = evidence.length ? 'PASS_WITH_CONDITIONS' : 'DEFERRED';
    result.notes.push('이 결과는 정책(Fail-Closed 세부 규칙) 확정이 아니라 근거자료 산출일 뿐이다(§19 P2-10, ADR-017 §13).');
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = result.finishedAt || poc2__nowIso();
    result.cleanup = { performed: false, remaining: null }; // 이 시나리오는 신규 cache 리소스를 생성하지 않음
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 8. P2-11: quota/실행시간 중단 처리 ───────────────────────── */

/**
 * P2-11: quota·실행시간 제한 발생 시 중단 절차 확인.
 * 실제 GAS quota 초과를 인위적으로 유발하지 않는다(신뢰성 있게 재현 불가). 대신 동일한
 * poc2__timeGuard를 의도적으로 매우 짧은 한도(timeLimitMs=1)로 poc2_bulkRetention에
 * 넘겨, "조기 중단 + 부분결과 보존 + cleanup 정상 동작"을 결정론적으로 검증한다.
 * 아울러 CacheService/LockService 호출 자체의 예외는 각 시나리오 함수 내부의
 * try/catch에서 이미 ENVIRONMENT_LIMIT/UNEXPECTED_API_BEHAVIOR로 분류된다.
 */
function poc2_quotaStopHandling(runId) {
  runId = runId || poc2_newRunId();
  var cfg = poc2_config();
  var result = poc2__baseResult('P2-11', runId);
  try {
    var forced = poc2_bulkRetention({ runId: runId, keyCount: cfg.BULK_KEY_COUNT, timeLimitMs: 1 });

    var stoppedAsExpected = (forced.status === 'STOPPED') && (forced.counts.created < forced.counts.requested);
    result.observations = {
      forcedScenario: 'P2-06(의도적으로 timeLimitMs=1로 강제 중단)',
      forcedResultStatus: forced.status,
      forcedCounts: forced.counts,
      stoppedAsExpected: stoppedAsExpected
    };
    result.counts = { requested: forced.counts.requested, created: forced.counts.created };
    result.status = stoppedAsExpected ? 'PASS' : 'FAIL';
    result.cleanup = forced.cleanup; // 강제 중단 시나리오가 스스로 cleanup까지 수행함
    if (!stoppedAsExpected) {
      result.notes.push('강제 중단 조건에서도 조기 정지가 관측되지 않음 — 안전시간 가드 로직 재검토 필요.');
    } else {
      result.notes.push('안전시간 가드에 의한 조기 중단, 부분결과 보존, cleanup이 모두 정상 동작함을 확인.');
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 9. P2-12: 리소스 정리·검증 ───────────────────────── */

/** 내부용: keys 중 실제로 남아있는(get 성공) 개수를 배치로 나눠 센다. */
function poc2__countRetained(cache, keys, chunkSize) {
  var retained = 0;
  for (var i = 0; i < keys.length; i += chunkSize) {
    var chunk = keys.slice(i, i + chunkSize);
    var got = cache.getAll(chunk);
    retained += Object.keys(got).length;
  }
  return retained;
}

/**
 * P2-12(정리): 이 실행에서 생성된 것으로 추적된 key만 제거한다.
 * GAS Script Cache는 전체 key 목록 조회 API가 없으므로, 호출자가 넘긴 keys 배열이
 * 유일한 정리 대상 목록이다(§25 한계 재확인).
 */
function poc2_cleanup(keys) {
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var cleanup = { performed: false, remaining: null, requested: (keys ? keys.length : 0) };
  try {
    if (!keys || !keys.length) {
      cleanup.performed = true;
      cleanup.remaining = 0;
      return cleanup;
    }
    for (var i = 0; i < keys.length; i += cfg.BATCH_CHUNK_SIZE) {
      var chunk = keys.slice(i, i + cfg.BATCH_CHUNK_SIZE);
      cache.removeAll(chunk);
    }
    cleanup.performed = true;
  } catch (e) {
    cleanup.performed = false;
    cleanup.errorType = 'CLEANUP_FAILURE';
    cleanup.errorMessageSafe = poc2__sanitizeError(e);
  }
  return cleanup;
}

/** P2-12(검증): 정리 후 지정된 keys 중 실제로 남아있는 개수를 확인한다(스냅샷, §25). */
function poc2_verifyCleanup(keys) {
  var cfg = poc2_config();
  var cache = CacheService.getScriptCache();
  var result = poc2__baseResult('P2-12', 'verify');
  try {
    var checked = (keys && keys.length) ? keys.length : 0;
    var remaining = checked > 0
      ? poc2__countRetained(cache, keys, cfg.BATCH_CHUNK_SIZE)
      : 0;

    var handoffPropertyPresent =
      !!PropertiesService.getScriptProperties()
        .getProperty(POC2_HANDOFF_PROPERTY_KEY);

    result.counts = {
      checked: checked,
      remaining: remaining
    };
    result.observations = {
      handoffPropertyPresent: handoffPropertyPresent
    };
    result.status =
      (remaining === 0 && !handoffPropertyPresent) ? 'PASS' : 'FAIL';

    if (remaining !== 0) {
      result.errorType = 'CLEANUP_FAILURE';
      result.notes.push(
        '정리 후에도 ' + remaining + '개 key가 잔존 — cleanup 실패 가능성.'
      );
    }

    if (handoffPropertyPresent) {
      result.errorType = result.errorType || 'CLEANUP_FAILURE';
      result.notes.push(
        'TTL handoff property가 남아 있음 — 수동 TTL 사이클 완료 또는 전용 정리 필요.'
      );
    }
  } catch (e) {
    result.status = 'FAIL';
    result.errorType = poc2__classifyError(e);
    result.errorMessageSafe = poc2__sanitizeError(e);
  } finally {
    result.finishedAt = poc2__nowIso();
    poc2__log(result);
  }
  return result;
}

/* ───────────────────────── 10. Scenario Registry + 진입점 ───────────────────────── */

/**
 * P2-01~P2-12 전체를 명시적으로 등록한다. phase 필드는 단일 실행 완결 가능 여부를 나타낸다.
 *  - 'single'   : runPoc2All()에서 자동 실행 가능
 *  - 'phase-a'  : Phase A만 자동 실행(P2-04) — Phase B는 별도 수동 호출 필요
 *  - 'manual'   : 항상 수동 인자 필요(P2-05, P2-10)
 *  - 'derived'  : 다른 시나리오 실행 결과에 의존해 자체 실행되는 자기검증(P2-11)
 *  - 'utility'  : 정리·검증 유틸리티(P2-12)
 */
var POC2_SCENARIO_REGISTRY = {
  'P2-01': { fn: poc2_putAndGet, phase: 'single', purpose: 'put 후 즉시 get 기본 동작 확인' },
  'P2-02': { fn: poc2_overwrite, phase: 'single', purpose: '동일 key overwrite 동작 확인' },
  'P2-03': { fn: poc2_remove, phase: 'single', purpose: 'remove 후 miss 확인' },
  'P2-04': { fn: poc2_beforeTtl, phase: 'phase-a', purpose: 'TTL 이전 조회 기준선(Phase A)' },
  'P2-05': { fn: poc2_afterTtl, phase: 'manual', purpose: 'TTL 이후 조회(Phase B, runId+startedAtMs 필요)' },
  'P2-06': { fn: poc2_bulkRetention, phase: 'single', purpose: '다수 key 잔존율 측정' },
  'P2-07': { fn: poc2_pressureEviction, phase: 'single', purpose: '용량 압박 조기 eviction 관측' },
  'P2-08': { fn: poc2_repeatVariance, phase: 'single', purpose: '반복 실행별 잔존율 편차' },
  'P2-09': { fn: poc2_lockComparison, phase: 'single', purpose: 'LockService 적용/미적용 구조 비교' },
  'P2-10': { fn: poc2_failClosedEvidence, phase: 'manual', purpose: 'Fail-Closed 근거자료 산출(priorResults 필요)' },
  'P2-11': { fn: poc2_quotaStopHandling, phase: 'derived', purpose: '중단조건 자기검증(P2-06 강제 중단 기반)' },
  'P2-12': { fn: poc2_verifyCleanup, phase: 'utility', purpose: '정리 검증(keys 필요, cleanup 자체는 poc2_cleanup)' }
};

/** 단일 시나리오 수동 실행. Apps Script 편집기에서 scenarioId를 바꿔가며 직접 호출하는 용도. */
function runPoc2Scenario(scenarioId, args) {
  var entry = POC2_SCENARIO_REGISTRY[scenarioId];
  if (!entry) {
    var unknown = poc2__baseResult(scenarioId || 'UNKNOWN', 'n/a');
    unknown.status = 'FAIL';
    unknown.errorType = 'OBSERVATION_LOGIC_FAILURE';
    unknown.errorMessageSafe = 'Unknown scenario id: ' + scenarioId;
    unknown.finishedAt = poc2__nowIso();
    poc2__log(unknown);
    return unknown;
  }
  return entry.fn.apply(null, args || []);
}

/**
 * 단일 실행에서 안전하게 완결 가능한 시나리오를 순서대로 실행하고, 항상 P2-12(정리+검증)로
 * 마무리한다. P2-05(Phase B)와 P2-10(선행 결과 필요)은 이 함수 하나로 완결되지 않으므로
 * NOT_RUN으로 표시하고 별도 수동 호출 방법을 notes에 남긴다.
 */
function runPoc2All() {
  var cfg = poc2_config();
  var runId = poc2_newRunId();
  var start = poc2__now();
  var allKeys = [];
  var scenarioResults = {};

  function record(scenarioId, resultFn) {
    if (poc2__timeGuard(start, cfg.SAFE_EXECUTION_TIME_LIMIT_MS)) {
      var stoppedResult = poc2__baseResult(scenarioId, runId);
      stoppedResult.status = 'STOPPED';
      stoppedResult.errorType = 'ENVIRONMENT_LIMIT';
      stoppedResult.notes.push('runPoc2All 전체 안전시간 한도 도달로 이후 시나리오를 실행하지 않음(P2-11).');
      stoppedResult.finishedAt = poc2__nowIso();
      scenarioResults[scenarioId] = stoppedResult;
      return false;
    }
    var r = resultFn();
    scenarioResults[scenarioId] = r;
    if (r.observations && r.observations.phaseAHandoff) {
      // P2-04 key는 Phase B를 위해 cleanup되지 않았으므로 이 실행의 최종 정리 대상에 포함한다.
      allKeys.push(r.observations.phaseAHandoff.key);
    }
    return true;
  }

  record('P2-01', function () { return poc2_putAndGet(runId); });
  record('P2-02', function () { return poc2_overwrite(runId); });
  record('P2-03', function () { return poc2_remove(runId); });
  record('P2-04', function () { return poc2_beforeTtl(runId); });
  record('P2-06', function () { return poc2_bulkRetention({ runId: runId }); });
  record('P2-07', function () { return poc2_pressureEviction({ runId: runId }); });
  record('P2-08', function () { return poc2_repeatVariance({ runId: runId }); });
  record('P2-09', function () { return poc2_lockComparison(runId); });
  record('P2-11', function () { return poc2_quotaStopHandling(poc2_newRunId()); }); // 자체 격리된 runId로 강제 중단 자기검증

  var p205 = poc2__baseResult('P2-05', runId);
  p205.status = 'NOT_RUN';
  p205.notes.push('Phase B — TTL(' + cfg.TTL_SECONDS + '초) 경과 후 poc2_afterTtl(\'' + runId + '\', <P2-04 결과의 startedAtMs>)를 별도로 수동 실행하십시오.');
  p205.finishedAt = poc2__nowIso();
  scenarioResults['P2-05'] = p205;

  var priorForP210 = [scenarioResults['P2-07'], scenarioResults['P2-08']].filter(function (r) { return !!r; });
  scenarioResults['P2-10'] = poc2_failClosedEvidence(priorForP210, runId);

  // P2-12: 이번 실행에서 추적된 모든 key(주로 P2-04 handoff key)를 최종 정리하고 검증한다.
  var cleanupResult = poc2_cleanup(allKeys);
  var verifyResult = poc2_verifyCleanup(allKeys);
  scenarioResults['P2-12'] = verifyResult;
  scenarioResults['P2-12'].cleanup = cleanupResult;

  var summary = {
    runId: runId,
    startedAt: new Date(start).toISOString(),
    finishedAt: poc2__nowIso(),
    elapsedMs: poc2__now() - start,
    scenarios: scenarioResults,
    notes: [
      'P2-05는 이 일괄 실행에 포함되지 않음(별도 수동 Phase B 필요).',
      'P2-10은 이번 실행에서 수집된 P2-07/P2-08 결과만 근거자료로 사용함.'
    ]
  };
  console.log(JSON.stringify(summary));
  return summary;
}
