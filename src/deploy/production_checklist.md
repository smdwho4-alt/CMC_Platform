# CSHSP 운영 전 점검표 (Production Checklist)

> 최초 작성: Sprint H(로컬 JSON 중심 시제품 기준). **Sprint 7 Commit7-4(2026-07-29)에서 Sprint2~6(Google Sheets SSOT, Admin Portal, FastAPI 예약 승인/Slot/Policy, Legacy Guard) 반영해 현행화.**
> 대상: 파일럿/운영 개시 전 검진센터 담당자·전산 담당자가 함께 체크. 내부 검토용.
> 범례: `□` 미확인 · `✅` 확인 · `⚠` 제한사항 있음(운영 가능하나 위험 인지 필요) · `⛔` 운영 차단(해결 전 배포 금지)

---

## ① Git 및 소스

- [ ] □ 공식 Baseline Commit 확인(현재 기준: `73cb25a` — Sprint7 Commit7-3, PM 승인 시점 문서 참조)
- [ ] □ `git status --short` 실행 — 미커밋 변경사항이 배포 대상에 의도치 않게 포함되지 않았는지 확인
- [ ] □ 미커밋 파일 존재 시 사유 확인(문서 초안 등 의도된 것인지, 실수로 남은 코드 변경은 아닌지)
- [ ] ⛔ **Push 승인 여부 확인** — PM이 명시적으로 승인한 시점에만 `git push`(ADR-012). 이 항목이 미확인이면 배포 진행 금지
- [ ] □ 해당 Sprint의 Release Note/Closeout Report 확인(예: `Sprint6_Closeout_Report_v1.0.md`) — 무엇이 바뀌었는지 파악 없이 배포하지 않는다

## ② Backend / FastAPI

- [ ] □ API 서버 기동 확인: `python -m uvicorn src.api.api_server:app --host 127.0.0.1 --port 8600`(`process_manager.md` 참조)
- [ ] □ Health Check: `GET http://127.0.0.1:8600/api/admin-portal/health` — Sheets 연동 상태(`connected`/`not_configured`/`error`) 확인
- [ ] □ 환경변수 확인(상세는 ⑤ 참조) — 특히 `CSHSP_GAS_WEBAPP_URL`(FastAPI가 Sheets에 접근하기 위한 필수값, 미설정 시 승인/거절 API가 503 반환)
- [ ] □ 오류 Contract 확인 — 승인/거절 API가 `{code, message}` 형식으로 응답하는지(`RESERVATION_POLICY_BLOCKED`/`SLOT_FULL` 등, 상세는 `Sprint5_Portal_Integration_Implementation_Plan_v1.0.md` §2 참조)
- [ ] □ Regression PASS 확인 — 최소 아래 스위트 재실행:
  - `tests/run_sprint4_commit2_approval_qa.py`(승인/거절 기초)
  - `tests/run_sprint4_commit3_slot_integration_qa.py` / `run_sprint4_commit3a_slot_hardening_qa.py`(Slot)
  - `tests/run_sprint4_commit5_1_validation_context_program_mapping_qa.py` / `run_sprint4_commit5_2_approval_pipeline_policy_integration_qa.py`(Policy)
  - `tests/run_sprint_b_tests.py`(예약 엔진 기초)
  - Node: `tests/run_sprint5_commit5_3_1_portal_error_parser_qa.js`(Portal Error Contract), `tests/run_sprint6_commit6_1_legacy_approval_guard_qa.js`(Legacy Guard)
  - 2026-07-29 시점 최종 확인 결과는 각 Commit 완료 보고 참조(예: `Sprint6_Closeout_Report_v1.0.md` §1)

## ③ Admin Portal

- [ ] □ 접속 확인(`app/pages/admin_portal_new.html`, 정적 서버 경유)
- [ ] □ X-User-Id 입력 후 예약 목록 조회 정상(⚠ 실 로그인이 아닌 Mock 인증 — §⑦ 참조)
- [ ] □ 승인 버튼 동작(정상 시 200, Slot/Policy 위반 시 409 `RESERVATION_POLICY_BLOCKED` 또는 기존 `SLOT_*` 코드)
- [ ] □ 거절 버튼 동작(사유 입력 Dialog 정상, 422 검증 정상)
- [ ] □ 오류 메시지가 `parseApiError()` 경유로 정상 표시되는지(Commit5-3.2) — 특히 `RESERVATION_POLICY_BLOCKED`가 "다른 사용자가 이미 처리했거나..."로 오도 표시되지 않는지(과거 결함, Sprint5에서 수정됨)
- [ ] □ Timeout 처리 확인(8초 AbortController, Commit5-3.2) — 네트워크 지연 시뮬레이션으로 "요청 시간이 초과되었습니다" 안내 확인

## ④ Legacy Portal

- [ ] ✅ **예약확정 차단 확인**(Sprint6 Commit6-1) — `admin_reservations_v2_new.html`에서 상태를 "예약확정"으로 선택 후 저장 시도 → 차단되고 "Admin Portal의 승인 버튼을 이용해 주세요" 안내가 표시되는지 확인. **단, 이 가드는 클라이언트측(브라우저 JS)에만 존재** — GAS Web App을 직접 호출하면 우회 가능(`Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1 참조)
- [ ] ⚠ **예약변경** — 현재 상태 라벨만 "일정변경"으로 바뀌며 **실제 희망일시는 변경되지 않는다**(코드로 확인된 사실, `Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1). 운영자에게 이 제한사항을 반드시 공지
- [ ] ⚠ **예약취소** — 정상 동작하나 **Slot이 반환되지 않는다**(코드로 확인, 동일 문서 §5-1) — 취소가 누적되면 Slot 정원이 실제보다 좁게 표시될 수 있음. 취소 발생 시 별도로 Slot 데이터 수동 확인 권장
- [ ] □ **검진완료** — 정상 동작(GAS `_actionUpdateStatus`가 `검진종료` 컬럼에 자동 타임스탬프 기록)
- [ ] ⚠ **현재 잔여 쓰기 기능 확인** — 조회/CSV 다운로드/메모(`특이사항`) 편집은 계속 정상 제공(위험 없음, 감사 대상 아니었던 것과 동일 이유)
- [ ] ⛔ **Legacy Stage3 Phase B 미완료 경고** — 예약변경/취소/검진완료 3개 전이는 FastAPI 검증·권한 검사·감사 로그가 전무한 상태(`Operation_Readiness_Assessment_v1.0.md` §3-1). Phase B(B-1~B-6) 완료 전까지 이 상태가 지속됨을 운영진이 인지해야 함

## ⑤ Google Sheets / Apps Script

- [ ] □ Sheets 연결 확인: `GET /api/admin-portal/health` 또는 GAS `?action=ping` 응답이 `ok:true`
- [ ] □ 시트명(`종합검진_예약대장`) 및 컬럼 수(29컬럼, `COL` 정의) 실제 시트와 일치 확인
- [ ] □ Apps Script 배포 버전이 최신인지 확인 — 재배포 시 반드시 **"새 버전"** 선택("기존 버전 재사용" 시 STEP1.5 DateFix 미반영 사고가 재발한 전례 있음, `PROJECT_STATUS.md` §2 참조)
- [ ] □ 읽기(`action=list/get`)·쓰기(`action=updateStatus/update`) 각각 정상 확인
- [ ] ⛔ **GAS 직접 호출 보안 위험 표시** — Apps Script Web App의 `doGet`/`doPost`는 **호출자 인증·인가를 전혀 수행하지 않는다**(코드로 확인). Web App URL을 아는 누구나 예약 데이터를 조회·수정할 수 있다. 배포 시 "액세스 권한"을 **"조직 내"** 또는 **"나만"**으로 설정하고 URL 노출을 엄격히 관리할 것(`google_sheets_service_v2_new.js` 기존 보안 주석 및 `Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1에서도 확인된 사실)
- [ ] ⛔ **실제 운영 Web App URL/Spreadsheet ID를 이 체크리스트나 어떤 문서에도 기록하지 않는다** — 서버 환경변수(`CSHSP_GAS_WEBAPP_URL`)로만 관리

## ⑥ Slot / Policy

- [ ] □ Slot 상태(`AVAILABLE`/`FULL`/`BLOCKED`/`HOLD`/`WAITING`) 데이터 정상 여부(`slot_generator`로 생성된 기간 확인)
- [ ] □ 예약정원(capacity/reservedCount) 실제 운영 규모에 맞게 설정
- [ ] □ 공휴일/휴진일(`schedules.json`, type=HOLIDAY) 연간 등록
- [ ] □ 운영시간(`OPERATING_START`/`OPERATING_END`, 현재 08:00~17:00 하드코딩) 실제 병원 운영시간과 일치 확인
- [ ] □ 의료진(`doctors.json`)·간호사(`nurses.json`) 근무일(workDays) 최신 상태 반영
- [ ] □ 검사실(`rooms.json`)·장비(`equipment.json`) 상태(ACTIVE/MAINTENANCE) 최신 반영
- [ ] □ 프로그램 제한(Slot.programRestriction) 설정 여부 확인(현재 기본값 전부 `null` — 제한 없음)
- [ ] □ 프로그램 매핑(`resolve_program()`) 정상 — 특히 "온김에검진"처럼 `Program.code`가 아닌 `Program.name`으로만 일치하는 항목이 422로 오차단되지 않는지 확인(Sprint4 Commit5-1에서 해결됨, 회귀 여부만 재확인)

## ⑦ 보안

- [ ] □ 관리자 권한(`roles.json` 5개 역할: DIRECTOR/ADMIN/STAFF/CRM/AI-AGENT) 실제 운영 인력 구성과 일치 확인
- [ ] □ 역할별 실제 Enforcement 확인(Admin Portal 경유 승인/거절만 — Legacy 경유 3개 전이는 권한 검사 없음, §④ 참조)
- [ ] □ 운영 계정(`users.json`) 실계정으로 교체, QA 더미 계정(USR-0001~0003) 비활성 여부 결정
- [ ] ⛔ **관리자 실인증 미구현** — 현재 `X-User-Id` 헤더만으로 인증하는 Mock 방식(운영 전 필수 항목으로 계속 등록됨, `ARCHITECTURE.md` §6). 내부망 신뢰에만 의존하므로 외부 노출 금지
- [ ] □ 개인정보 노출 확인 — Admin Portal 목록·API 응답에서 이름/연락처/생년월일 마스킹 적용 여부(`pii_mask.py`)
- [ ] ⚠ 로그 — 구조화된 로깅 프레임워크 없음(`print`/`stderr`만, Commit5-2의 `_server_log()`). 장애 추적 시 이 점 인지 필요
- [ ] □ 브라우저 저장 데이터 확인 — `localStorage`에 남는 값(`config_v2_new.js` 설정 등) 중 민감정보 없는지 확인

## ⑧ Backup / Restore

- [ ] □ 로컬 JSON 백업(`data/`) 스케줄 등록 확인(`backup_policy.md` §1)
- [ ] □ 1회 수동 백업/복구 리허설 실행 및 결과 확인(`tests/run_backup_restore_rehearsal.py`)
- [ ] ⚠ **Google Sheets 백업은 별도 정책 미비** — 로컬 JSON 백업 정책만 존재, Sheets는 Google 자체 버전 기록에 암묵적으로만 의존 중(`backup_policy.md` §5 Decision Required 참조)
- [ ] □ 복구 파일 위치 및 접근 권한 확인(백업 드라이브 암호화·접근 제한)
- [ ] □ 복구 책임자 지정 여부(현재 미확정 — `CSHSP_Failure_Response_Manual.md` §3 연락망 참조)
- [ ] □ 복구 후 정합성 확인 절차 숙지(`python src/core/data_validator.py`, 오류 0건 확인)

## ⑨ Release / Rollback

- [ ] ⛔ 배포 승인 — PM 명시적 승인 없이 Push/Deploy 금지(핵심 원칙 전체 Sprint 공통)
- [ ] □ Netlify 상태 확인(정적 파일 배포, `DEPLOY_GUIDE_new.md` §4 참조)
- [ ] □ GAS 상태 확인(배포 버전, §⑤ 참조)
- [ ] ⛔ **Rollback 기준 및 절차 문서 미비** — 독립된 Rollback Guide가 아직 없음(Sprint7 Commit7-5 예정, `Operation_Readiness_Assessment_v1.0.md` Gap #5). 현재는 Git 커밋 되돌리기(코드)만 가능하고, GAS 버전 롤백·Sheets 데이터 롤백 절차는 미문서화 상태임을 인지
- [ ] □ 비상 연락 체계 확인(`CSHSP_Failure_Response_Manual.md` §3, 담당자 미기입 상태 — 운영 착수 전 반드시 실제 인력으로 채울 것)

---

## 개시 후 일일 점검(파일럿/운영 기간, 기존 유지)

- [ ] 아침: Health Check 확인, Admin Portal 승인 대기함 확인
- [ ] 저녁: 백업 성공 확인, Legacy Portal을 통한 예약변경/취소/검진완료 처리 건수 확인(⚠ 감사 로그가 없으므로 Sheets를 직접 확인해야 함, §④)
- [ ] 주간: Slot 정원 실측 대비 실제 예약 건수 대조(취소 시 Slot 미반환 누적 여부 점검, §④)

---

## 참고 문서

- 프로세스 관리: `process_manager.md`
- 백업 정책: `backup_policy.md`
- 장애 대응: `docs/CSHSP_Failure_Response_Manual.md`
- 배포 절차: `docs/DEPLOY_GUIDE_new.md`
- Portal Error Contract: `Sprint5_Portal_Integration_Implementation_Plan_v1.0.md`
- Legacy 제한사항 상세: `Legacy_Stage3_PhaseB_Design_v1.0.md`
- 운영 준비도 종합 평가: `Operation_Readiness_Assessment_v1.0.md`
