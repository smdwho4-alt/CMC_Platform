# -*- coding: utf-8 -*-
"""
CSHSP Admin Authentication — 관리자 계정 부트스트랩 CLI (Sprint8 Commit8-2)

운영 인증 계정을 생성하는 유일한 안전 경로다. 애플리케이션 코드는 어떤
기본 계정·기본 비밀번호도 자동으로 생성하지 않는다(PM 승인사항 §7 금지사항).

사용법(대화형, 비밀번호는 표시되지 않음):
    python src/auth/bootstrap_admin.py \
        --data-dir <data_dir> \
        --user-id USR-0001 \
        --login-id admin01

--user-id는 반드시 기존 data/users.json(Core Data Layer)에 이미 존재하는
사용자 id와 일치해야 한다(신원 SSOT는 users.json — 이 CLI는 그 사용자에 대한
로그인 자격증명만 SQLite에 추가한다). 존재하지 않는 id를 지정하면 오류로
중단한다.

이 스크립트는 이번 Commit에서 실행하지 않았다 — 실제 운영 계정 생성은
DR8-1-04(계정 생성·승인 주체, 병원 전산담당) 결정 이후 별도로 수행한다.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "core"))
sys.path.insert(0, str(_HERE))

import core_data_loader as loader  # noqa: E402

import auth_service  # noqa: E402
import auth_store as store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="CSHSP 관리자 인증 계정 생성(부트스트랩)")
    parser.add_argument("--data-dir", required=True, help="데이터 디렉터리 경로")
    parser.add_argument("--user-id", required=True, help="기존 users.json의 사용자 id")
    parser.add_argument("--login-id", required=True, help="신규 로그인 ID")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    identity = next(
        (u for u in loader.load_entity("User", data_dir) if u.get("id") == args.user_id), None
    )
    if identity is None:
        print(f"오류: users.json에 존재하지 않는 사용자 id: {args.user_id}", file=sys.stderr)
        return 1
    if identity.get("status") != "ACTIVE":
        print(f"오류: 비활성 상태(status={identity.get('status')})인 사용자에는 계정을 만들 수 없습니다", file=sys.stderr)
        return 1

    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        existing = store.user_by_id(conn, args.user_id)
    if existing is not None:
        print(f"오류: 이미 인증 계정이 존재합니다: {args.user_id}", file=sys.stderr)
        return 1

    password = getpass.getpass("비밀번호 입력(화면에 표시되지 않음): ")
    confirm = getpass.getpass("비밀번호 확인: ")
    if password != confirm:
        print("오류: 비밀번호가 일치하지 않습니다", file=sys.stderr)
        return 1
    if len(password) < 12:
        # 세부 정책값은 Decision Required(비밀번호 정책, Sprint8 Commit8-1 §24) —
        # 여기서는 명백히 취약한 값만 최소 차단선으로 둔다.
        print("오류: 비밀번호는 최소 12자 이상이어야 합니다", file=sys.stderr)
        return 1

    auth_service.create_user(
        data_dir,
        user_id=args.user_id,
        login_id=args.login_id,
        password=password,
        display_name=identity.get("name"),
        role_id=identity.get("roleId"),
        created_by="bootstrap_admin.py",
    )
    print(f"완료: {args.login_id} 계정이 생성되었습니다(연계 사용자: {args.user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
