# -*- coding: utf-8 -*-
"""
CSHSP File Lock — Sprint D
JSON 데이터 폴더 쓰기 동시성 보호.

- 프로세스 내: threading.RLock (uvicorn 스레드 동시 요청 직렬화)
- 프로세스 간: data_dir/.cshsp.lock 파일 배타 잠금 (Windows msvcrt / POSIX fcntl)

사용:
    with DataLock(data_dir):
        ... 엔진 쓰기 작업 ...
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

_THREAD_LOCK = threading.RLock()

if os.name == "nt":
    import msvcrt

    def _lock_file(f):
        while True:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)  # 최대 10회/10초 재시도 내장
                return
            except OSError:
                time.sleep(0.1)

    def _unlock_file(f):
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class DataLock:
    """데이터 폴더 단위 배타 잠금 컨텍스트 매니저 (재진입 가능)."""

    def __init__(self, data_dir: Path | str, timeout: float = 30.0):
        self.lock_path = Path(data_dir) / ".cshsp.lock"
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        _THREAD_LOCK.acquire()
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.lock_path, "a+")
            self._fh.seek(0)
            _lock_file(self._fh)
        except Exception:
            _THREAD_LOCK.release()
            raise
        return self

    def __exit__(self, *exc):
        try:
            if self._fh:
                _unlock_file(self._fh)
                self._fh.close()
                self._fh = None
        finally:
            _THREAD_LOCK.release()
        return False
