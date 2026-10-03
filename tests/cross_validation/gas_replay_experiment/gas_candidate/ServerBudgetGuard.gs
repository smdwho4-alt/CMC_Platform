// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: ServerBudgetGuard_new.gs — 서버 측 요청 상한·종료시각 강제
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// 설계 원칙(요청사항 1 반영):
//  - 15분 종료시각과 요청 상한을 **드라이버가 아니라 GAS 서버 자신**이
//    강제한다(드라이버가 멈춰도, 다른 누군가 같은 URL로 요청을 보내도
//    서버 쪽에서 막는다).
//  - 집계(카운트 증가·상한 비교)는 Script Lock으로 감싸 **원자적**으로
//    처리한다 — 동시 요청이 카운터를 동시에 읽어 상한을 넘겨 통과시키는
//    경쟁을 막는다.
//  - 이 가드는 **서명 검증을 통과한 요청에 대해서만** 호출된다
//    (Main_doPost_stub_new.gs의 호출 순서 참조) — 즉 여기서 세는 숫자는
//    "인증된 요청 수"다.
//  - 카운터·시작시각 저장소는 PropertiesService를 쓴다(CacheService가
//    아니다) — 이 가드 자체가 안전장치이므로, 그 안전장치 상태가
//    CacheService의 비영속성 때문에 조용히 초기화되어 상한이 무의미해지는
//    일이 없도록 하기 위함이다(CacheService를 쓰면 유실 시 카운터가 0으로
//    리셋되어 상한이 사실상 없어지는 것과 같아진다 — 안전장치에는
//    맞지 않는 선택).
//
// 명시해야 할 한계(요청사항 1의 마지막 항목):
//  이 가드는 **서명 검증을 통과한 "인증된" 요청의 수만 제한한다.**
//  "Who has access: Anyone"으로 배포된 Web App은 서명이 전혀 없는
//  임의의 HTTP POST도 받아들인다 — 그런 요청은 doPost()가 호출되는
//  시점에 이미 Apps Script 자체의 실행 quota를 1건 소비한 뒤다(Google
//  인프라가 그 실행을 받아들인 순간 발생하는 소비이며, 우리 코드가
//  실행되기도 전이다). 즉 이 가드는 "우리가 계획한 인증된 테스트
//  트래픽"의 총량만 통제할 뿐, **공개 endpoint 자체에 도달하는 외부
//  요청(서명 없는 노이즈 포함)이 GAS 실행 quota를 소모하는 것까지는
//  막을 수 없다.** 이것은 이 가드의 버그가 아니라 "Anyone" 접근 설정의
//  구조적 한계이며, 실행계획 보고서에 명시한다.

/**
 * @param {number} nowEpochSeconds
 * @return {{outcome: string, requestCount: number, elapsedSeconds: number}}
 *   outcome: "WITHIN_BUDGET" | "BUDGET_EXCEEDED" | "EXPERIMENT_EXPIRED" | "BLOCKED_STORE_ERROR"
 */
function checkAndConsumeRequestBudget_(nowEpochSeconds) {
  var lock = LockService.getScriptLock();
  var acquired = false;
  try {
    acquired = lock.tryLock(LOCK_WAIT_TIMEOUT_MS);
    if (!acquired) {
      // 예산 집계 자체가 락을 못 잡으면, 안전 쪽으로(요청 자체를) 차단한다.
      return { outcome: "BLOCKED_STORE_ERROR", requestCount: -1, elapsedSeconds: -1 };
    }

    var props = PropertiesService.getScriptProperties();
    var startRaw = props.getProperty("experiment_start_time");
    var startTime;
    if (startRaw === null) {
      // 이 서버가 받은 "인증된" 첫 요청 — 실험 시작시각을 이 시점으로 고정한다.
      startTime = nowEpochSeconds;
      props.setProperty("experiment_start_time", String(startTime));
    } else {
      startTime = Number(startRaw);
    }

    var elapsed = nowEpochSeconds - startTime;
    if (elapsed > EXPERIMENT_DEADLINE_SECONDS) {
      return { outcome: "EXPERIMENT_EXPIRED", requestCount: -1, elapsedSeconds: elapsed };
    }

    var countRaw = props.getProperty("experiment_request_count");
    var count = countRaw === null ? 0 : Number(countRaw);

    if (count + 1 > EXPERIMENT_REQUEST_CAP) {
      return { outcome: "BUDGET_EXCEEDED", requestCount: count, elapsedSeconds: elapsed };
    }

    count = count + 1;
    props.setProperty("experiment_request_count", String(count));
    return { outcome: "WITHIN_BUDGET", requestCount: count, elapsedSeconds: elapsed };
  } catch (e) {
    return { outcome: "BLOCKED_STORE_ERROR", requestCount: -1, elapsedSeconds: -1 };
  } finally {
    if (acquired) {
      lock.releaseLock();
    }
  }
}

/**
 * 편집기에서만 실행하는 수동 초기화(공개 라우트에 연결하지 않는다 —
 * AdminOnly_ManualCacheRemoval_new.gs와 동일한 원칙). 실험을 완전히
 * 새로 시작할 때(예: 전날 실험 종료 후 다음 날 재시작) 수동으로 1회
 * 실행하는 용도다.
 */
function adminResetExperimentBudget_() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty("experiment_start_time");
  props.deleteProperty("experiment_request_count");
}
