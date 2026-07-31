# CSHSP Rollback Guide

> 작성: Sprint7 Commit7-5(2026-07-29) — 신규 독립 문서.
> 기준선: `9c41776`(Commit7-4 완료본) 위, 선행 Baseline `73cb25a`(Commit7-3).
> 분류 범례: **[Confirmed]** 코드/문서로 확인된 사실 · **[Manual Procedure]** 수동 절차로만 가능(자동화 도구 없음) · **[Decision Required]** 미확정, PM/운영팀 결정 필요 · **[Not Implemented]** 아직 구현되지 않음 · **[Design Only]** 설계 문서만 존재, 실제 절차 아님.

---

## 1. 문서 목적과 적용 범위

**[Confirmed]** 이 문서는 CSHSP(천안의료원 AI 건강검진 플랫폼)의 배포·운영 중 문제가 발생했을 때 이전 상태로 되돌리는(Rollback) 절차를 정리한다. 적용 범위는 Git 소스, Netlify 정적 배포, Google Apps Script(GAS) 배포, FastAPI Backend, Google Sheets 데이터, Admin/Reservation/Legacy 3개 Portal이다. 예약(Reservation) 데이터의 SSOT는 Google Sheets이며(ADR-013), 이 문서의 모든 절차는 이 원칙을 전제로 한다.

이 문서는 기존 `docs/CSHSP_Failure_Response_Manual.md`(장애 증상별 1차 대응)의 후속 문서다 — 장애를 먼저 진단할 때는 그 문서를, **되돌리기로 결정한 이후의 구체적 절차**는 이 문서를 참조한다.

## 2. Rollback 개시 기준

**[Decision Required]** 아래는 제안 기준이며 최종 확정은 PM/운영팀 결정 사항이다.

| 상황 | Rollback 개시 여부(제안) |
|---|---|
| 배포 직후 Regression FAIL 다발 | 개시 검토(§17 Regression과 연계) |
| Admin Portal 승인/거절이 정상 작동하지 않음 | 개시 검토 |
| Google Sheets 조회/쓰기 실패가 지속됨(30분 이상) | 개시 검토(단, Sheets 자체는 Rollback 대상이 아니라 GAS/환경변수 원인일 가능성부터 확인 — §10) |
| Netlify 배포 후 화면 자체가 뜨지 않음 | 즉시 개시(§7) |
| GAS 재배포 후 `?action=ping` 실패 | 즉시 개시(§8) |
| 예약 데이터 정합성 이상(정원 초과 등) | **데이터 Rollback은 신중히 접근** — §16 참조, 단순 코드 Rollback으로 해결되지 않을 수 있음 |

## 3. Rollback 결정권자 및 실행 책임

**[Decision Required]** 아래는 이 세션에서 실제 인력 배정을 확인할 수 없어 자리만 마련한다(`CSHSP_Failure_Response_Manual.md` §3 연락망과 동일하게 미확정 상태).

- **Rollback 실행 승인**: PM(코드/설정 변경 전 항상 승인 필요, 이번 Sprint 전체의 공통 원칙)
- **Git/Netlify Rollback 실행**: 전산 담당(미지정)
- **GAS Rollback 실행**: Google 계정 소유자 또는 위임받은 전산 담당(Google 계정 인증이 필요해 특정 인원만 가능 — `PROJECT_STATUS.md` §2에서 이미 확인된 제약과 동일)
- **Sheets 데이터 정정**: 검진센터 운영 담당 + 전산 담당 공동(개인정보 포함 데이터이므로 단독 처리 지양)

## 4. 배포 전 확인사항

**[Confirmed]** `src/deploy/production_checklist.md` ①(Git 및 소스)~⑨(Release/Rollback)를 배포 전에 먼저 확인한다. 이 문서는 "이미 배포했는데 문제가 생겼을 때"를 다루며, 배포 전 예방은 그 체크리스트가 담당한다(중복 작성하지 않음).

## 5. 공통 초동조치

**[Manual Procedure]**

1. 증상 발생 시각·발견자·증상을 기록한다(§20 사후 기록 양식 사용).
2. `docs/CSHSP_Failure_Response_Manual.md`에서 해당 증상 항목을 찾아 1차 대응을 먼저 수행한다 — **재시작·설정 확인만으로 해결되면 이 문서(Rollback)까지 갈 필요 없다.**
3. 1차 대응으로 해결되지 않으면 이 문서의 해당 절(§6~§16)로 이동한다.
4. **어떤 Rollback도 시작 전에 현재 상태를 기록해 둔다**(가능하면 스크린샷·로그 저장) — Rollback 후 비교 기준이 된다(§17).

## 6. Git 및 소스 기준 Rollback

**[Confirmed]** 버전 관리는 Git 커밋 기반이다(ADR-012).

- **발생 조건**: 최근 커밋된 코드/문서 변경이 문제의 원인으로 의심될 때
- **주요 증상**: 특정 기능이 이전에는 되던 대로 동작하지 않음
- **영향 범위**: 해당 커밋이 건드린 파일 범위(`git show --stat <hash>`로 확인)
- **즉시 조치**: 현재 `git status`/`git log -1`로 정확한 현재 위치 확인
- **복구 절차**:
  1. 문제 원인으로 의심되는 커밋 특정(`git log --oneline`)
  2. **[Manual Procedure]** 되돌릴 커밋 범위를 PM과 함께 확정
  3. **⛔ 파괴적 명령 금지** — `git reset --hard`, `git clean -fd`, `git checkout -- .` 등은 사용하지 않는다(다른 사람의 미커밋 변경사항을 삭제할 위험). 대신 **`git revert <hash>`**(새 커밋으로 되돌리기)를 우선 검토하거나, 이전 상태의 파일만 골라 복사하는 방식을 사용한다
  4. 되돌린 결과를 로컬에서 충분히 검증한 뒤에만 PM 승인 하에 push
- **확인 방법**: `git diff <이전커밋> <되돌린 후>`로 실제로 이전 상태와 동일한지 확인
- **성공 기준**: 문제 증상이 재현되지 않음, Regression PASS(§17)
- **실패 시 조치**: 원인이 코드가 아니라 데이터/환경 문제일 수 있음 — §9~§16으로 이동
- **책임자**: §3 참조
- **기록 항목**: 되돌린 커밋 범위, 사유, 결과

## 7. Netlify 배포 Rollback

**[Confirmed]** `netlify.toml` 기반 정적 배포(`docs/DEPLOY_GUIDE_new.md` §5).

- **발생 조건**: Netlify 배포 후 사이트 접속 불가/404/화면 깨짐
- **주요 증상**: `CSHSP_Failure_Response_Manual.md` §T(Netlify 배포 장애)와 동일
- **영향 범위**: 정적 파일(Portal HTML/JS) 전체 — Backend/Sheets에는 영향 없음
- **즉시 조치**: Netlify 대시보드에서 배포 로그 확인
- **복구 절차**: **[Manual Procedure]** Netlify 대시보드의 "Deploys" 화면에서 정상 동작이 확인된 이전 배포를 선택해 "Publish deploy"(Netlify 자체 기능, 이 플랫폼 코드와 무관) — Git 커밋을 되돌릴 필요 없이 Netlify 쪽에서만 즉시 복구 가능
- **확인 방법**: 배포된 URL 재접속, Admin Portal 로딩 확인
- **성공 기준**: 정상 화면 표시
- **실패 시 조치**: `netlify.toml`의 `publish` 경로 확인(`DEPLOY_GUIDE_new.md` §10 트러블슈팅), 그래도 안 되면 §6(Git Rollback) 병행 검토
- **책임자**: §3 참조
- **기록 항목**: 되돌린 배포 시각, 원인 배포의 커밋 해시

## 8. Google Apps Script Rollback

**[Confirmed]** 현재 운영 GAS 배포본은 `sheets_api_v3_final.gs`다(`ARCHITECTURE.md`, `DEPLOY_GUIDE_new.md` §2-0에서 확인). **`sheets_api_v4_deploy_new.gs` 파일이 저장소에 존재하나 실사용 여부는 확인되지 않았다 — 이 문서에서도 v3를 기준으로 작성하며, 확인 없이 v3에서 v4로 전환하지 않는다.**

- **발생 조건**: GAS 재배포 후 `?action=ping` 실패, 또는 예약 조회/쓰기 전체 장애(`CSHSP_Failure_Response_Manual.md` §L)
- **주요 증상**: Sheets 연동 전체 중단
- **영향 범위**: Admin Portal 조회/승인/거절, Legacy Portal 전체, Reservation Portal 예약 생성 — 사실상 예약 관련 전 기능
- **즉시 조치**: Apps Script 편집기 "배포 관리"에서 배포 이력 확인
- **복구 절차**: **[Manual Procedure, Google 계정 인증 필요]**
  1. Apps Script 편집기 → 배포 → 배포 관리
  2. 문제가 발생하기 이전의 배포 버전 확인
  3. **[Decision Required]** GAS는 "이전 버전으로 되돌리기" 자체보다 "이전 코드로 새 버전을 다시 배포"하는 방식이 일반적 — 정확한 절차는 실제 장애 시점에 Apps Script UI를 직접 보고 결정해야 한다(이 세션에서 실제 Rollback 조작을 실행해 본 적이 없어 UI 세부 단계를 추측으로 기재하지 않음)
  4. 재배포 시 **반드시 "새 버전"**(기존 버전 재사용 금지 — `PROJECT_STATUS.md` §2의 STEP1.5 사고 전례)
- **확인 방법**: `?action=ping` 재확인(§DEPLOY_GUIDE_new.md §2-5 응답 형식)
- **성공 기준**: ping 정상, Admin Portal 목록 조회 정상
- **실패 시 조치**: Google Workspace 자체 장애 가능성(`CSHSP_Failure_Response_Manual.md` §L) — Google 측 복구 대기
- **책임자**: §3(Google 계정 소유자 필수)
- **기록 항목**: 재배포 버전 번호, 원인, 소요 시간

## 9. FastAPI 장애 시 복구 및 우회 원칙

**[Confirmed]**

- **발생 조건**: `GET /api/admin-portal/health` 무응답 또는 500
- **주요 증상**: Admin Portal 전체 응답 없음(`CSHSP_Failure_Response_Manual.md` §A/§I)
- **영향 범위**: 승인/거절 처리 전체(Legacy Portal은 FastAPI를 거치지 않으므로 영향 없음 — 단, 예약변경/취소/검진완료는 원래도 검증이 없어 Rollback 여지 자체가 다름, §13 참조)
- **즉시 조치**: 프로세스 상태 확인(`process_manager.md`)
- **복구 절차**:
  1. FastAPI 프로세스 재시작(NSSM 서비스 재시작 또는 수동 재기동)
  2. 재시작으로 해결되지 않으면 §6(직전 배포 코드 Rollback) 검토
  3. **우회 원칙**: FastAPI 복구 전까지 승인 업무는 **전화·수기 접수로 우회**(`CSHSP_Failure_Response_Manual.md` §A와 동일 원칙) — 단, 이 경우 승인 시 수행되는 Slot 점유·Policy 검증이 생략되므로, 복구 후 수기 처리분에 대해 **수동으로 Slot/Sheets 정합성을 재확인**해야 한다(§16 연계)
- **확인 방법**: Health Check 정상, 승인 API 테스트 호출 정상
- **성공 기준**: Regression PASS(§17)
- **실패 시 조치**: 데이터 손상 의심 시 로컬 JSON은 §11, Sheets는 §10
- **책임자**: §3 참조
- **기록 항목**: 장애 시간, 우회 처리 건수(수기 접수 건), 복구 후 재확인 결과

## 10. Google Sheets 장애·오염·오입력 복구

**[Confirmed 사실만 기재, Decision Required 다수]**

- **발생 조건**: 조회/쓰기 실패, 또는 정상 응답하나 값이 잘못됨(오입력/오염)
- **주요 증상**: `CSHSP_Failure_Response_Manual.md` §J(조회장애)/§K(쓰기장애)/§U(정합성 이상)
- **영향 범위**: 예약 데이터 전체(SSOT이므로)
- **즉시 조치**: §J/§K/§L(GAS) 절차로 먼저 "장애"인지 "데이터 오염"인지 구분
- **복구 절차(장애)**: §8(GAS Rollback)/§9(FastAPI) 참조
- **복구 절차(오염/오입력)**:
  1. **[Confirmed]** Google Sheets는 자체 버전 기록(파일 히스토리) 기능을 제공한다(Google Workspace 표준 기능, `backup_policy.md` §5-1에서 이미 확인) — 이것이 현재 확인 가능한 유일한 복구 수단이다
  2. **[Manual Procedure]** Sheets 메뉴 → 파일 → 버전 기록에서 오염 이전 시점 확인 → 필요한 범위만 수동으로 복사해 되돌림(시트 전체를 통째로 되돌리면 그 사이 발생한 정상 예약도 함께 사라지므로 **행 단위로 신중히 판단**)
  3. **[Decision Required]** 버전 기록의 보존 기간, 복구 성공 기준(행 수 대조 등)은 미확정(`backup_policy.md` §5-2)
- **확인 방법**: 되돌린 범위의 데이터를 Admin Portal에서 재조회해 정상 표시되는지 확인
- **성공 기준**: **[Decision Required]** 아직 명확한 기준이 없음 — 임시로 "감사로그(`audit_logs.json`)와 대조해 예약확정 이력이 일치하는지"를 최소 기준으로 제안하나 확정 아님
- **실패 시 조치**: 개인정보보호 책임자 및 PM 보고(P1, `CSHSP_Failure_Response_Manual.md` §2 보고 체계 기준)
- **책임자**: §3 참조
- **기록 항목**: 오염 범위, 복구 방법, 복구 전후 건수 비교
- **⛔ 반드시 지킬 것**: 복구 과정에서 개인정보가 포함된 Sheets 사본을 **로컬 저장 시에도 Git 저장소에 커밋하지 않는다**(`backup_policy.md` §2)

## 11. Admin Portal 장애 복구

**[Confirmed]** §7(Netlify, 정적 파일 문제)과 §9(FastAPI, API 문제) 중 어느 쪽인지 먼저 구분한다(브라우저 콘솔에서 네트워크 요청이 아예 안 나가면 §7, 요청은 나가는데 실패하면 §9). 상세는 `CSHSP_Failure_Response_Manual.md` §H 참조. 이 절은 두 절차의 진입점 안내이며 중복 작성하지 않는다.

## 12. Reservation Portal 장애 대응

**[Confirmed]** `reservation_v3_new.html`은 GAS를 직접 호출하며 FastAPI를 거치지 않는다(코드로 확인, `Sprint5_Portal_Integration_Implementation_Plan_v1.0.md` §1-3). 따라서 이 화면의 장애는 §7(정적 파일)과 §8(GAS)의 조합으로 대응한다 — 별도의 FastAPI 우회 원칙(§9)은 적용되지 않는다(애초에 FastAPI를 거치지 않으므로).

- **발생 조건**: 예약 신청 폼 제출 실패
- **주요 증상**: 제출 후 오류 메시지(`alert()` — 이 화면은 Toast로 표준화되지 않음, `Operation_Readiness_Assessment_v1.0.md` §3-2)
- **영향 범위**: 신규 예약 접수 불가
- **즉시 조치**: §8(GAS) 절차로 원인 확인
- **복구 절차**: §7/§8 참조
- **확인 방법**: 테스트 데이터로 신청 후 Sheets 반영 확인(`DEPLOY_GUIDE_new.md` §7-2)
- **성공 기준**: 정상 접수·채번
- **실패 시 조치**: 수검자에게 전화 접수 안내(§9 우회 원칙과 동일 성격)
- **책임자**: §3 참조
- **기록 항목**: 장애 시간, 우회 접수 건수

## 13. Legacy Portal 상태변경 장애 대응

**[Confirmed]** `admin_reservations_v2_new.html`은 예약변경/취소/검진완료를 담당하며, "예약확정"만 클라이언트측(브라우저 JS)에서 차단된다(Sprint6 Commit6-1) — **서버측 강제는 아니다**(`Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1). 이 3개 전이는 FastAPI 검증·권한 검사·감사 로그가 없다.

- **발생 조건**: Legacy Portal에서 상태 저장 실패, 또는 저장은 됐으나 결과가 이상함
- **주요 증상**: `CSHSP_Failure_Response_Manual.md` §P
- **영향 범위**: 해당 예약 1건(단, 오조작이 누적되면 §16으로 확대)
- **즉시 조치**: §8(GAS) 절차로 GAS 자체 장애인지 먼저 확인
- **복구 절차**: **[Manual Procedure]** 잘못 저장된 상태값을 Sheets에서 직접 열어 올바른 값으로 수동 재수정 — **[Not Implemented]** 자동 복구 도구는 없다. **[Design Only]** Phase B(`ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md`)가 완료되면 서버측 검증/Rollback이 생기나 현재는 미구현
- **확인 방법**: 수정 후 Admin Portal/Legacy Portal에서 재조회
- **성공 기준**: 의도한 상태값으로 정상 표시
- **실패 시 조치**: §16(데이터 정합성)으로 확대 보고
- **책임자**: §3 참조
- **기록 항목**: 어떤 전이에서 발생했는지, 수동 수정 내용

**⚠ 참고(제한사항, Rollback과 별개로 항상 인지)**: 예약변경은 현재 실제 희망일시를 변경하지 않고 상태 라벨만 바뀐다(코드로 확인, `Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1) — 이는 장애가 아니라 현재 기능 자체의 한계이므로 Rollback 대상이 아니다.

## 14. Policy 오류 대응

**[Confirmed]** `RESERVATION_POLICY_BLOCKED`(409)는 정상적인 정책 차단(휴진일/의료진 부재/검사실·장비 문제/프로그램 제한)일 가능성이 높다 — `CSHSP_Failure_Response_Manual.md` §N 참조.

- **발생 조건**: 승인 시 정책 차단 응답
- **주요 증상**: "예약 정책 검증에 의해 이 예약을 확정할 수 없습니다"
- **영향 범위**: 해당 예약 1건
- **즉시 조치**: `schedules.json`/`doctors.json`/`nurses.json`/`rooms.json`/`equipment.json` 확인
- **복구 절차**: **이것은 대부분 Rollback 대상이 아니다** — 데이터(휴진일 미등록 등) 설정 오류라면 해당 데이터 정정, 정상 차단이라면 조치 불필요
- **확인 방법**: 원인 데이터 정정 후 재승인 시도
- **성공 기준**: 정상 승인 또는 차단 사유 확인 완료
- **실패 시 조치**: 설정 오류가 아닌데 반복 차단되면 `SLOT_POLICY_VALIDATION_FAILED`(500) 여부 확인 → §9(FastAPI) 절차
- **책임자**: §3 참조
- **기록 항목**: 불필요(정상 동작 시), 예외 시 §9 기준

## 15. Slot 충돌 및 Slot 미반환 대응

**[Confirmed]** `CSHSP_Failure_Response_Manual.md` §O(Slot 충돌)/§Q(취소 후 Slot 미반환) 참조.

- **발생 조건**: `SLOT_FULL`/`SLOT_BLOCKED`/`SLOT_ON_HOLD`/`SLOT_NOT_AVAILABLE`/`SLOT_INVALID_STATE`/`SLOT_RESERVATION_CONFLICT`(전부 실제 구현된 코드) 또는 취소 후에도 Slot 정원이 줄지 않는 현상(§Q)
- **주요 증상**: 승인 실패, 또는 겉보기엔 정상이나 정원 표시가 이상함
- **영향 범위**: 해당 Slot(정원 왜곡은 누적되면 다른 예약에도 영향)
- **즉시 조치**: `data/slots.json`에서 해당 Slot 확인
- **복구 절차**:
  - `SLOT_RESERVATION_CONFLICT`: **자동 정정하지 않는다**(Sprint4 Commit3A 정책, 확정된 기존 원칙) — Sheets와 Slot 데이터를 대조해 수동 확인
  - **취소 후 Slot 미반환**: **[Manual Procedure, Not Implemented 자동화]** `reservedCount`를 수동으로 감소시키고 `sheetsReservationNos` 배열에서 해당 예약번호 제거 — 단, 이 작업은 **동시에 다른 예약이 해당 Slot을 점유하지 않았는지 먼저 확인**해야 한다(경쟁 상태 위험, `Legacy_Stage3_PhaseB_Design_v1.0.md` §14에서 이미 High Risk로 등록된 것과 동일 성격의 위험)
- **확인 방법**: 수정 후 Slot 정원과 실제 예약 건수 대조
- **성공 기준**: `reservedCount` = 실제 유효 예약 건수
- **실패 시 조치**: §16(데이터 정합성)으로 확대
- **책임자**: §3 참조
- **기록 항목**: 발생 건수 누적 기록(Phase B 우선순위 근거로 활용 — `Legacy_Stage3_PhaseB_Design_v1.0.md` §15 Risk #3과 연계)

## 16. 데이터 정합성 이상 대응

**[Confirmed]** `CSHSP_Failure_Response_Manual.md` §U 참조. Sheets와 로컬 Slot 간 불일치의 최종 단계.

- **발생 조건**: §15의 수동 대응으로도 원인이 불명확하거나, 정원 초과 예약이 실제로 발생한 것으로 확인됨
- **주요 증상**: 여러 건의 정원/상태 불일치가 동시다발
- **영향 범위**: 전체 Slot 데이터 신뢰도
- **즉시 조치**: **정원 초과가 실제로 확인되면 해당 Slot의 신규 예약을 임시 중지**(Admin Portal 승인 버튼 자체를 막을 도구는 없으므로, 운영자가 수동으로 해당 시간대 승인을 보류)
- **복구 절차**: **[Manual Procedure]** `data/slots.json` 전수 조사 + Sheets 예약 목록 전수 대조 — **[Not Implemented]** 자동 대조 도구는 없다
- **확인 방법**: 대조 완료 후 재검증
- **성공 기준**: 모든 Slot의 `reservedCount`가 Sheets 상 유효 예약(예약확정 상태) 건수와 일치
- **실패 시 조치**: P1 즉시 보고(`CSHSP_Failure_Response_Manual.md` §2 보고 체계)
- **책임자**: §3 참조, 반드시 전산 담당 참여
- **기록 항목**: 전수 조사 결과, 정정 내역 — 재발방지책 수립 근거로 보존(§20)

## 17. Rollback 후 Regression Test

**[Confirmed]** 어떤 Rollback이든(§6~§16) 완료 후 아래를 재실행해 회귀가 없는지 확인한다(`production_checklist.md` ②에 이미 나열된 스위트와 동일, 중복 작성하지 않고 인용).

- Backend: `run_sprint4_commit2_approval_qa.py`, `run_sprint4_commit3_slot_integration_qa.py`, `run_sprint4_commit3a_slot_hardening_qa.py`, `run_sprint4_commit5_1_validation_context_program_mapping_qa.py`, `run_sprint4_commit5_2_approval_pipeline_policy_integration_qa.py`, `run_sprint_b_tests.py`
- Node: `run_sprint5_commit5_3_1_portal_error_parser_qa.js`, `run_sprint6_commit6_1_legacy_approval_guard_qa.js`, `run_sprint6_commit6_2_technical_debt_cleanup_qa.js`
- **Sheets/GAS Rollback(§8/§10)의 경우** 위 스위트에 더해 §DEPLOY_GUIDE_new.md §2-5(ping)·§6(Smoke Test)도 재확인

## 18. 운영 재개 승인 기준

**[Decision Required]** 최종 확정은 PM 사항이나, 제안 기준은 다음과 같다.

1. §17 Regression 전부 PASS
2. 원인이 된 장애 유형(§8~§16)의 "확인 방법"/"성공 기준" 충족
3. §20 사후 기록 작성 완료
4. PM 확인 후 운영 재개 공지

## 19. 실패 시 상위 보고·서비스 제한 기준

**[Confirmed]** `CSHSP_Failure_Response_Manual.md` §2 보고 체계(P1/P2/P3)를 그대로 따른다. Rollback 시도가 실패했거나 원인 불명이면 **P1(즉시)**로 격상해 센터장·개인정보보호 책임자에게 유선 보고한다. 서비스 제한(예: Admin Portal 승인 기능 일시 중지)이 필요하면 이 단계에서 PM과 함께 결정한다 — **[Not Implemented]** 원격으로 특정 기능만 끄는 기능 플래그는 현재 없으므로, 제한이 필요하면 담당자가 Admin Portal 접근 자체를 안내하지 않는 방식(운영적 조치)으로 대응한다.

## 20. 사후 기록 및 재발방지

**[Manual Procedure]** 아래 양식으로 기록한다(전용 도구 없음, 운영 문서/일지로 보존).

```
발생일시:
발견자:
장애/오류 유형(§6~§16 중 해당 절):
증상:
영향 범위(건수 등):
초동조치:
Rollback 실행 여부 및 절차:
Regression 결과:
운영 재개 시각:
재발방지 조치(필요 시):
기록자:
```

반복 발생하는 유형은 `Operation_Readiness_Assessment_v1.0.md`의 Gap Analysis 또는 `Legacy_Stage3_PhaseB_Design_v1.0.md`의 Risk Register에 누적 반영을 건의한다(이 문서에서 직접 그 문서들을 수정하지 않음 — 별도 절차).

## 21. Rollback 완료보고 양식

```
Rollback 완료 보고
─────────────────
대상: (§6 Git / §7 Netlify / §8 GAS / §9 FastAPI / §10 Sheets / §13 Legacy / §15 Slot / §16 데이터정합성)
개시 시각:
완료 시각:
실행자:
승인자(PM):
수행 절차 요약:
Regression 결과(§17):
운영 재개 승인 여부(§18):
잔여 위험:
후속 조치 필요 여부:
```

---

## 완료 조건 준수 확인

이 문서 작성 중 어떤 코드·설정·운영 데이터도 변경하지 않았다. 파괴적 Git 명령을 절차로 제시하지 않았다(`git revert`만 예시로 제안, `reset --hard`/`clean -fd`/`checkout -- .` 등은 명시적으로 금지 표기). 확인되지 않은 명령어·URL·파일명은 만들지 않았으며, 실제 값을 확인할 수 없는 절차는 [Decision Required]/[Manual Procedure]/[Not Implemented]/[Design Only]로 명확히 표시했다.
