# CSHSP 전체 상태 점검 보고서 (2026-07-12)

> v1.0.0-pilot 태그 생성 전 전체 점검 결과. 작성: Claude (세션 점검), 근거: git 이력 + PROJECT_STATUS.md + DEV-003 테스트 재실행.

---

## 1. Git 상태

| 항목 | 상태 |
|---|---|
| HEAD | `3288382` feat(DEV-003) — 보고된 커밋과 일치 ✅ |
| 브랜치 | main, **origin보다 1커밋 앞섬 (DEV-003 커밋 미push)** 🟡 |
| 태그 | **없음** (v0.9.0-pilot 태그도 미생성) 🟡 |
| 작업트리 | **비클린 — 커밋되지 않은 변경 존재** 🔴 (아래 §1-1) |

### 1-1. 커밋되지 않은 변경 (🔴 태그 생성 전 반드시 정리 필요)

세 그룹으로 나뉜다.

**(A) `app/data/` 3개 파일 — git 인덱스에서 삭제 스테이징됨**
- 대상: `programs_config_new.json`, `programs_data_new.js`, `sample_data_new.js`
- 디스크에는 파일이 그대로 존재. git 추적에서만 빠지는 상태 (`git rm --cached` 형태). `.gitignore`의 `data/` 규칙이 `app/data/`에도 매칭되어 untracked로도 표시되지 않음.
- **위험**: 이 파일들은 `cc5803f` (Critical HotFix — "404 파일 추가")에서 배포 404 오류를 고치려고 **의도적으로 커밋된 파일**이다. `reservation_v2_new.html:153-154` 등 활성 페이지가 `<script src>`로 직접 로드한다. 이 삭제를 커밋하고 push하면 **Netlify 배포에서 404 재발** 가능성이 높다.
- 추정: `.gitignore`의 `data/`(PII 차단용) 규칙과 `app/data/`(프로그램 정적 데이터) 가 충돌하는 상황에서 누군가/어느 세션이 정리하다 만 흔적으로 보임. 의도 불명.

**(B) `app/services/dashboard_sheets_service_new.js` — 미스테이징 수정 (112줄)**
- 워킹트리 버전은 **어느 커밋과도 일치하지 않는 제3의 버전**.
- 이력 분석: HotFix#1(`b5bb240`)이 이 파일에 "날짜 필터 제거" 수정을 넣었으나, 이후 `cc5803f`(FUSE 파일 잘림 복구)가 이 파일을 **HotFix#1 이전 내용으로 되돌려 커밋**했다 (65682ac 버전과 blob 동일 확인). 즉 **현재 HEAD에는 HotFix#1의 'Dashboard 전체 0 표시' 수정이 빠져 있을 가능성**이 있다.
- 워킹트리 버전에는 HotFix#1 주석("HotFix#1: 날짜 필터 제거")과 해당 로직이 포함되어 있음 → **워킹트리 쪽이 정본일 가능성이 높다.**
- 검증: 현재 워킹트리 상태에서 DEV-003 테스트 3종 재실행 → **60/60 PASS** (2026-07-12 본 세션 확인).

**(C) 나머지 6개 파일 (config_new.js, 대시보드/예약 html 5종) — MM 상태**
- staged 변경과 unstaged 변경이 상쇄되어 **HEAD 대비 순변경 0** (LF/CRLF 왕복만). 실질 위험 없음. `git restore --staged` 후 `git restore`로 정리하면 됨.

### 1-2. 정리 방안 (사용자 승인 필요)

| 그룹 | 권고 |
|---|---|
| (A) app/data 삭제 스테이징 | **취소 권고** (`git restore --staged app/data/`) — 배포 404 재발 방지. 삭제가 의도된 것이었다면 사유 확인 후 진행 |
| (B) 서비스 파일 | **커밋 권고** — HotFix#1 회귀 복구로 보이며 테스트 60/60 PASS. 단, 커밋 전 diff 최종 검토 |
| (C) CRLF 왕복 6종 | staged+unstaged 모두 원복 (순변경 0이므로 안전) |

---

## 2. Pilot Ready 체크리스트

| # | 항목 | 상태 | 담당 |
|---|---|---|---|
| 1 | STEP1.5 DateFix 코드 수정 | ✅ 완료 (회귀 150건 PASS) | — |
| 2 | **GAS 재배포 ("새 버전")** — DateFix + DEV-003 Lock 반영 | ✅ 완료로 보고됨 (Version 5 재배포, 사용자 확인) — 단 PROJECT_STATUS.md에는 아직 🔴 미반영으로 기재되어 있어 **문서 갱신 필요** | 문서: Claude |
| 3 | DEV-003 구현+검증 (60/60, 응답 1.765초) | ✅ 완료 | — |
| 4 | Live 모드 응답시간 실측 (NFR 3초) | ✅ 1.765초로 충족 확인됨 | — |
| 5 | `reservation_v2_new.html` 실브라우저 QA | 🔲 미완 (Follow-up #1) | Claude+사용자 |
| 6 | LockService 실동시성(503) 검증 | 🔲 미완 (Follow-up #2) | Claude+사용자 |
| 7 | `CMC_CONFIG.load()` 모드전환 롤백 | 🔲 별도 세션 진행 중 (task_a8cf5790) | 별도 세션 |
| 8 | Git 작업트리 정리 (§1-1) | 🔴 **신규 발견** | 사용자 승인 → Claude |
| 9 | QA 더미 데이터 정리 (Date 손상 셀 포함) | 🔲 파일럿 1주차 허용 (기존 결정) | 사용자 |

## 3. Release Checklist (v1.0.0-pilot 태그 전)

1. 🔴 작업트리 클린 상태 확보 (§1-2 승인 후 처리) — **태그의 전제조건**
2. 🔲 DEV-003 커밋(3288382) origin push — 현재 로컬에만 존재, 유실 위험
3. 🔲 CHANGELOG.md 갱신 (현재 v0.9.0까지만 기재)
4. 🔲 PROJECT_STATUS.md 갱신 (GAS 재배포 완료·DEV-003 검증 완료 반영, Known Issue 상태 변경)
5. 🔲 RELEASE_NOTES_v1.0.0-pilot 작성 (v0.9.0 노트 형식 재사용)
6. 🔲 `git tag v1.0.0-pilot` 생성 + push

## 4. 남은 위험요소

| 위험 | 수준 | 비고 |
|---|---|---|
| 작업트리 미정리 상태에서 태그/커밋 진행 | 🔴 높음 | app/data 삭제가 커밋되면 배포 404 재발 |
| HEAD의 dashboard 서비스 파일이 HotFix#1 이전 버전 | 🟡 중간 | 워킹트리 정본 커밋으로 해소 가능 |
| DEV-003 커밋 미push (백업 없음) | 🟡 중간 | 로컬 디스크 유실 시 복구 불가 |
| 실브라우저 QA 미완 (reservation_v2) | 🟡 중간 | 파일 무수정이라 회귀 위험은 낮음 |
| LockService 실동시성 미검증 | 🟡 중간 | 파일럿 중 동시 접속 낮으면 영향 제한적 |
| 관리자 인증·HTTPS 미적용 | 🟡 기존 인지 | 운영(정식) 전환 전 필수, 파일럿 허용 여부 기존 결정 유지 |
| 더미 데이터/계정 잔존 | 🟢 낮음 | 파일럿 1주차 정리 예정 |

## 5. 다음 우선순위 (권고)

1. **§1-2 정리 방안 승인** → 작업트리 클린화 (+ 서비스 파일 커밋)
2. DEV-003 커밋 + 서비스 파일 커밋 **origin push**
3. PROJECT_STATUS.md / CHANGELOG.md 갱신
4. RELEASE_NOTES_v1.0.0-pilot 작성 → **v1.0.0-pilot 태그 생성·push**
5. Follow-up: reservation_v2 실브라우저 QA → LockService 동시성 검증
