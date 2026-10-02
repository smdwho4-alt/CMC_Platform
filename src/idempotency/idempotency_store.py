# -*- coding: utf-8 -*-
"""
CSHSP Idempotency Store — Sprint8 Commit8-3b (격리 개발, 로컬 전용) v2

ADR-017 §14("Idempotency 상태모델과 TTL")·§16(재시도 정책)·§23(불확실 성공
상태 처리)이 정의한 5상태(`IN_PROGRESS`/`SUCCEEDED`/`FAILED_RETRYABLE`/
`FAILED_FINAL`/`UNKNOWN`)·TTL(60/900/300/900초/48시간) Idempotency 저장로직의
최소 구현이다.

이 모듈은 **운영 Google Sheets·GAS에 연결하지 않으며, 예약 생성·변경 API를
호출하지 않는다** — 순수 저장소 계층(src/auth/auth_store.py와 동일한 성격)
이며, 어떤 라우트에도 아직 배선(wiring)되어 있지 않다(기존 쓰기 경로는 이
모듈을 아직 import하지 않는다 — 통합은 별도 STEP·승인 대상).

## v2 변경 사항(이번 STEP — payload 충돌 차단 + 결과 재사용 + FAILED_RETRYABLE 재분류)

**1) 요구사항 대조 결과(Gate Plan IDEM-01/02, ADR-017, API Contract)**:
- Gate Plan §21 원문: "IDEM-01 | 동일 idempotencyKey+동일 payload 재전송 |
  POST 2회 | 2번째는 캐시된 결과 반환(재실행 안함) | ADR-017 §14 | ...". "IDEM-02
  | 동일 idempotencyKey+다른 payload | POST 2회 | `IDEMPOTENCY_CONFLICT` |
  ADR-017 §14 | ... | **확정(원칙)**". → **"동일 key+다른 payload=
  IDEMPOTENCY_CONFLICT"는 "확정(원칙)"으로 명시된 요구사항**이다(미확정이
  아님). "2번째는 캐시된 결과 반환"(IDEM-01)도 확정 요구사항이나, **그
  반환할 결과(payload)를 저장소가 저장해야 한다는 조항은 ADR-017·API
  Contract 어디에도 없다** — 이 부분만 미확정(아래 "정책 미확정 사항" 참조).
- ADR-017 §12의 Canonical String은 이미 `<payloadHash>`(SHA-256) 필드를
  포함한다("payload 원문은 서명 대상에서 제외하고 payloadHash(SHA-256)만
  포함"). 즉 **"요청의 payload를 대표하는 해시값을 호출부(HMAC 서명 계층)가
  이미 계산한다"는 전제가 ADR에 이미 있다** — 이 모듈이 받는 `fingerprint`
  파라미터는 그 payloadHash를 그대로 재사용할 수 있도록 설계했다(단,
  payloadHash의 정규화 규칙 자체 — 어떤 JSON 직렬화를 해시하는지 — 는
  ADR-017 §12가 Canonical String 자체의 직렬화 규칙만 상술할 뿐 payload
  해시의 정규화 규칙까지 동일한 수준으로 명시하지는 않아, **그 연결은
  이 모듈의 제안일 뿐 ADR이 확정한 사실은 아니다**, Open Question).
- **문서 간 명시적 충돌은 발견되지 않았다.** Gate Plan·ADR-017·API
  Contract 모두 동일하게 ADR-017 §14를 근거로 인용하며 서로 다른 내용을
  주장하지 않는다.
- **FAILED_RETRYABLE 재분류(수정)**: v1에서 이 모듈은 FAILED_RETRYABLE을
  SUCCEEDED/FAILED_FINAL과 동일하게 "TTL 이내=차단(DUPLICATE_LIVE)"으로
  취급했다 — 이는 **오류**였다. ADR-017 §16은 "불확실 성공 상태(UNKNOWN/
  RECONCILIATION_REQUIRED)"만 자동 재시도 금지 대상으로 명시하며
  FAILED_RETRYABLE은 포함하지 않는다. FAILED_RETRYABLE은 "최종 상태"가
  아니라 "재시도 가능 상태"이며, 그 존재 이유 자체가 §16의 재시도(새
  nonce, 동일 key로 다시 시도)를 허용하기 위함이다. v1처럼 차단하면 §16의
  재시도 메커니즘이 작동할 수 없다. **v2는 FAILED_RETRYABLE이 TTL 이내일
  때 재시도를 허용(`RETRY_ACCEPTED`, IN_PROGRESS로 재오픈)하도록 수정했다.**
  SUCCEEDED/FAILED_FINAL만 진짜 "최종 상태"(`_FINAL_STATES`)로 재정의했다.

**2) payload 충돌 차단 설계**:
- `fingerprint` 책임 분리: **이 모듈은 fingerprint를 계산하지 않는다.**
  호출부(HMAC 서명 계층, 위 payloadHash 재사용 제안 참조)가 계산해 문자열로
  전달하면, 이 모듈은 그 값을 그대로 저장·비교만 한다(형식 검증만 수행,
  의미 검증 없음).
- 비교 범위: 기존 행이 **살아있는(TTL 이내) 경우에만** fingerprint를
  비교한다. 이미 만료되어 RECONCILIATION_REQUIRED/POLICY_UNDETERMINED로
  분류된 행은 어차피 모든 생성 시도를 차단하므로 fingerprint 비교가
  의미를 갖지 않는다(차단 사유가 "다른 작업이라서"가 아니라 "정책
  미확정/재조정 필요"이기 때문).
- 다른 fingerprint → `IDEMPOTENCY_CONFLICT`, 기존 행 **전혀 변경 없음**
  (ROLLBACK). 동일 fingerprint → 상태별 정상 분기(DUPLICATE_LIVE/
  RETRY_ACCEPTED).

**3) 완료 결과 재사용**: `record_outcome()`이 상태 전이와 함께 **같은
트랜잭션**으로 `result`(호출부가 만든 비식별 요약값, 자유 형식 문자열)를
기록할 수 있게 했다. `get_completed_result()`가 그 값을 조회한다(fingerprint
일치 확인 포함). **HTTP 상태코드·응답 JSON 스키마·보존기간은 이 모듈이
정의하지 않는다**(Open Question, 호출부·API 계약 단계에서 확정 사항).

## 정책 미확정 사항(이 모듈이 임의로 확정하지 않음 — 호출부·PM 결정에 위임)
- `SUCCEEDED`/`FAILED_RETRYABLE`/`FAILED_FINAL`의 TTL 경과 후 전이 대상,
  `UNKNOWN` 자신의 48시간 TTL 경과 "이후"의 처리 — 둘 다 ADR-017 어디에도
  명시되어 있지 않다(v1과 동일, 변경 없음). `POLICY_UNDETERMINED`로만
  분류하고 삭제·재생성하지 않는다.
- `fingerprint`(payloadHash 재사용 제안)의 **정규화 규칙 자체**는 확정되지
  않았다 — 이 모듈은 합성(테스트용) fingerprint 문자열로만 검증했다.
  운영 연계 시 실제 payload 정규화 규칙은 별도로 확정해야 한다.
- 재시도 횟수 상한(§16 "최대 3회") **집행(enforcement)은 이 모듈에 없다**
  — `RETRY_ACCEPTED`는 몇 번째 재시도인지 세지 않는다. 횟수 제한을
  저장소 계층에서 강제할지, 호출부(클라이언트 백오프)에만 맡길지는
  미확정(Open Question, 이번 STEP 범위 밖).
- "동일 key+동일 fingerprint=진짜 재시도" vs "동일 key+동일 fingerprint지만
  실제로는 새 작업"(우연한 fingerprint 충돌)의 구분은 여전히 이 모듈의
  범위 밖이다(정책 제안서 §4.5(a) 재확인, fingerprint만으로는 완전한
  구분이 불가능할 수 있음).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "reservation"))

from json_store import KST, now_iso  # noqa: E402

SCHEMA_VERSION = 2  # v2: fingerprint/result 컬럼 추가(배포된 데이터 없음 — 마이그레이션 불필요)
_DB_FILENAME = "idempotency.db"

# ADR-017 §14 확정값(PM 확정 — "§29의 부하검증이 완료되기 전까지 위 TTL은
# '구현 확정값'이 아니라 '설계 확정값'으로만 간주한다", ADR-017 §14 원문
# 재인용). 이 모듈은 이 값을 그대로 쓰되 최종 확정값으로 주장하지 않는다.
TTL_SECONDS: dict[str, int] = {
    "IN_PROGRESS": 60,
    "SUCCEEDED": 900,
    "FAILED_RETRYABLE": 300,
    "FAILED_FINAL": 900,
    "UNKNOWN": 172800,
}

_VALID_STATES = frozenset(TTL_SECONDS.keys())

# "최종 상태"(더 이상 자동 재시도 대상이 아님) vs "재시도 가능 상태" 구분.
# ADR-017 §16이 자동 재시도 금지 대상으로 명시한 것은 "불확실 성공 상태
# (UNKNOWN/RECONCILIATION_REQUIRED)"뿐이며 FAILED_RETRYABLE은 포함하지
# 않는다 — FAILED_RETRYABLE을 _FINAL_STATES에 넣는 것은 v1의 오류였다.
_FINAL_STATES = frozenset({"SUCCEEDED", "FAILED_FINAL"})
_RETRYABLE_STATE = "FAILED_RETRYABLE"
# record_outcome()이 IN_PROGRESS로부터 받을 수 있는 목표 상태(최종+재시도가능).
_OUTCOME_STATES = frozenset(_FINAL_STATES | {_RETRYABLE_STATE})

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\-:]{1,200}$")
_MAX_RESULT_LENGTH = 500  # 안전장치일 뿐 응답 형식을 규정하지 않음(모듈 docstring 참조)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS idempotency_store (
    key TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class IdempotencyError(RuntimeError):
    """예상 밖 저장소 오류(락 타임아웃, 예상 밖 무결성 위반 등). 호출부는
    이 예외를 그대로 전파받아 처리한다 — 이 모듈은 내부에서 재시도하거나
    오류를 조용히 삼키지 않는다."""


@dataclass(frozen=True)
class IdempotencyResult:
    """모든 공개 함수의 반환 타입. `classification`은 호출부가 분기할 때
    쓰는 값이며, 응답 코드·메시지로의 매핑은 이 모듈의 책임이 아니다.

    classification 전체 목록:
      CREATED / RETRY_ACCEPTED / DUPLICATE_LIVE / IDEMPOTENCY_CONFLICT /
      RECONCILIATION_REQUIRED / POLICY_UNDETERMINED / ABSENT /
      RECORDED(record_outcome 전용) / CACHED_RESULT(get_completed_result 전용) /
      RECONCILED(reconcile_unknown 전용) / NO_ACTION(reconcile_expired_in_progress 전용)
    """

    classification: str
    state: str
    result: Optional[str] = None


def _db_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / _DB_FILENAME


def _validate_key(key: str) -> str:
    """SQLite는 Parameter Binding으로 값 자체는 안전하지만(SQL Injection은
    이미 방지됨), 식별자성 값의 형식을 별도로 검증해 애플리케이션 레벨의
    이상값 유입을 막는다(auth_store.py::_validate_identifier와 동일 원칙)."""
    if not isinstance(key, str) or not _SAFE_TOKEN_RE.match(key):
        raise ValueError("허용되지 않는 idempotency key 형식")
    return key


def _validate_fingerprint(fingerprint: str) -> str:
    """형식 검증만 수행한다(길이·문자셋) — fingerprint의 **의미**(어떤
    payload 정규화 규칙으로 계산되었는지)는 검증하지 않는다. 그 책임은
    호출부(모듈 docstring "payload 충돌 차단 설계" 참조)에 있다."""
    if not isinstance(fingerprint, str) or not _SAFE_TOKEN_RE.match(fingerprint):
        raise ValueError("허용되지 않는 fingerprint 형식")
    return fingerprint


def _validate_result(result: Optional[str]) -> Optional[str]:
    """`result`는 호출부가 만드는 비식별 요약값이다. 이 함수는 길이만
    제한하는 안전장치이며, PII 탐지기가 아니다 — 원문 payload·개인정보를
    넣지 않을 책임은 호출부에 있다(모듈 docstring 재확인)."""
    if result is None:
        return None
    if not isinstance(result, str) or len(result) > _MAX_RESULT_LENGTH:
        raise ValueError(f"result는 문자열이며 {_MAX_RESULT_LENGTH}자를 넘을 수 없음")
    return result


@contextmanager
def connect(data_dir: Path | str) -> Iterator[sqlite3.Connection]:
    """단일 커넥션 컨텍스트. WAL 모드. 트랜잭션은 호출부(이 모듈의 공개
    함수들)가 명시적으로 BEGIN IMMEDIATE/COMMIT/ROLLBACK한다. auth_store.py
    ::connect()와 동일한 패턴(house convention)."""
    path = _db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def init_schema(data_dir: Path | str) -> None:
    """스키마가 없으면 생성한다(idempotent). 기존 DB를 손상시키지 않는다
    (auth_store.py::init_schema와 동일 원칙)."""
    with connect(data_dir) as conn:
        conn.executescript(_SCHEMA_SQL)
        cur = conn.execute("PRAGMA user_version")
        if cur.fetchone()[0] == 0:
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def _key_fingerprint_for_log(value: str) -> str:
    """로그 출력 전용 비식별 지문(ADR-017 §19 "Nonce 지문 앞 8자" 관행
    재사용). key에도, fingerprint 값 자체에도 동일하게 적용해 원문을
    로그에 절대 남기지 않는다."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _emit_metric(event: dict) -> None:
    """최소 계측. 저장소에 구조화 로깅 인프라가 아직 없음을 확인했다
    (`Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md` §26 "현재
    구조화 로깅 없음, stderr만"). 정식 로깅 체계 도입 전까지, stderr에
    파싱 가능한 JSON 한 줄을 출력하는 최소 수준으로만 구현한다.

    이 함수에 전달되는 dict에는 PII·예약내용·인증정보·원문 key/nonce/
    fingerprint/result가 없어야 한다(호출부 책임 — 이 모듈 내부 호출은
    전부 지문값만 전달한다). 계측 실패가 업무 로직을 막지 않도록 모든
    예외를 삼킨다."""
    try:
        print(json.dumps(event, ensure_ascii=False), file=sys.stderr)
    except Exception:  # noqa: BLE001 - 계측은 best-effort, 업무로직 방해 금지
        pass


def _elapsed_seconds(updated_at_iso: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(updated_at_iso)).total_seconds()


def _classify(conn: sqlite3.Connection, key: str, now: datetime) -> tuple[str, str]:
    """(phase, raw_state_or_ABSENT) 판정. DB를 변경하지 않는 순수 조회다.
    시간(TTL)만으로 판정하며 fingerprint는 보지 않는다(fingerprint 비교는
    상위 함수가 phase 결과를 보고 별도로 수행 — 책임 분리).

    phase 값: ABSENT / LIVE_IN_PROGRESS / LIVE_RETRYABLE / LIVE_FINAL /
    RECONCILIATION_REQUIRED / POLICY_UNDETERMINED.

    우선순위(ADR-017 §14/§16/§23, 호출 경로 무관 동일 결과 보장):
    1. UNKNOWN은 48시간 이내=RECONCILIATION_REQUIRED, 초과=POLICY_UNDETERMINED.
    2. IN_PROGRESS는 60초 이내=LIVE_IN_PROGRESS, 초과=RECONCILIATION_REQUIRED.
    3. FAILED_RETRYABLE은 300초 이내=LIVE_RETRYABLE(재시도 허용 대상),
       초과=POLICY_UNDETERMINED.
    4. SUCCEEDED/FAILED_FINAL은 각 TTL 이내=LIVE_FINAL, 초과=POLICY_UNDETERMINED.
    """
    row = conn.execute(
        "SELECT state, updated_at FROM idempotency_store WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return "ABSENT", "ABSENT"
    state = row["state"]
    elapsed = _elapsed_seconds(row["updated_at"], now)

    if state == "UNKNOWN":
        if elapsed <= TTL_SECONDS["UNKNOWN"]:
            return "RECONCILIATION_REQUIRED", state
        return "POLICY_UNDETERMINED", state

    if state == "IN_PROGRESS":
        if elapsed <= TTL_SECONDS["IN_PROGRESS"]:
            return "LIVE_IN_PROGRESS", state
        return "RECONCILIATION_REQUIRED", state

    if state == _RETRYABLE_STATE:
        if elapsed <= TTL_SECONDS[state]:
            return "LIVE_RETRYABLE", state
        return "POLICY_UNDETERMINED", state

    # SUCCEEDED / FAILED_FINAL
    if elapsed <= TTL_SECONDS[state]:
        return "LIVE_FINAL", state
    return "POLICY_UNDETERMINED", state


def get_effective_state(
    conn: sqlite3.Connection,
    *,
    key: str,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """순수 읽기 전용 조회(부작용 없음, DB를 변경하지 않는다). IN_PROGRESS가
    만료되었어도 이 함수는 물리적으로 전이시키지 않는다 — 실제 전이(UPDATE)는
    `try_create()` 또는 `reconcile_expired_in_progress()`가 쓰기 락을 쥔
    시점에만 수행한다. 그럼에도 **이 함수의 반환 classification은 물리적
    전이 여부와 무관하게 항상 RECONCILIATION_REQUIRED를 보고한다**(아래
    phase→classification 매핑 참조) — "유효 상태가 UNKNOWN이면 물리적
    상태가 아직 IN_PROGRESS여도 자동 재실행이 차단되어야 한다"는 요구사항을
    조회 경로에서도 만족시키기 위함이다."""
    _validate_key(key)
    now_dt = now or datetime.now(KST)
    t0 = time.perf_counter()
    phase, state = _classify(conn, key, now_dt)
    classification = _phase_to_blocking_classification(phase, state)
    _emit_metric(
        {
            "ts": now_iso(),
            "op": "get_effective_state",
            "correlation_id": correlation_id,
            "key_fp": _key_fingerprint_for_log(key),
            "classification": classification,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )
    return IdempotencyResult(classification=classification, state=state)


def _phase_to_blocking_classification(phase: str, state: str) -> str:
    """읽기 전용 조회(`get_effective_state`/`get_completed_result`)에서
    쓰는 공용 매핑 — fingerprint 비교가 필요 없는 phase들을 사람이 읽을
    classification 이름으로 변환한다. LIVE_* phase는 호출부가 fingerprint를
    아직 비교하지 않았을 수 있으므로 그대로 "DUPLICATE_LIVE"로 보수적으로
    보고한다(진짜 CREATED/RETRY_ACCEPTED 여부는 try_create()만 판정)."""
    if phase == "ABSENT":
        return "ABSENT"
    if phase in ("LIVE_IN_PROGRESS", "LIVE_RETRYABLE", "LIVE_FINAL"):
        return "DUPLICATE_LIVE"
    return phase  # RECONCILIATION_REQUIRED / POLICY_UNDETERMINED


def try_create(
    conn: sqlite3.Connection,
    *,
    key: str,
    fingerprint: str,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """동일 key에 대한 생성/재시도 시도. BEGIN IMMEDIATE로 원자성을
    확보한다(동시 요청 중 정확히 1건만 CREATED/RETRY_ACCEPTED).

    `fingerprint`는 호출부가 계산한 요청 대표값(payloadHash 재사용 제안,
    모듈 docstring 참조)이다 — 이 함수는 그 값을 저장·비교만 한다.

    분기:
    - 행 없음 → 신규 IN_PROGRESS 생성, CREATED.
    - 기존 행이 살아있고(LIVE_*) fingerprint가 다르면 → IDEMPOTENCY_CONFLICT,
      **기존 행 변경 없음**(ROLLBACK).
    - 기존 행이 살아있고 fingerprint가 같으면:
        - LIVE_IN_PROGRESS/LIVE_FINAL → DUPLICATE_LIVE(차단, 변경 없음).
        - LIVE_RETRYABLE → **재시도 허용**: 같은 행을 IN_PROGRESS로 재오픈
          하고 RETRY_ACCEPTED 반환(ADR-017 §16 재시도 메커니즘 지원 —
          FAILED_RETRYABLE은 최종 상태가 아니므로 차단하지 않는다).
    - IN_PROGRESS 만료 → 이 시점에 UNKNOWN으로 전이(삭제 아님), 유효 상태가
      이미 UNKNOWN(선행 조회로 전이됨)이어도 결과는 동일(RECONCILIATION_
      REQUIRED) — 호출 경로 무관 동일 결과.
    - 그 외 만료(SUCCEEDED/FAILED_FINAL/FAILED_RETRYABLE 자체 TTL 초과) →
      POLICY_UNDETERMINED, 어떤 조치도 취하지 않음(삭제·재생성 없음).

    트랜잭션 실패(예상 밖 OperationalError 등) 시 rollback 후 IdempotencyError
    로 전파한다 — 조용히 삼키지 않는다."""
    _validate_key(key)
    _validate_fingerprint(fingerprint)
    now_dt = now or datetime.now(KST)
    ts = now_dt.isoformat(timespec="seconds")
    t0 = time.perf_counter()
    try:
        conn.execute("BEGIN IMMEDIATE")
        phase, state = _classify(conn, key, now_dt)

        if phase == "ABSENT":
            try:
                conn.execute(
                    "INSERT INTO idempotency_store "
                    "(key, state, fingerprint, result, created_at, updated_at) "
                    "VALUES (?, 'IN_PROGRESS', ?, NULL, ?, ?)",
                    (key, fingerprint, ts, ts),
                )
            except sqlite3.IntegrityError as e:
                # BEGIN IMMEDIATE가 쓰기를 직렬화하므로 정상 흐름에서는
                # 발생하지 않아야 한다 — 발생하면 예상 밖 상황으로 간주해
                # rollback 후 전파한다.
                conn.execute("ROLLBACK")
                raise IdempotencyError(
                    f"BEGIN IMMEDIATE 보호 하에서도 UNIQUE 충돌 발생(예상 밖): {e}"
                ) from e
            conn.execute("COMMIT")
            result = IdempotencyResult(classification="CREATED", state="IN_PROGRESS")

        elif phase in ("LIVE_IN_PROGRESS", "LIVE_RETRYABLE", "LIVE_FINAL"):
            stored = conn.execute(
                "SELECT fingerprint FROM idempotency_store WHERE key = ?", (key,)
            ).fetchone()
            if stored["fingerprint"] != fingerprint:
                conn.execute("ROLLBACK")
                result = IdempotencyResult(classification="IDEMPOTENCY_CONFLICT", state=state)
            elif phase == "LIVE_RETRYABLE":
                conn.execute(
                    "UPDATE idempotency_store SET state = 'IN_PROGRESS', updated_at = ? WHERE key = ?",
                    (ts, key),
                )
                conn.execute("COMMIT")
                result = IdempotencyResult(classification="RETRY_ACCEPTED", state="IN_PROGRESS")
            else:
                conn.execute("ROLLBACK")
                result = IdempotencyResult(classification="DUPLICATE_LIVE", state=state)

        elif phase == "RECONCILIATION_REQUIRED":
            if state == "IN_PROGRESS":
                conn.execute(
                    "UPDATE idempotency_store SET state = 'UNKNOWN', updated_at = ? WHERE key = ?",
                    (ts, key),
                )
                conn.execute("COMMIT")
            else:
                conn.execute("ROLLBACK")
            result = IdempotencyResult(classification="RECONCILIATION_REQUIRED", state="UNKNOWN")

        elif phase == "POLICY_UNDETERMINED":
            conn.execute("ROLLBACK")
            result = IdempotencyResult(classification="POLICY_UNDETERMINED", state=state)

        else:  # pragma: no cover - 방어적 분기, _classify의 반환값 집합 밖
            conn.execute("ROLLBACK")
            raise IdempotencyError(f"알 수 없는 내부 분류값: {phase}")

    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise IdempotencyError(f"저장소 트랜잭션 오류: {e}") from e
    finally:
        _emit_metric(
            {
                "ts": now_iso(),
                "op": "try_create",
                "correlation_id": correlation_id,
                "key_fp": _key_fingerprint_for_log(key),
                "classification": locals().get("result").classification
                if "result" in locals()
                else "ERROR",
                "duration_ms": round((time.perf_counter() - t0) * 1000, 3),
            }
        )

    return result


def record_outcome(
    conn: sqlite3.Connection,
    *,
    key: str,
    outcome_state: str,
    result: Optional[str] = None,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """IN_PROGRESS로 생성/재오픈된 레코드에 실제 업무 결과를 기록한다(정상
    완료 경로). `outcome_state`는 SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL
    중 하나여야 한다. **이 모듈은 운영 예약 생성·변경을 호출하지 않으므로**,
    실제 업무 작업(GAS 호출 등)은 호출부가 수행한 뒤 그 결과만 이 함수에
    알려준다.

    `result`(선택, 비식별 요약 문자열)가 주어지면 **상태 전이와 같은
    UPDATE문·같은 트랜잭션**으로 함께 기록한다(요구사항: "상태 변경과
    결과 기록을 같은 트랜잭션으로 처리"). 원문 payload·개인정보를 넣지
    않을 책임은 호출부에 있다(길이 제한만 이 함수가 강제함, §_validate_result).

    현재 raw state가 정확히 "IN_PROGRESS"가 아니면 ValueError를 낸다 —
    ADR에 명시되지 않은 동작이라 이 모듈이 임의로 허용하지 않는 보수적
    설계다(Open Question)."""
    _validate_key(key)
    if outcome_state not in _OUTCOME_STATES:
        raise ValueError(
            f"outcome_state는 {sorted(_OUTCOME_STATES)} 중 하나여야 함: {outcome_state!r}"
        )
    result = _validate_result(result)
    now_dt = now or datetime.now(KST)
    ts = now_dt.isoformat(timespec="seconds")
    t0 = time.perf_counter()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT state FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            raise ValueError(
                f"존재하지 않는 key에 결과를 기록할 수 없음: key_fp={_key_fingerprint_for_log(key)}"
            )
        if row["state"] != "IN_PROGRESS":
            conn.execute("ROLLBACK")
            raise ValueError(
                f"IN_PROGRESS가 아닌 레코드(state={row['state']!r})에는 record_outcome()을 "
                "적용하지 않는다(정책 미확정 — Open Question)"
            )
        conn.execute(
            "UPDATE idempotency_store SET state = ?, result = ?, updated_at = ? WHERE key = ?",
            (outcome_state, result, ts, key),
        )
        conn.execute("COMMIT")
        outcome_result = IdempotencyResult(classification="RECORDED", state=outcome_state, result=result)
    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise IdempotencyError(f"저장소 트랜잭션 오류: {e}") from e
    finally:
        _emit_metric(
            {
                "ts": now_iso(),
                "op": "record_outcome",
                "correlation_id": correlation_id,
                "key_fp": _key_fingerprint_for_log(key),
                "classification": locals().get("outcome_result").classification
                if "outcome_result" in locals()
                else "ERROR",
                "duration_ms": round((time.perf_counter() - t0) * 1000, 3),
            }
        )
    return outcome_result


def get_completed_result(
    conn: sqlite3.Connection,
    *,
    key: str,
    fingerprint: str,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """IDEM-01이 요구하는 "캐시된 결과 재조회"를 위한 최소 읽기 인터페이스.
    순수 읽기(부작용 없음). fingerprint가 다르면 IDEMPOTENCY_CONFLICT를
    반환하고(행은 애초에 변경하지 않음 — 읽기이므로), state가 SUCCEEDED/
    FAILED_FINAL(LIVE_FINAL)일 때만 `result`를 채워 CACHED_RESULT를
    반환한다. 그 외(아직 처리 중, 재시도 가능, 재조정 필요, 정책 미확정)는
    `result=None`으로 해당 classification만 반환한다 — **응답 HTTP
    상태코드·JSON 스키마는 이 함수가 정의하지 않는다**(Open Question)."""
    _validate_key(key)
    _validate_fingerprint(fingerprint)
    now_dt = now or datetime.now(KST)
    t0 = time.perf_counter()
    phase, state = _classify(conn, key, now_dt)

    if phase == "ABSENT":
        classification, result_value = "ABSENT", None
    else:
        row = conn.execute(
            "SELECT fingerprint, result FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if phase in ("LIVE_IN_PROGRESS", "LIVE_RETRYABLE", "LIVE_FINAL") and row["fingerprint"] != fingerprint:
            classification, result_value = "IDEMPOTENCY_CONFLICT", None
        elif phase == "LIVE_FINAL":
            classification, result_value = "CACHED_RESULT", row["result"]
        else:
            classification, result_value = _phase_to_blocking_classification(phase, state), None

    _emit_metric(
        {
            "ts": now_iso(),
            "op": "get_completed_result",
            "correlation_id": correlation_id,
            "key_fp": _key_fingerprint_for_log(key),
            "classification": classification,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )
    return IdempotencyResult(classification=classification, state=state, result=result_value)


def reconcile_expired_in_progress(
    conn: sqlite3.Connection,
    *,
    key: str,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """IN_PROGRESS 만료를 물리적으로 UNKNOWN 전이시키는 **명시적** 메서드.
    `try_create()`도 동일 전이를 내부적으로 수행하지만, 이 함수는 "생성
    시도" 없이 전이만 수행하고 싶은 경우(예: 향후 배치 잡 설계 검토용)를
    위해 별도로 노출한다. **이 함수는 어떤 스케줄러·배치 작업·라우트에도
    연결되어 있지 않다** — 호출자가 명시적으로 불러야 한다."""
    _validate_key(key)
    now_dt = now or datetime.now(KST)
    ts = now_dt.isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT state, updated_at FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return IdempotencyResult(classification="ABSENT", state="ABSENT")
        is_expired_in_progress = (
            row["state"] == "IN_PROGRESS"
            and _elapsed_seconds(row["updated_at"], now_dt) > TTL_SECONDS["IN_PROGRESS"]
        )
        if not is_expired_in_progress:
            conn.execute("ROLLBACK")
            return IdempotencyResult(classification="NO_ACTION", state=row["state"])
        conn.execute(
            "UPDATE idempotency_store SET state = 'UNKNOWN', updated_at = ? WHERE key = ?",
            (ts, key),
        )
        conn.execute("COMMIT")
        return IdempotencyResult(classification="RECONCILIATION_REQUIRED", state="UNKNOWN")
    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise IdempotencyError(f"저장소 트랜잭션 오류: {e}") from e


def mark_unknown(
    conn: sqlite3.Connection,
    *,
    key: str,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """오케스트레이션 계층(예: `gas_orchestration.py`)이 "GAS 요청을 보냈으나
    결과를 확정할 수 없다"(요청 전송 후 timeout/연결오류, 또는 GAS 응답은
    받았으나 그 결과를 로컬에 기록하는 데 실패한 경우 포함)고 판단한 **즉시**
    호출하는 명시적 전이 메서드다.

    `reconcile_expired_in_progress()`와의 차이: 그 함수는 **IN_PROGRESS TTL
    (60초)이 실제로 경과했을 때만** 동작하는 시간 기반 지연 전이이고, 이
    함수는 **TTL 경과 여부와 무관하게 즉시** IN_PROGRESS를 UNKNOWN으로
    전이시킨다 — "불확실성을 감지한 순간 바로 기록한다"는 요구사항(60초를
    기다리지 않음)을 만족하기 위함이다.

    현재 raw state가 정확히 "IN_PROGRESS"가 아니면 ValueError를 낸다(이미
    다른 상태로 전이된 레코드를 되돌리거나 덮어쓰지 않는다). 트랜잭션 실패
    시 rollback 후 IdempotencyError로 전파한다 — **호출부는 이 실패를 GAS
    재호출 신호로 쓰지 않아야 한다**(기존 IN_PROGRESS+TTL 안전망에 맡긴다,
    오케스트레이션 계층의 책임)."""
    _validate_key(key)
    now_dt = now or datetime.now(KST)
    ts = now_dt.isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT state FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            raise ValueError(
                f"존재하지 않는 key를 UNKNOWN으로 표시할 수 없음: key_fp={_key_fingerprint_for_log(key)}"
            )
        if row["state"] != "IN_PROGRESS":
            conn.execute("ROLLBACK")
            raise ValueError(
                f"IN_PROGRESS가 아닌 레코드(state={row['state']!r})는 mark_unknown() 대상이 아님"
            )
        conn.execute(
            "UPDATE idempotency_store SET state = 'UNKNOWN', updated_at = ? WHERE key = ?",
            (ts, key),
        )
        conn.execute("COMMIT")
        result = IdempotencyResult(classification="MARKED_UNKNOWN", state="UNKNOWN")
    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise IdempotencyError(f"저장소 트랜잭션 오류: {e}") from e
    finally:
        _emit_metric(
            {
                "ts": now_iso(),
                "op": "mark_unknown",
                "correlation_id": correlation_id,
                "key_fp": _key_fingerprint_for_log(key),
                "classification": locals().get("result").classification
                if "result" in locals()
                else "ERROR",
            }
        )
    return result


def reconcile_unknown(
    conn: sqlite3.Connection,
    *,
    key: str,
    resolved_state: str,
    performed_by: str,
    result: Optional[str] = None,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> IdempotencyResult:
    """ADR-017 §23 "운영자의 Sheets 직접 확인 후 수동으로 SUCCEEDED 또는
    FAILED_FINAL로 전이"를 위한 **수동·명시적** 전이 함수다. **이 함수는 어떤
    라우트·스케줄러에도 자동 연결되어 있지 않다** — 호출 자체가 "사람이
    확인했다"는 것을 전제로 하며, `performed_by`(운영자 식별자, PII 아닌
    로그인ID 등)를 필수로 받아 "자동 재실행이 아니라 수동 조정"임을 코드
    구조로도 드러낸다.

    현재 raw state가 "UNKNOWN"이 아니면 ValueError를 낸다. resolved_state는
    SUCCEEDED 또는 FAILED_FINAL만 허용한다(ADR-017 §23 원문 그대로).
    `result`(선택)는 운영자가 Sheets를 직접 확인한 뒤 남기는 비식별 요약값
    으로, `record_outcome()`과 동일하게 상태 전이와 같은 트랜잭션으로
    기록된다 — 수동 조정 후에도 `get_completed_result()`로 재조회 가능하게
    하기 위한 확장이다(원래 요청사항에는 없었으나, record_outcome과의
    일관성을 위해 이번 STEP에서 추가)."""
    _validate_key(key)
    if resolved_state not in _FINAL_STATES:
        raise ValueError("resolved_state는 SUCCEEDED 또는 FAILED_FINAL만 허용함(ADR-017 §23)")
    if not performed_by:
        raise ValueError("performed_by(운영자 식별자)가 필요함 — 자동 호출 금지")
    result = _validate_result(result)
    now_dt = now or datetime.now(KST)
    ts = now_dt.isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT state FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None or row["state"] != "UNKNOWN":
            conn.execute("ROLLBACK")
            raise ValueError("UNKNOWN 상태의 레코드에만 reconcile_unknown()을 적용할 수 있음")
        conn.execute(
            "UPDATE idempotency_store SET state = ?, result = ?, updated_at = ? WHERE key = ?",
            (resolved_state, result, ts, key),
        )
        conn.execute("COMMIT")
        result_obj = IdempotencyResult(classification="RECONCILED", state=resolved_state, result=result)
    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise IdempotencyError(f"저장소 트랜잭션 오류: {e}") from e
    finally:
        _emit_metric(
            {
                "ts": now_iso(),
                "op": "reconcile_unknown",
                "correlation_id": correlation_id,
                "key_fp": _key_fingerprint_for_log(key),
                "performed_by_present": bool(performed_by),
                "classification": locals().get("result_obj").classification
                if "result_obj" in locals()
                else "ERROR",
            }
        )
    return result_obj
