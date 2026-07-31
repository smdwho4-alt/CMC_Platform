# CSHSP 장애 대응 매뉴얼 (Sprint H, Sprint7 Commit7-4에서 Sheets/Admin Portal/Slot/Policy 반영 갱신)

> 파일럿 기간 검진센터·전산 담당자용. 모든 조치는 시각·조치자·내용을 기록한다. 내부 검토용.
> **Sprint7 Commit7-4 갱신 안내**: §1(A~G)은 Sprint H 시점(예약 원장이 로컬 JSON이던 시기) 작성 내용으로 여전히 유효하며 무수정 보존했다. **§1-2(신설)**에 ADR-013(Sprint4) 이후의 Google Sheets SSOT·Admin Portal·FastAPI 예약 승인/Slot/Policy·Legacy Guard 관련 장애 유형을 추가했다.

## 0. 공통 원칙
- **예약 원장은 이제 Google Sheets다(ADR-013, Sprint4)** — `data/reservations.json`은 더 이상 신규 예약의 원장이 아니며 로컬 사본/Fixture 용도로만 유지된다(§1의 "예약 원장은 data/ JSON 파일"은 Sprint H 시점 기준이었음, 이 문서 갱신 시점 기준으로 정정). `Patient`/`CRM`/`AuditLog` 등 나머지 19개 Entity는 여전히 로컬 JSON이 원장이다.
- 어떤 조치든 data/ 폴더를 먼저 복사(스냅샷)한 뒤 진행. Sheets 관련 조치는 `backup_policy.md` §5 참조(대규모 변경 전 시트 사본 권장).
- AI 채팅은 부가 채널 — 장애 시 전화 접수(041-570-7333)로 즉시 우회 가능.
- **Legacy Portal(예약변경/취소/검진완료)은 감사 로그가 없다** — 장애·오조작 발생 시 Sheets를 직접 열어 확인해야 한다(`Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1).

## 1. 증상별 대응

### A. API 서버 무응답 (admin/채팅 "API 연결 실패")
1. `http://127.0.0.1:8600/api/health` 확인
2. 서비스 재시작: `nssm restart CSHSP-API` (또는 작업 스케줄러 재실행)
3. 로그 확인: `logs\api.err.log` 마지막 50줄
4. 재시작 반복 실패 → 데이터 손상 의심 (B 절차)
5. **우회**: 직원은 전화·수기 접수, 승인 업무는 복구 후 일괄 처리

### B. 데이터 파일 손상 (JSON 파싱 오류, validator 오류)
1. 서비스 중지 → data/ 전체를 `data_broken_일시/`로 보존
2. `python src/core/data_validator.py`로 손상 범위 확인
3. backup_policy.md 복구 절차 수행 (최신 스냅샷 복원 → validator 0오류 확인)
4. 백업 시점 이후 발생분은 audit_logs(스냅샷·현재분)를 대조해 수기 재입력
5. 복구 후 승인 대기함·Slot 상태 전수 확인

### C. 채팅 위젯 오류 (응답 없음/이상 응답)
1. 브라우저 콘솔 확인 (F12) — CORS/api 주소 확인 (`?api=` 파라미터)
2. AI 경로 문제 시: 서버 환경변수 `ANTHROPIC_API_KEY` 제거 후 재시작 →
   **규칙 기반 경로로 자동 폴백** (플랫폼 원칙 유지된 채 서비스 지속)
3. 위젯 자체 차단 필요 시: 정적 서버에서 chat/ 접근 차단 — admin·엔진은 영향 없음

### D. AI 이상 응답 (확정 표현·의료 판단·개인정보 노출 의심)
1. **즉시 채팅 차단** (C-3) — 파일럿 중단 기준 해당
2. 해당 세션ID·시각 기록, `GET /api/audit-logs`와 AI 상담 통계 화면에서 이력 확보
3. 데이터 훼손 여부 확인 (예약이 임의 확정됐는지: 감사로그에 RESERVATION_APPROVED 행위자 확인
   — AI 계정(USR-9000)의 APPROVED 기록은 구조상 불가하므로 발견 시 최우선 보고)
4. 개인정보보호 책임자 보고 후 재개 결정

### E. 알림 미발송 (PENDING 적체)
1. `python src\workers\notification_worker.py` 수동 실행 → 결과 확인
2. FAILED 사유 확인 (수신자·전화번호 없음 등) → 수기 연락으로 보완
3. `retry_failed` 후 재처리. 적체 지속 시 스케줄러 등록 상태 점검

### F. Rate Limit 오작동 (정상 사용자 429)
1. `CSHSP_CHAT_RATE` 상향(예: 60/60) 후 서비스 재시작
2. 특정 세션 반복 429는 봇/오남용 가능성 — 세션ID 기록

### G. 포트 충돌 / 이중 기동
1. `Get-NetTCPConnection -LocalPort 8600 -State Listen` → PID 확인 → 중복 프로세스 종료
2. 서비스 단일 인스턴스 원칙 (파일 잠금은 다중 프로세스도 보호하지만 성능 저하)

## 1-2. Sheets / Admin Portal / Slot / Policy / Legacy 관련 대응 (신설, Sprint7 Commit7-4)

> 오류 코드는 실제 구현된 것과 설계 단계인 것을 구분해 표기한다. `RESERVATION_POLICY_BLOCKED`/`SLOT_FULL`/`SLOT_BLOCKED`/`SLOT_ON_HOLD`/`SLOT_NOT_AVAILABLE`/`SLOT_INVALID_STATE`/`SLOT_RESERVATION_CONFLICT`/`SLOT_POLICY_VALIDATION_FAILED`/`RESERVATION_PROGRAM_UNMAPPED`는 **실제 운영 코드에 존재**(`routes_admin_portal.py`, 코드로 확인). `INVALID_STATUS_TRANSITION` 등 Legacy Stage3 Phase B 관련 코드는 **[Draft] — 아직 구현되지 않은 설계안**(`Legacy_Stage3_PhaseB_Design_v1.0.md` §10)이며 실제로 발생하지 않는다.

### H. Admin Portal 접속 장애
- **증상**: `admin_portal_new.html` 접속 불가 또는 백지 화면
- **영향**: 승인/거절 업무 중단(Legacy Portal은 별도 URL이라 영향 없을 수 있음)
- **사용자 안내**: "관리자 화면 접속 불가, 확인 중" 공지
- **1차 확인**: 정적 서버(포트 4000 등) 기동 상태, 브라우저 콘솔(F12) 오류 확인
- **담당자 조치**: 정적 서버 재시작, `?api=` 파라미터로 API 서버 주소가 올바른지 확인
- **중단 기준**: 10분 내 미복구 시 P2 보고
- **복구 방법**: 정적 서버 재기동
- **Rollback 필요 여부**: 불필요(정적 파일 서빙 문제)
- **상위 보고 기준**: `## 2. 보고 체계` P2
- **사후 기록**: 원인(서버 다운/네트워크 등) 기록

### I. FastAPI 응답 장애 / Timeout
- **증상**: Admin Portal 승인/거절 클릭 시 무응답 또는 "요청 시간이 초과되었습니다"(Commit5-3.2, 8초 AbortController)
- **영향**: 승인/거절 처리 지연
- **사용자 안내**: 기존 A(API 서버 무응답) 절차와 동일하게 우회(전화·수기 접수)
- **1차 확인**: `GET /api/admin-portal/health` 응답 확인(§A 참조)
- **담당자 조치**: FastAPI 프로세스 재시작(`process_manager.md`)
- **중단 기준**: §A와 동일
- **복구 방법**: §A와 동일
- **Rollback 필요 여부**: 불필요(단순 재시작으로 해결되지 않으면 §B 데이터 손상 절차로 전환)
- **상위 보고 기준**: §A와 동일
- **사후 기록**: Timeout 발생 빈도 기록(반복 시 네트워크/서버 성능 이슈 의심)

### J. Google Sheets 조회 장애
- **증상**: Admin Portal 목록이 비거나 "Sheets 연동 미설정/오류" 배지 표시
- **영향**: 예약 목록 조회 불가, 승인/거절도 함께 불가(승인 흐름이 조회를 선행함)
- **사용자 안내**: "예약 조회 시스템 점검 중"
- **1차 확인**: `GET /api/admin-portal/health`의 `sheetsIntegration` 값(`not_configured`/`error`)
- **담당자 조치**: `not_configured`면 `CSHSP_GAS_WEBAPP_URL` 환경변수 확인, `error`면 GAS 배포 상태(§K) 확인
- **중단 기준**: 즉시 P2 보고(예약 업무 전면 중단이므로)
- **복구 방법**: 환경변수 재설정 또는 GAS 재배포 후 확인
- **Rollback 필요 여부**: GAS를 방금 재배포했다면 이전 버전으로 되돌리는 것도 고려(`DEPLOY_GUIDE_new.md` §8)
- **상위 보고 기준**: P2(당일), 장시간 지속 시 P1
- **사후 기록**: 원인·복구 소요 시간 기록

### K. Google Sheets 쓰기 장애
- **증상**: 승인 시도 시 502 `SHEETS_WRITE_FAILED`(실제 코드로 확인된 코드)
- **영향**: 해당 예약 승인 실패, **Slot은 자동 Rollback됨**(Sprint4 Commit3, `_safe_rollback_slot()` — 코드로 확인된 기존 동작이므로 안심 가능)
- **사용자 안내**: "일시적 오류, 잠시 후 재시도 요청"
- **1차 확인**: GAS `?action=ping` 응답
- **담당자 조치**: GAS 배포 상태 확인, LockService 경합(동시 요청 과다)이면 잠시 대기 후 재시도
- **중단 기준**: 5회 이상 반복 실패 시 P2 보고
- **복구 방법**: GAS 재배포 또는 대기 후 자동 회복
- **Rollback 필요 여부**: 이미 자동 Rollback되므로 추가 조치 불필요(단, `SLOT_ROLLBACK_FAILED`(500) 발생 시는 예외 — 아래 §M 참조)
- **상위 보고 기준**: P2
- **사후 기록**: 실패 건수·시간대 기록(패턴 확인용)

### L. Apps Script 장애
- **증상**: GAS `?action=ping` 무응답 또는 5xx
- **영향**: Sheets 조회/쓰기 전체 중단(FastAPI 경유든 Legacy 직접 호출이든 전부 영향)
- **사용자 안내**: §J/§K와 동일
- **1차 확인**: Google Workspace 상태 대시보드(외부), Apps Script 실행 기록(Google 콘솔)
- **담당자 조치**: Apps Script 편집기에서 실행 로그 확인, 필요 시 재배포(`DEPLOY_GUIDE_new.md` §2, 반드시 "새 버전")
- **중단 기준**: 즉시 P2, 30분 이상 지속 시 P1
- **복구 방법**: 재배포 또는 Google 측 장애 해소 대기
- **Rollback 필요 여부**: 직전 배포가 원인으로 의심되면 이전 버전 재배포
- **상위 보고 기준**: P1/P2(지속 시간에 따라)
- **사후 기록**: Google 측 장애였는지 배포 문제였는지 구분해 기록

### M. 예약 승인 실패(일반)
- **증상**: 승인 클릭 시 4xx/5xx 응답, Admin Portal에 오류 Toast 표시
- **영향**: 해당 건 미승인
- **사용자 안내**: Toast 메시지를 그대로 안내(Sprint5 Commit5-3.2 이후 서버 메시지가 정확히 표시됨)
- **1차 확인**: 응답 코드 확인(§N/§O/§K 중 어디 해당하는지 분류)
- **담당자 조치**: 코드별 분기 처리(아래 항목 참조)
- **중단 기준**: 코드별 상이
- **복구 방법**: 코드별 상이
- **Rollback 필요 여부**: `SLOT_ROLLBACK_FAILED`(500)면 **Slot 데이터 수동 확인 필수**(코드 주석에 명시된 기존 정책)
- **상위 보고 기준**: 반복/다발 시 P2
- **사후 기록**: 코드별 발생 건수 기록

### N. Policy 차단(RESERVATION_POLICY_BLOCKED, 409)
- **증상**: 승인 시 "예약 정책 검증에 의해 이 예약을 확정할 수 없습니다"
- **영향**: 정상적인 정책 차단(휴진일/의료진 부재/검사실·장비 문제/프로그램 제한) — **오류가 아니라 의도된 동작일 수 있음**
- **사용자 안내**: 구체적 사유는 현재 응답에 포함되지 않음(reason_code는 [Draft], `Sprint4_Commit5_Reservation_Policy_Integration_Implementation_Plan_v1.1.md` §11 참조) — 담당자가 해당 날짜/Slot의 휴진일·의료진 근무표를 직접 확인해야 함
- **1차 확인**: `schedules.json`(휴진일), `doctors.json`/`nurses.json`(근무일), `rooms.json`/`equipment.json`(상태)
- **담당자 조치**: 확인된 사유를 수검자에게 안내, 다른 Slot 추천
- **중단 기준**: 다발 시(설정 오류 의심) P2
- **복구 방법**: 해당 없음(정상 동작)
- **Rollback 필요 여부**: 불필요
- **상위 보고 기준**: 다발 시에만
- **사후 기록**: 불필요(정상 동작 로그이므로 서버 로그로 충분, `_server_log()` 참조)

### O. Slot 충돌(SLOT_FULL/BLOCKED/ON_HOLD/NOT_AVAILABLE/INVALID_STATE/RESERVATION_CONFLICT)
- **증상**: 승인 시 409, 코드별 메시지(`production_checklist.md` ⑤/⑥ 참조)
- **영향**: 해당 Slot 승인 불가
- **사용자 안내**: 코드별 메시지 그대로 안내(정원마감/차단/보류/미확정상태/중복점유)
- **1차 확인**: `data/slots.json`에서 해당 Slot 상태 확인
- **담당자 조치**: `SLOT_RESERVATION_CONFLICT`(동일 예약번호 중복 점유)는 **자동 정정하지 않음** — 운영자가 Sheets와 Slot 데이터를 직접 대조해 확인(Sprint4 Commit3A 정책)
- **중단 기준**: `SLOT_RESERVATION_CONFLICT` 다발 시 P2(데이터 불일치 의심)
- **복구 방법**: 코드별 상이, 데이터 정정은 수동
- **Rollback 필요 여부**: 불필요(승인 자체가 실패했으므로 되돌릴 것이 없음)
- **상위 보고 기준**: `SLOT_RESERVATION_CONFLICT`만 P2, 나머지는 정상 동작으로 간주
- **사후 기록**: `SLOT_RESERVATION_CONFLICT` 발생 시 상세 기록 필수(데이터 정합성 조사 근거)

### P. Legacy 상태 변경 오류
- **증상**: Legacy Portal에서 상태 저장 시 오류 Toast(Legacy 자체 `toast()`, Admin Portal과 다른 구현)
- **영향**: 예약변경/취소/검진완료 실패(예약확정은 Commit6-1로 차단되며 별도 안내, §Q 아님)
- **사용자 안내**: Legacy 자체 오류 메시지 그대로 안내(표준화 미흡, `Operation_Readiness_Assessment_v1.0.md` §3-2)
- **1차 확인**: GAS `?action=ping`(§L), 브라우저 콘솔
- **담당자 조치**: §J/§K/§L 절차 준용(Legacy도 결국 동일 GAS를 호출)
- **중단 기준**: §L과 동일
- **복구 방법**: §L과 동일
- **Rollback 필요 여부**: 불필요(Legacy는 Slot을 점유하지 않으므로 Rollback 대상 자체가 없음)
- **상위 보고 기준**: 다발 시 P2
- **사후 기록**: 어떤 전이(변경/취소/완료)에서 발생했는지 기록

### Q. 취소 후 Slot 미반환(알려진 제한사항, 오류 아님)
- **증상**: 예약확정 상태였던 예약을 Legacy Portal에서 "예약취소"로 변경했는데 해당 Slot의 정원이 그대로(감소하지 않음)
- **영향**: **이것은 버그가 아니라 현재 알려진 시스템 제한사항이다** — `_actionUpdateStatus()`(GAS)에는 Slot 관련 코드가 없어 취소 시 Slot이 자동으로 반환되지 않는다(코드로 확인, `Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1/§15 Risk #3 — **Critical로 이미 등록됨**)
- **사용자 안내**: 해당 없음(장애가 아니므로 수검자 안내 불필요)
- **1차 확인**: `data/slots.json`에서 해당 Slot의 `reservedCount`/`sheetsReservationNos` 확인
- **담당자 조치**: **수동으로 Slot 데이터 정정**(현재 자동화된 도구 없음 — 별도 스크립트는 이번 갱신 범위 밖)
- **중단 기준**: 해당 없음(알려진 제한사항이므로 서비스 중단 사유 아님)
- **복구 방법**: 수동 정정
- **Rollback 필요 여부**: 불필요
- **상위 보고 기준**: 누적 시(정원 왜곡이 유의미해지면) P2로 격상해 Legacy Stage3 Phase B(Commit7-5 이후) 우선순위 상향 요청
- **사후 기록**: 발생 건수를 누적 기록해 Phase B 착수 근거로 활용(`Operation_Readiness_Assessment_v1.0.md` Gap #1 연계)

### R. 잘못된 상태 전이(역방향 등, 오류 아님)
- **증상**: Legacy Portal에서 "검진완료"를 다시 "예약접수"로 되돌리는 등 비정상적 순서 변경이 성공함
- **영향**: **현재 시스템은 이를 막지 않는다**(코드로 확인, §5-1 — UNDEFINED BUSINESS RULE로 등록됨, `Legacy_Stage3_PhaseB_Design_v1.0.md` §6)
- **사용자 안내**: 해당 없음
- **1차 확인**: Sheets에서 실제 상태값 이력 확인(단, 이력 저장 자체가 없어 현재값만 확인 가능)
- **담당자 조치**: 의도치 않은 변경으로 판단되면 수동으로 올바른 상태로 재수정
- **중단 기준**: 해당 없음(알려진 제한사항)
- **복구 방법**: 수동 재수정
- **Rollback 필요 여부**: 불필요
- **상위 보고 기준**: 빈번하면 운영자 교육 필요성으로 보고
- **사후 기록**: Phase B 설계 시 규칙 확정의 근거 자료로 누적

### S. 권한 오류
- **증상**: Admin Portal에서 403 "권한 없음"
- **영향**: 해당 사용자의 해당 작업 거부(RBAC 정상 동작)
- **사용자 안내**: "권한이 없습니다. 담당 역할을 확인해 주세요"
- **1차 확인**: `data/roles.json`/`data/users.json`에서 해당 계정의 역할·권한 확인
- **담당자 조치**: 정당한 권한 미부여였다면 역할 재조정, 정상적인 차단이면 조치 불필요
- **중단 기준**: 해당 없음(정상 동작)
- **복구 방법**: 역할 재조정 시에만
- **Rollback 필요 여부**: 불필요
- **상위 보고 기준**: 불필요(정상 동작)
- **사후 기록**: 불필요
- **⚠ 참고**: Legacy Portal 경유 예약변경/취소/검진완료는 **권한 검사 자체가 없다**(§P와 함께 인지 필요, GAS 자체에도 인증이 없음 — `production_checklist.md` ⑤ 참조)

### T. Netlify 배포 장애
- **증상**: 배포 후 사이트 접속 불가 또는 404
- **영향**: Portal 접속 불가(정적 파일 서빙 문제, Backend와 무관)
- **사용자 안내**: §H와 동일
- **1차 확인**: Netlify 대시보드에서 배포 로그 확인
- **담당자 조치**: `netlify.toml`의 `publish` 경로 확인(`DEPLOY_GUIDE_new.md` §10)
- **중단 기준**: 즉시 P2
- **복구 방법**: 이전 배포로 Netlify에서 직접 Rollback(Netlify 자체 기능)
- **Rollback 필요 여부**: 예(Netlify UI에서 이전 배포 선택)
- **상위 보고 기준**: P2
- **사후 기록**: 배포 실패 원인 기록

### U. 데이터 정합성 이상(Sheets ↔ 로컬 Slot 간)
- **증상**: Sheets 예약 상태와 로컬 `data/slots.json`의 점유 정보(`reservedCount`/`sheetsReservationNos`)가 서로 맞지 않음
- **영향**: 정원 왜곡, 이중 점유 가능성
- **사용자 안내**: 해당 없음(내부 데이터 이슈)
- **1차 확인**: `SLOT_RESERVATION_CONFLICT`(§O) 또는 §Q(취소 후 Slot 미반환) 케이스에 해당하는지 우선 확인 — 로컬 JSON은 §B(데이터 파일 손상)와 별개로 `python src/core/data_validator.py`로 형식 오류만 확인 가능하고, **Sheets와의 대조는 자동화 도구가 없어 수동 확인만 가능**
- **담당자 조치**: 수동 대조 후 정정(§O/§Q 절차 준용)
- **중단 기준**: 정원 초과 예약이 실제로 발생한 것으로 확인되면 즉시 P1
- **복구 방법**: 수동 정정, 필요 시 해당 Slot 신규 예약 임시 중지
- **Rollback 필요 여부**: 상황에 따라(§14 `Legacy_Stage3_PhaseB_Design_v1.0.md` Rollback Strategy 참고 가능하나 이는 Phase B 전환 시나리오 전용이므로 현재 상황엔 직접 적용 불가 — 수동 대응이 유일한 현재 수단)
- **상위 보고 기준**: P1(정원 초과 확인 시), 그 외 P2
- **사후 기록**: 반드시 기록(Phase B 우선순위 근거로 누적, §Q와 동일 목적)

## 2. 보고 체계

| 등급 | 예시 | 보고 |
|------|------|------|
| P1 (즉시) | 개인정보 노출, AI 임의 확정, 데이터 복구 실패 | 센터장 + 개인정보보호 책임자 즉시 유선 |
| P2 (당일) | 서버 다운 30분 이상, 백업 실패 | 센터장 일일 보고 포함 |
| P3 (주간) | 채팅 오탐 차단, UI 불편 | 주간 파일럿 리뷰 |

## 3. 연락망 (파일럿 개시 전 기입)
- 검진센터 운영 담당: ______ / 전산 담당: ______ / 개인정보보호 책임자: ______
- 검진센터 대표번호: 041-570-7333 (장애 시 수검자 우회 접수)
