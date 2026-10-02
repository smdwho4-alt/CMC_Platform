# -*- coding: utf-8 -*-
"""
CSHSP Nonce 이중저장 — Sprint8 Commit8-3b (격리 개발, 로컬 전용)

ADR-017 §13("Nonce 영속화 구조")이 정의한 이중 구조(FastAPI SQLite 1차 방어 +
GAS CacheService 2차 방어, 저장 실패 시 Fail-Closed)의 최소 구현이다.

**Primary(SQLite)는 house 컨벤션(`src/auth/auth_store.py`/
`src/idempotency/idempotency_store.py`와 동일)을 따르는 실제 구현**이지만,
**Secondary는 `FakeSecondaryNonceStore`로 대체했다** — 실제 GAS
CacheService를 사용하지 않는다(운영 GAS 접근 없음). `FakeSecondaryNonceStore`는
**실제 CacheService의 원자성(`LockService` 기반)·1,000항목 LRU eviction·
네트워크 특성을 증명하지 않는다** — PoC#2(`Sprint8_DR_B_01_PoC2_GAS_
CacheService_Result_Report.md`)가 이미 지적한 동일한 한계를 그대로
계승한다. 이 모듈이 PASS하더라도 실제 GAS 연동 검증(별도 PM 승인·격리
환경에서의 PoC#2급 실측)을 대체하지 않는다.

## 생성·길이·인코딩·유일성 범위·TTL(계약 정합성 보완안 §4 재확인)
- **난수원**: `secrets.token_hex()` — Python 표준 CSPRNG(`os.urandom` 기반),
  보안 목적 토큰 생성에 공식 권장되는 모듈.
- **길이**: 16바이트(128비트) = hex 32자. 300초(Secondary TTL 기본값)~배치
  정리 주기 윈도우 내 추측·충돌 가능성을 무시할 수 있는 엔트로피.
- **인코딩**: 소문자 hex(`payloadHash`/key_fingerprint 관행과 통일).
- **유일성 범위**: 전역(모든 클라이언트·요청에 걸쳐) — Primary의 SQLite
  `UNIQUE` 제약과 Secondary의 중복 검사가 함께 강제한다. 세션/사용자 단위로
  범위를 좁히지 않는다(128비트 엔트로피로 충분).
- **TTL**: Secondary(Fake) 기본 300초는 ADR-017 §13이 확정한 GAS
  CacheService TTL 값을 그대로 참고한 것이다(운영 확정값 재확인, 이 모듈이
  새로 제안한 값이 아님). Primary(SQLite)는 이 모듈 범위에서 자동 만료
  삭제를 수행하지 않는다 — ADR §13의 "FastAPI DB는 배치 작업(1시간 주기)
  으로 만료분 삭제" 정책은 별도 배치 잡의 책임이며 이 모듈에 포함되지
  않는다(Open Question, 명시).

## 처리 순서와 Fail-Closed(ADR-017 §13, PoC#3 실측 패턴 재사용)
1. **Primary 먼저** INSERT 시도(`BEGIN IMMEDIATE` + `UNIQUE` 제약으로 원자성).
   이미 존재하면(`EXISTING`) 그 자리에서 즉시 `NONCE_REPLAYED`로 거부한다
   — Secondary는 조회하지 않는다(이미 복제임이 확실하므로).
2. Primary가 `NEW`로 **커밋을 마친 뒤** Secondary를 확인한다.
3. Secondary가 `EXISTING`이거나 `ERROR`면 **요청 전체를 차단**한다
   (`NONCE_REPLAYED`/`NONCE_STORE_FAILED`) — 하지만 **이미 커밋된 Primary
   레코드는 삭제하지 않는다.** 삭제하면 동일 nonce의 재사용(진짜 Replay
   공격이나 네트워크 중복 전송)이 이후 "NEW"로 재평가되어 통과할 수 있는
   치명적 위험이 생긴다(계약 정합성 보완안 §4-2 재확인) — 보존이 ADR §13의
   Fail-Closed 원칙과 일관된 선택이다.
4. 따라서 **Secondary DENY로 차단된 이후에도, 보존된 동일 nonce로 다시
   호출하면 Primary 단계에서 곧바로 `EXISTING`→`NONCE_REPLAYED`**가 된다
   (재사용 차단이 자동으로 유지됨, 추가 코드 불필요).
"""
from __future__ import annotations

import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

_DB_FILENAME = "nonce_store.db"
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\-:]{1,200}$")

DEFAULT_NONCE_BYTES = 16  # 128비트
DEFAULT_SECONDARY_TTL_SECONDS = 300  # ADR-017 §13 확정값 재참조(이 모듈이 새로 정한 값 아님)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nonce_store (
    nonce TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
"""


def generate_nonce(n_bytes: int = DEFAULT_NONCE_BYTES) -> str:
    """암호학적으로 안전한 난수원(`secrets.token_hex`)으로 nonce를 생성한다.
    기본 128비트(32 hex 문자)."""
    return secrets.token_hex(n_bytes)


def _validate_nonce(nonce: str) -> str:
    if not isinstance(nonce, str) or not _SAFE_TOKEN_RE.match(nonce):
        raise ValueError("허용되지 않는 nonce 형식")
    return nonce


def _db_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / _DB_FILENAME


@contextmanager
def connect(data_dir: Path | str) -> Iterator[sqlite3.Connection]:
    """house 컨벤션(`auth_store.py`/`idempotency_store.py`와 동일): WAL,
    호출부가 명시적으로 BEGIN IMMEDIATE/COMMIT/ROLLBACK."""
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
    with connect(data_dir) as conn:
        conn.executescript(_SCHEMA_SQL)


class NonceStoreError(RuntimeError):
    """예상 밖 저장소 오류(락 타임아웃 등). 호출부는 그대로 전파받는다."""


def _primary_try_insert(conn: sqlite3.Connection, nonce: str, now_iso: str) -> str:
    """Primary(SQLite) 1회 삽입 시도. 반환: 'NEW' | 'EXISTING'."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO nonce_store (nonce, created_at) VALUES (?, ?)", (nonce, now_iso)
            )
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return "EXISTING"
        conn.execute("COMMIT")
        return "NEW"
    except sqlite3.OperationalError as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise NonceStoreError(f"Primary 저장소 트랜잭션 오류: {e}") from e


class FakeSecondaryNonceStore:
    """GAS CacheService를 대체하는 **테스트/로컬 전용 Fake**. 실제
    CacheService의 원자성(`LockService` 기반)·1,000항목 LRU eviction·
    네트워크 특성을 증명하지 않는다(모듈 docstring 재확인). dict+TTL로만
    "이미 본 nonce인가"를 흉내 낸다."""

    def __init__(self, ttl_seconds: int = DEFAULT_SECONDARY_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: dict[str, float] = {}
        self._lock = threading.Lock()
        self._force_error_remaining = 0

    def force_error(self, times: int = 1) -> None:
        """다음 `times`번의 `check_and_mark()` 호출에서 강제로 'ERROR'를
        반환한다(테스트 전용 — GAS 측 일시적 장애 시뮬레이션)."""
        with self._lock:
            self._force_error_remaining += times

    def check_and_mark(self, nonce: str, now: float) -> str:
        """반환: 'NEW' | 'EXISTING' | 'ERROR'. 'NEW'일 때만 내부에 등록한다."""
        with self._lock:
            if self._force_error_remaining > 0:
                self._force_error_remaining -= 1
                return "ERROR"
            expiry = self._store.get(nonce)
            if expiry is not None and expiry > now:
                return "EXISTING"
            self._store[nonce] = now + self._ttl
            return "NEW"


@dataclass(frozen=True)
class NonceEvaluation:
    """`evaluate_and_register_nonce()`의 반환 타입. `classification`은
    API Contract가 이미 제안한 오류코드 이름(`NONCE_REPLAYED`/
    `NONCE_STORE_FAILED`)을 재사용하거나 `ACCEPTED`다 — 내부 참고용이며
    HTTP 계약 확정이 아니다(signing_v2.py와 동일 원칙)."""

    classification: str  # ACCEPTED / NONCE_REPLAYED / NONCE_STORE_FAILED
    primary_status: str  # NEW / EXISTING
    secondary_status: Optional[str] = None  # NEW / EXISTING / ERROR / None(Primary에서 이미 차단된 경우)


def evaluate_and_register_nonce(
    primary_conn: sqlite3.Connection,
    secondary_store: FakeSecondaryNonceStore,
    *,
    nonce: str,
    now: float,
    now_iso: str,
) -> NonceEvaluation:
    """Primary 먼저 확인·커밋, 그 다음 Secondary 확인(모듈 docstring
    "처리 순서와 Fail-Closed" 참조). Primary가 이미 `EXISTING`이면
    Secondary는 조회하지 않는다. Secondary가 `EXISTING`/`ERROR`면 전체
    요청을 차단하되 **Primary 레코드는 삭제하지 않는다**(보존)."""
    _validate_nonce(nonce)
    primary_status = _primary_try_insert(primary_conn, nonce, now_iso)
    if primary_status == "EXISTING":
        return NonceEvaluation(
            classification="NONCE_REPLAYED", primary_status="EXISTING", secondary_status=None
        )

    secondary_status = secondary_store.check_and_mark(nonce, now)
    if secondary_status == "EXISTING":
        return NonceEvaluation(
            classification="NONCE_REPLAYED", primary_status="NEW", secondary_status="EXISTING"
        )
    if secondary_status == "ERROR":
        return NonceEvaluation(
            classification="NONCE_STORE_FAILED", primary_status="NEW", secondary_status="ERROR"
        )
    return NonceEvaluation(classification="ACCEPTED", primary_status="NEW", secondary_status="NEW")
