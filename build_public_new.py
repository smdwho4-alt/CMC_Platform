"""Netlify 공개 배포 경계(Publish Boundary) — public/ Allowlist 생성 스크립트.

app/ 전체를 복사한 뒤 민감 파일을 제외하는 방식(차단목록)이 아니라, 운영에
필요하다고 확인된 파일·디렉터리만 명시적으로 나열해 복사하는 허용목록 방식이다
(Commit8-2d STEP1 설계, PM 결정: B안 채택). app/apps_script/, app/docs/,
src/, tests/, docs/, tools/, data/ 등은 이 목록에 없으므로 애초에 복사되지
않는다 — 별도 차단 규칙에 의존하지 않는다.

원본 app/ 파일은 읽기만 하며 수정·이동·삭제하지 않는다. public/ 은 이 스크립트가
매 실행마다 새로 생성하는 빌드 산출물이므로, 실행 시작 시 public/ 자신만
삭제 후 재생성한다(그 외 어떤 경로도 삭제하지 않는다).

Netlify 빌드 커맨드로 사용: `python3 build_public_new.py`
로컬 검증: `python build_public_new.py`
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"

# 허용목록 — 디렉터리 전체 복사 (app/ 전체 복사 후 제외하는 방식이 아니라,
# 필요하다고 확인된 디렉터리만 개별적으로 나열한다)
ALLOWLIST_DIRS = [
    ("app/pages", "pages"),
    ("app/styles", "styles"),
    ("app/components", "components"),
    ("app/data", "data"),
    ("app/services", "services"),
]

# 허용목록 — 개별 파일 복사
ALLOWLIST_FILES = [
    ("app/config_new.js", "config_new.js"),
    ("app/config_v2_new.js", "config_v2_new.js"),
]


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def _validate_sources() -> None:
    for src_rel, _ in ALLOWLIST_DIRS:
        src = ROOT / src_rel
        if not src.is_dir():
            _fail(f"필수 소스 디렉터리를 찾을 수 없습니다: {src_rel}")
    for src_rel, _ in ALLOWLIST_FILES:
        src = ROOT / src_rel
        if not src.is_file():
            _fail(f"필수 소스 파일을 찾을 수 없습니다: {src_rel}")


def _reset_public_dir() -> None:
    # public/ 만 정확히 대상으로 하는지 확인 후에만 삭제한다(광범위한 삭제 방지).
    resolved = PUBLIC_DIR.resolve()
    if resolved.name != "public" or resolved.parent != ROOT:
        _fail(f"public/ 경로 검증 실패 — 예상 밖 경로라 중단합니다: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _copy_allowlist() -> list[str]:
    copied: list[str] = []
    for src_rel, dst_rel in ALLOWLIST_DIRS:
        shutil.copytree(ROOT / src_rel, PUBLIC_DIR / dst_rel)
    for src_rel, dst_rel in ALLOWLIST_FILES:
        shutil.copy2(ROOT / src_rel, PUBLIC_DIR / dst_rel)
    for p in sorted(PUBLIC_DIR.rglob("*")):
        if p.is_file():
            copied.append(str(p.relative_to(PUBLIC_DIR)).replace("\\", "/"))
    return copied


def main() -> None:
    _validate_sources()
    _reset_public_dir()
    copied = _copy_allowlist()
    if not copied:
        _fail("public/ 생성 결과가 비어 있습니다(복사 대상 없음)")
    print(f"[OK] public/ 생성 완료 — 총 {len(copied)}개 파일")
    for rel in copied:
        print(f"  {rel}")


if __name__ == "__main__":
    main()
