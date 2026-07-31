# Sprint8 Commit8-2 — 관리자 인증·인가 최소 구현 결과 문서

> 작성: Sprint8 Commit8-2(2026-08-01) — 신규 독립 문서.
> 기준선: `7fee874f99a26c6040c4a9ade77acb5bd0c30908`("docs: design sprint8 admin authentication and threat model")
> 이 문서는 실제 구현된 내용, 운영 안내, Rollback 절차, 잔여 위험을 통합한다. 실제 Secret·계정·URL·개인정보는 기록하지 않는다.

---

## 1. 구현 개요

Sprint8 Commit8-1 설계와 PM 승인사항(대안 A: FastAPI 중심 인증, 서버 관리형 SQLite 세션, HttpOnly/Secure/SameSite=Lax 쿠키, CSRF, 로그인 실패 제한, X-User-Id Mock 환경 격리)을 실제 코드로 구현했다. 관리자 실 인증이 처음으로 도입되며, 기존 `roles.json` 기반 인가(`has_perm`/`need_perm`)는 그대로 재사용한다.

## 2. 신규 구성요소

| 파일 | 역할 |
|---|---|
| `src/auth/auth_store.py` | SQLite 스키마·CRUD(`auth_users`/`auth_sessions`/`auth_audit_log`) |
| `src/auth/auth_service.py` | Argon2id 해시·검증, 로그인/세션 생성·검증·만료, 실패 제한·계정 잠금 |
| `src/auth/csrf.py` | CSRF Token 대조(상수시간 비교) |
| `src/auth/routes_auth.py` | `/api/auth/login`·`/logout`·`/me`, 세션 우선 인증 Depends, CSRF Depends, Mock 환경 게이트 |
| `src/auth/service_hmac.py` | FastAPI-GAS 서비스 인증 HMAC 서명 유틸리티(설계·로컬 테스트만, GAS 미배선) |
| `src/auth/bootstrap_admin.py` | 운영 계정 생성 CLI(비대화형 자동 생성 없음) |
| `app/pages/admin_login_new.html` | 관리자 로그인 화면(신규) |

## 3. 수정된 기존 파일

| 파일 | 변경 내용 |
|---|---|
| `src/api/api_server.py` | `require_user`를 세션 우선 인증으로 교체(내부 구현만, 호출부 `Depends(require_user)` 전부 무변경), CORS `allow_credentials=True` 추가, `/api/auth/*` 라우터 등록, `app.state.cshsp_data_dir` 추가 |
| `src/api/routes_admin_portal.py` | `_build_require_user()`가 세션 우선 인증에 위임, 승인/거절/상담상태변경 엔드포인트에 CSRF Depends 추가 |
| `app/pages/admin_portal_new.html` | 페이지 진입 시 세션 확인(`requireSession()`) 및 미인증 시 로그인 화면 리다이렉트, 로그아웃 버튼, 모든 fetch에 `credentials:'include'` 추가, 상태변경 요청에 `X-CSRF-Token` 헤더 추가, 401 응답 시 재로그인 유도로 변경 |
| `requirements.txt` | `argon2-cffi` 추가 |

## 4. 사용자 계정 저장소 설계 근거

신원(표시이름/역할/계정활성상태)의 SSOT는 여전히 `data/users.json`이다(`roles.json`이 역할·권한 정의 전용으로 남는 것과 동일한 관계). `auth_users` 테이블은 **인증 전용**(로그인ID/비밀번호 해시/잠금상태)이며 `id` 컬럼으로 `users.json`의 실제 사용자 id를 참조한다. 세션 검증 시 SQLite 상태와 `users.json` 상태(`status=="ACTIVE"`)를 모두 확인한다(이중 방어).

## 5. SQLite 초기화·백업·복구 안내

- **위치**: `<data_dir>/auth.db`(기존 `CSHSP_DATA_DIR` 규칙 그대로 재사용, 이미 `.gitignore`로 전체 제외되는 `data/` 하위라 별도 조치 불필요)
- **초기화**: 첫 접근 시 `init_schema()`가 자동으로 `CREATE TABLE IF NOT EXISTS`(idempotent) — 기존 DB 손상 없음
- **백업**: 로컬 JSON 백업 정책(`src/deploy/backup_policy.md`)에 `auth.db`가 아직 포함되지 않았다 — **[운영 전 필요조치]**: 백업 스냅샷 대상에 `<data_dir>/auth.db`를 추가해야 함(Decision Required, §11)
- **복구**: 스냅샷에서 `auth.db` 파일 자체를 복사(SQLite 단일 파일이라 별도 절차 불필요), WAL 모드이므로 `-wal`/`-shm` 보조 파일도 함께 백업 대상에 포함해야 함

## 6. 테스트 계정 생성 방법(운영)

`src/auth/bootstrap_admin.py`를 사용한다(비대화형 자동 생성 없음, 기본 계정·기본 비밀번호 없음).

```bash
python src/auth/bootstrap_admin.py --data-dir <data_dir> --user-id USR-XXXX --login-id <신규 로그인ID>
```

`--user-id`는 반드시 기존 `data/users.json`에 이미 존재하는 사용자 id와 일치해야 한다. 비밀번호는 대화형 프롬프트(`getpass`)로만 입력하며 화면에 표시되지 않고 인자로 전달되지 않는다. 실제 운영 계정 생성은 이번 Commit에서 수행하지 않았다 — DR8-2-01(계정 생성 승인 주체) 결정 이후 별도로 진행한다.

## 7. Session·Cookie 정책(구현값)

| 항목 | 값 | 근거 |
|---|---|---|
| 유휴시간 | 30분 | PM 승인사항 |
| 절대 유효시간 | 8시간 | PM 승인사항 |
| 사용자당 최대 동시 세션 | 2개(3번째 로그인 시 가장 오래된 세션 자동 폐기) | PM 승인사항 |
| Cookie 속성 | HttpOnly, Secure(운영/Staging 기본 True, `CSHSP_COOKIE_INSECURE_DEV=1` 명시 시에만 로컬 HTTP 개발 예외), SameSite=Lax | PM 승인사항 |
| 세션 저장소 | SQLite(`auth_sessions` 테이블) | PM 승인사항(JSON 파일·메모리 세션 금지) |
| 재인증 조건 | 계정정보 변경/역할·권한 변경/계정 비활성화 시 `security_stamp` 갱신 → 기존 세션 자동 무효화 | PM 승인사항 |

## 8. CSRF 적용 범위

세션 Cookie로 인증된 상태변경 요청에만 적용한다(승인/거절/상담 상태변경, `routes_admin_portal.py`). **X-User-Id Mock 경로는 CSRF 대상이 아니다** — CSRF는 브라우저가 자동으로 실어 보내는 Cookie(ambient authority)를 노리는 공격이라 헤더 기반 인증에는 성립하지 않으며, Mock 자체가 이미 별도 환경 게이트로 제한되어 있다(이 판단은 회귀 테스트 중 실제로 발견·수정된 사항이며 §16에 기록).

Sprint7/8에서 이미 확인된 구버전 로컬 JSON 예약 API(`/api/reservations/{rid}/approve` 등, `api_server.py`)는 어떤 Portal UI도 호출하지 않는 미사용 경로이므로(Commit8-0/8-1 CF-01) 이번 Commit에서 CSRF를 추가하지 않았다 — 처리 방향은 D28(Commit8-0)로 이월된 상태 그대로다.

## 9. X-User-Id Mock 격리 정책(구현값)

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `CSHSP_ENV` | 미설정 시 `development`로 간주 | `production`이면 Mock 완전 차단(다른 조건 무관) |
| `CSHSP_ALLOW_MOCK_AUTH` | 미설정(빈 값, 즉 차단) | `1`/`true`/`yes`일 때만, 그리고 `CSHSP_ENV != production`일 때만 Mock 허용 |
| `CSHSP_COOKIE_INSECURE_DEV` | 미설정(빈 값, 즉 Secure=True 유지) | `1`일 때만 로컬 HTTP 개발 환경에서 Cookie Secure 속성 예외 |

두 조건(`CSHSP_ENV != production` AND `CSHSP_ALLOW_MOCK_AUTH` 명시적 설정) 중 하나라도 충족되지 않으면 Mock은 차단되고 `MOCK_AUTH_BLOCKED` 감사 이벤트가 기록된다. 운영 인증(세션) 자체가 장애를 겪어도 Mock으로 자동 전환하지 않는다(코드 상 별도 우회 경로 없음).

**기존 테스트 실행 시**: 테스트 파일 자체는 무수정, 프로세스 환경변수로 `CSHSP_ALLOW_MOCK_AUTH=1 CSHSP_ENV=test`를 지정해 재실행했다(§16 검증 결과 참조).

## 10. 인증 장애 대응 원칙

세션 저장소(SQLite) 또는 인증 로직 자체가 장애를 겪으면, 신규 로그인·세션 검증이 실패해 관리자 작업이 중단된다(보안 우회보다 작업 중단을 기본으로 하는 PM 승인 원칙). Mock으로 전환하는 코드 경로는 존재하지 않는다. 상세 장애 대응 절차(연락망 포함)는 기존 `docs/CSHSP_Failure_Response_Manual.md`/`docs/CSHSP_Rollback_Guide.md`에 인증 관련 시나리오를 추가하는 것을 향후 과제로 남긴다(이번 Commit에서 그 문서들은 수정하지 않음 — 대상 외 문서).

## 11. Rollback 절차

| 대상 | 절차 |
|---|---|
| DB 파일 | `auth.db`는 신규 생성물이므로 파일 삭제만으로 이전 상태(무DB, Mock 없음, 즉 전체 차단) 복귀 가능. 삭제 전 백업 권장 |
| Schema Migration | 별도 Migration 도구 없음(`CREATE TABLE IF NOT EXISTS`), Rollback은 파일 삭제와 동일 |
| API 코드 | 이 Commit을 `git revert`로 되돌림(코드 Rollback 시에도 Mock 재활성화 아님 — PM 승인사항, `docs/CSHSP_Rollback_Guide.md` §6의 `git revert` 권장 원칙과 일치) |
| 관리자 화면 | `admin_portal_new.html`/`admin_login_new.html`도 동일 Commit 단위 `git revert` |
| 환경변수 | `CSHSP_ALLOW_MOCK_AUTH`/`CSHSP_ENV`/`CSHSP_COOKIE_INSECURE_DEV`는 배포 환경에만 존재(코드 기본값은 전부 안전측) — Rollback 시 별도 조치 불필요 |
| Mock 격리 설정 Rollback | 수행하지 않음(§10 원칙) |
| 세션 전체 폐기 | `auth_service.revoke_all_sessions(data_dir, user_id=..., reason=...)` 호출 또는 `auth.db` 삭제(전체 세션 소실) |

## 12. Decision Required(신규, 통합)

| ID | 결정사항 | 현재상태 | 권장안 | 결정주체 |
|---|---|---|---|---|
| DR8-2-01 | 실제 운영 계정 생성 승인 절차 | 미확정 | `bootstrap_admin.py` + 병원 전산담당 확인 | PM/병원 |
| DR8-2-02 | `auth.db` 백업 정책 편입 | 미확정 | `backup_policy.md`에 대상 추가(향후 별도 Commit) | PM |
| DR8-2-03 | 비밀번호 최소 정책 세부값(길이 12자만 임시 하한, 복잡도/만료 등 미정) | 임시값만 존재 | 병원 보안정책 있으면 그것을 따름 | 병원/PM |
| DR8-2-04 | 구버전 로컬 JSON 예약 API(`/api/reservations/*`) CSRF 미적용 상태 유지 여부 | Commit8-0 D28 승계, 미결 | 미사용 경로이므로 현행 유지 | PM |
| DR8-2-05 | FastAPI-GAS HMAC 서버 측 배선·GAS 측 검증 구현 시점 | 미착수(Commit8-3 대상) | Commit8-3에서 진행 | PM |

## 13. 잔여 위험

- **GAS 직접호출 위험 잔존**: 이번 Commit은 관리자 브라우저-FastAPI 구간만 다뤘다. FastAPI-GAS 서버간 인증(HMAC)은 유틸리티만 구현했고 실제 배선·GAS 배포는 하지 않았다 — Threat T14(Commit8-1)는 그대로 남아 있다.
- **Legacy/Reservation Portal 직접호출 위험 잔존**: 이번 Commit 범위 밖(PM 승인사항 §14), 별도 Sprint 대상.
- **비밀번호 정책 미완성**: 최소 12자 하한만 구현, 복잡도·만료·이력 재사용 금지 등은 미구현.
- **운영 계정 미생성**: 이번 Commit에서 실제 운영 계정을 만들지 않았으므로, 이 기능이 실제로 사용되려면 별도 Bootstrap 절차가 필요하다.
- **Rate Limit과 로그인 실패 제한의 관계**: 기존 `rate_limit.py`(AI 채팅용)와 신규 로그인 실패 제한은 별도 메커니즘이다 — 통합 여부는 검토하지 않았다.

## 14. 후속 Sprint 대상

- Commit8-3: FastAPI-GAS 서비스 인증(HMAC) 실제 배선 및 GAS 측 검증 코드 설계·배포 검토
- Commit8-4 이후: Legacy 상태전이 서버 검증(Sprint8 Security Plan §33 그대로 승계)
- `auth.db` 백업 정책 반영(별도 Commit, `backup_policy.md` 대상 외 수정 방지 원칙 준수)
- Rollback Guide/Failure Response Manual에 인증 장애 시나리오 추가(별도 Commit)

## 15. Business Rule / 운영환경 변경 여부

없음. 예약변경이 실제 일정·시간·프로그램 변경이 아니라 상태 라벨 변경 수준이라는 기존 확인사실을 그대로 유지했다(이번 Commit은 인증·인가만 다루며 예약 도메인 로직을 변경하지 않았다).

## 16. 검증 결과 요약

- **신규 테스트**: `tests/run_sprint8_commit8_2_admin_authentication_qa.py`, 62개 항목(A~J 범주) 전부 PASS(`tests/sprint8_commit8_2_admin_authentication_test_result.csv`).
- **회귀 테스트**: 기존 Python 테스트 스위트 전체를 `CSHSP_ALLOW_MOCK_AUTH=1 CSHSP_ENV=test` 프로세스 환경변수로 재실행(테스트 파일 자체는 로직 무수정 원칙 준수, 단 아래 §17 예외 5건은 "무수정 self-check"가 구조적으로 낡아 설명 주석과 함께 갱신함). JS 기반 테스트(Portal Error Parser 58/58, Legacy Approval Guard 24/24, TD Cleanup 12/12)도 재실행, 전부 PASS.
- **발견 및 수정한 버그**: CSRF가 Mock 인증 경로에도 잘못 적용되어 기존 승인/거절/상담상태변경 테스트가 실패했던 것을 발견 → §8 원칙에 따라 세션 인증에만 CSRF를 적용하도록 수정 → 전체 재확인 PASS.
- **사전 확인된 무관 실패**: `run_sprint_g_tests.py`(questionnaires/start 응답 스키마 이슈), `run_sprint_h_tests.py`(체크리스트 필수 항목 검사), `run_sprint_i_quality_gate.py`(Windows cp949 콘솔 인코딩 크래시) — **이번 Commit 이전 커밋(`7fee874`) 기준 별도 worktree에서 동일하게 재현되어 사전 결함임을 확인**, 신규 회귀 아님. 이 3개 파일과 이를 집계하는 `sprint1/2/3_full_regression_summary.py`는 수정하지 않았다(대상 외).

## 17. 기존 테스트 파일 수정 내역(무수정 self-check 낡음, 설명 주석 포함 갱신)

Sprint8 Commit8-2가 `src/api/api_server.py`/`src/api/routes_admin_portal.py`를 정당하게(PM 승인) 수정함에 따라, 과거 특정 Commit이 "자기 자신의 범위가 백엔드 .py 파일을 건드리지 않았는지"를 실시간 `git diff`로 스스로 검사하던 낡은 self-check들이 구조적으로 더는 유효하지 않게 됐다. 아래 5개 파일에서 해당 self-check만 제거하고 설명 주석을 남겼다(다른 실제 동작 검증 assertion은 전부 그대로 유지):

- `tests/run_sprint4_commit2_approval_qa.py`
- `tests/run_sprint4_commit3_slot_integration_qa.py`
- `tests/run_sprint4_commit3a_slot_hardening_qa.py`
- `tests/run_sprint3_ai_support_qa.py`
- `tests/run_sprint3_audit_qa.py`
- `tests/run_sprint3_ux_qa.py`(추가로, `admin_portal_new.html`의 사용자 배지 갱신 로직이 `requireSession()`이라는 공용 함수로 리팩터링됨에 따라 "리터럴 호출 횟수 ≥2" 검사도 동일 의미의 새 검사로 갱신)

## 18. 보호 대상 파일 관련 특기사항

테스트 회귀 재실행 중 `run_sprint3_rbac_qa.py`를 무심코 함께 실행해 보호 대상 파일 `tests/sprint3_rbac_test_result.csv`의 스냅숏이 재생성되는 부작용이 있었다. 재생성된 내용을 `git diff`로 직접 대조한 결과, 변경 내용은 이 세션 전체에서 이미 여러 차례 문서화된 기존 사실(TD-S5-05, "6→10, 코드 기능 확장에 따른 정상 누적, 결함 아님")과 **완전히 동일**했다 — 즉 이번 실행이 새로운 값을 만들어낸 것이 아니라 기존에 이미 존재하던 동일한 미확정 상태를 그대로 재생성한 것이다. 이 파일은 PM 지시에 따라 **Staging·Commit·복원(git restore) 어느 것도 하지 않았으며**, 앞으로도 이 파일을 재생성하는 테스트(`run_sprint3_rbac_qa.py`)는 이 저장소의 회귀 스위트 전체 재실행 대상에서 제외해야 한다는 점을 이 문서에 명시적으로 기록한다.

---

## 완료 조건 준수 확인

이번 Commit에서 Google Sheets 구조, Apps Script, Netlify 설정, 운영 데이터, Legacy 기능, 기존 Portal 기능(승인/거절/조회 로직 자체)을 변경하지 않았다. 실제 운영 계정을 생성하지 않았고, 실제 개인정보를 사용하지 않았다(테스트는 전부 합성 계정 사용). 실제 Secret·GAS URL·Spreadsheet ID를 기록하지 않았다. 보호 대상 파일(`ADR-015_Slot_Status_Policy_Draft.md`, `tests/sprint3_rbac_test_result.csv`)을 수정·삭제·복원·Staging·Commit하지 않았다(§18 특기사항 참조). Push, Netlify/GAS/FastAPI Deploy, Pilot을 수행하지 않았다.
