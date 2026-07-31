# Sprint7 Closeout & Operational Readiness Consolidation

> 작성: Sprint7 Commit7-6(2026-07-31) — 신규 독립 문서.
> 기준선: `73cb25a`(Commit7-3, 선행 Baseline) → `9c41776`(Commit7-4) → `d414202`(Commit7-5, 직전 승인 Commit).
> 목적: Sprint7(Commit7-0~7-5) 전체 산출물을 통합하여 종료보고서와 운영 준비도 통합판정을 제공한다.
> 이 문서는 신규 평가를 수행하지 않는다 — **기존에 실측·기록된 내용을 통합·인용**할 뿐이며, 새로운 코드·테스트를 실행하지 않았다.

---

## 1. 문서 목적

Sprint7("Operation Readiness Sprint")의 6개 Commit(7-0~7-5) 산출물을 한 곳에 모아 Sprint7 종료 여부와 실제 운영 투입 가능 여부를 PM이 판단할 수 있도록 근거를 통합 제공한다. 이 문서 자체가 Sprint7을 종료시키는 것이 아니라 **PM 승인을 위한 근거 자료**다.

## 2. Sprint7 범위

`Sprint7_Design_Freeze_v1.0.md`에서 정의된 대로, Sprint7은 신규 기능 개발이 아니라 **운영 준비**(문서·절차·복구 대비·품질 검증)를 목표로 했다. 명시적 제외 대상: Reservation Portal FastAPI 마이그레이션, 대규모 Backend 리팩터링, Sheets/Apps Script 구조 변경, 신규 Business Rule.

## 3. 기준 Baseline과 Commit 이력

| 커밋 | 메시지 | 역할 |
|---|---|---|
| `4f21d0e` | docs: finalize sprint6 closeout | Sprint6 종료(Sprint7 시작 이전 Baseline) |
| `3c42c97` | docs: add sprint7 design freeze | Commit7-0 |
| `bccd04c` | docs: synchronize project ssot documents | Commit7-1 |
| `7f7d915` | docs: add operation readiness assessment | Commit7-2 |
| `73cb25a` | docs: design legacy stage3 phase b transitions | Commit7-3 |
| `9c41776` | docs: refresh operation documentation | Commit7-4 |
| `d414202` | docs: add rollback guide and operation faq | Commit7-5 |

모든 Hash는 `git log --oneline`으로 실측 확인했다(2026-07-31). 이 문서 작성 시점 HEAD는 `d414202`.

## 4. Sprint7 Commit7-0~7-5 완료 내역

§7 통합표 참조.

## 5. 주요 산출물 목록

- `Sprint7_Design_Freeze_v1.0.md`(7-0)
- `PROJECT_STATUS.md`/`ROADMAP.md`/`CLAUDE.md`/`ARCHITECTURE.md` 갱신(7-1)
- `Operation_Readiness_Assessment_v1.0.md`(7-2)
- `Legacy_Stage3_PhaseB_Design_v1.0.md`, `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md`(7-3)
- `src/deploy/production_checklist.md`, `docs/DEPLOY_GUIDE_new.md`, `src/deploy/backup_policy.md`, `docs/CSHSP_Failure_Response_Manual.md` 갱신(7-4)
- `docs/CSHSP_Rollback_Guide.md`, `docs/CSHSP_Operation_FAQ.md`(7-5)

전 Commit에서 **코드 변경은 0건**이었다(7-1의 문서 갱신 포함, 전부 `docs:` 커밋).

## 6. 시스템 현행 구조 요약

`ARCHITECTURE.md` §1~4 기준. Reservation Portal(수검자 예약신청, GAS `action=create` 직접 호출) / Admin Portal(승인·거절, FastAPI 경유) / Legacy Portal(변경·취소·검진완료, Sheets 직접 쓰기) 3-Portal 구조. Google Sheets가 예약 SSOT(ADR-013), FastAPI와 Legacy Portal 모두 GAS(`sheets_api_v3_final.gs`)를 거쳐 Sheets에 접근한다. 로컬 JSON(`data/`)은 Patient/CRM/AuditLog 등 19개 Entity의 원장이며, 예약 관련 로컬 JSON은 사본/Fixture 용도다.

## 7. Sprint7 Commit별 통합표

| Commit | 목적 | 주요 산출물 | 주요 결정 | 검증 결과 | 잔여 위험 | 승인 상태 | Commit Hash | 비고 |
|---|---|---|---|---|---|---|---|---|
| 7-0 | Design Freeze — Sprint7을 "운영 준비 Sprint"로 정의 | `Sprint7_Design_Freeze_v1.0.md` | 신규기능 금지, Commit 계획 확정 | 문서 리뷰만(코드 없음) | — | PM 승인 완료 | `3c42c97` | — |
| 7-1 | SSOT 문서 현행화 | PROJECT_STATUS/ROADMAP/CLAUDE/ARCHITECTURE 갱신 | Sprint4~6 실제 완료 상태 반영 | 문서 간 교차검증(충돌 없음) | — | PM 승인 완료 | `bccd04c` | — |
| 7-2 | 운영 준비도 평가 | `Operation_Readiness_Assessment_v1.0.md` | 5개 영역 Readiness Score(평균 58/100) | 실측 근거 기반 평가(회귀 스위트 재실행 결과 인용) | 인증 미구현·Legacy 무감사 등 Critical Gap 확인 | PM 승인 완료 | `7f7d915` | Sprint7의 근거 문서, 이번 통합판정의 기준선 |
| 7-3 | Legacy Stage3 Phase B 설계 | `Legacy_Stage3_PhaseB_Design_v1.0.md`, ADR-016 Draft | TO-BE 구조 권고(Admin Portal 신규 엔드포인트, 구현은 미착수), Decision Required 10건 | 설계 문서 리뷰만(구현 없음) | GAS 무인증, 예약변경 라벨전용 확인·문서화 | PM 승인 완료 | `73cb25a` | **설계만, 구현 없음**(ADR-016은 Draft 상태) |
| 7-4 | 운영 문서 현행화 | production_checklist/DEPLOY_GUIDE/backup_policy/Failure_Response_Manual 갱신 | 기존 7종 문서를 Sheets/Admin Portal 반영 갱신(신규 작성 아님) | 문서 리뷰, 용어 통일, 15개 실패유형 정리 | 미확정 항목 다수 Decision Required로 이월 | PM 승인 완료 | `9c41776` | — |
| 7-5 | Rollback Guide & Operation FAQ | `docs/CSHSP_Rollback_Guide.md`, `docs/CSHSP_Operation_FAQ.md` | 21개 섹션 Rollback 절차, 36개 Q&A FAQ | PII/Secret 정규식 검사 0건, 8개 참조문서 교차검증(충돌 없음) | 운영재개 승인권자 등 다수 Decision Required | PM 승인 완료 | `d414202` | — |

## 8. 구성요소별 실제 구현 상태

각 항목: 현재 상태 / 확인 근거 / 운영 가능 범위 / 제한사항 / 미조치 시 위험 / 운영 전 필요 조치 / 담당·결정 주체 순.

### Reservation Portal
- **상태**: Confirmed(구현·운영 중)
- **근거**: `reservation_v3_new.html` → GAS `action=create` 직접 호출(`Operation_Readiness_Assessment_v1.0.md` §3-1)
- **운영 가능 범위**: 신규 예약 접수 전체
- **제한사항**: FastAPI 미경유, Timeout 처리 없음(`AbortController` 0건, 재확인 완료)
- **미조치 시 위험**: 네트워크 무응답 시 무기한 대기 가능
- **운영 전 필요 조치**: 없음(Sprint7 범위 밖, Gap으로 기록만)
- **담당**: 향후 Portal 개선 Commit 후보(미정)

### Admin Portal
- **상태**: Confirmed(승인/거절 경로 성숙)
- **근거**: 252개 테스트 PASS(Commit2/3/3A/5-1/5-2, 2026-07-29 재확인), `parseApiError()`+8초 Timeout(Commit5-3.2)
- **운영 가능 범위**: 예약 승인·거절, Slot·Policy 검증 포함
- **제한사항**: 관리자 인증이 Mock(`X-User-Id` 헤더)뿐
- **미조치 시 위험**: 내부망 이탈 시 무인가 접근 가능
- **운영 전 필요 조치**: 실 인증 구현(Sprint7 범위 밖, 별도 Sprint 필요) — P0
- **담당**: PM/병원 전산 담당(Decision Required #13)

### Legacy Portal
- **상태**: Partially Implemented / Operationally Restricted
- **근거**: `admin_reservations_v2_new.html`, `reservation_approval_states.py` 설계상 예약확정 외 3개 전이(변경/취소/완료) 전담(§3-1 인용)
- **운영 가능 범위**: 변경/취소/검진완료 처리(현행 운영 절차상 필요)
- **제한사항**: **예약확정은 클라이언트 UI 수준 차단만**(Commit6-1 `approvalBlocked`, GAS 직접호출로 우회 가능, Commit7-3에서 확인). 변경/취소/완료는 서버 검증·감사로그 전무. "예약변경"은 상태 라벨 변경일 뿐 실제 일정 미반영(Commit7-3 §5-1에서 코드로 확인된 사실, "~일 수 있다"가 아니라 확정 사실).
- **미조치 시 위험**: 무인가 상태 변경, 정원 미반환 누적, 추적 불가
- **운영 전 필요 조치**: Legacy Stage3 Phase B(B-1 이후) 착수 여부 결정 — P1/P2
- **담당**: PM(Decision Required, Legacy_Stage3_PhaseB_Design_v1.0.md §16)

### FastAPI
- **상태**: Confirmed(승인·거절·Slot·Policy 경로에 한정)
- **근거**: `routes_admin_portal.py`, Commit5-2/5-2A Policy/Execution Layer 분리
- **운영 가능 범위**: 승인/거절 API
- **제한사항**: 모든 Portal 기능이 FastAPI를 경유하는 구조가 아님(생성은 GAS 직접, 변경/취소/완료는 Legacy 직접)
- **미조치 시 위험**: 없음(현재 범위 내에서는 안정적, §3-1 성숙도 평가 참조)
- **운영 전 필요 조치**: 없음
- **담당**: —

### Google Apps Script(GAS)
- **상태**: Confirmed(v3) / Decision Required(v4)
- **근거**: `sheets_api_v3_final.gs`가 `ARCHITECTURE.md`·`DEPLOY_GUIDE_new.md` §2-0에서 "현재 배포본"으로 일관 확인. `sheets_api_v4_deploy_new.gs`는 저장소에 존재하나 실사용 여부 미확인(자체 헤더에 "핵심 로직 v3와 동일" 명시).
- **운영 가능 범위**: v3 기준 전체 예약 CRUD
- **제한사항**: **`doGet`/`doPost`가 호출자 인증·인가를 전혀 수행하지 않음**(코드 확인, Commit7-3). Web App URL만 알면 누구나 호출 가능.
- **미조치 시 위험**: URL 유출 시 데이터 무단 접근/수정
- **운영 전 필요 조치**: GAS 직접호출 통제 방식 결정 — P0/P1(Decision Required)
- **담당**: PM/병원 전산 담당

### Google Sheets
- **상태**: Confirmed(SSOT)
- **근거**: ADR-013, 전 문서 일관 인용
- **운영 가능 범위**: 예약 데이터 전체의 공식 원장
- **제한사항**: 버전 기록(히스토리) 외 별도 백업 정책 없음(`backup_policy.md` §5-2, Decision Required)
- **미조치 시 위험**: 대규모 오염 시 복구 기준 부재
- **운영 전 필요 조치**: 백업 보존기간/책임자/복구 성공기준 확정 — P1
- **담당**: PM/병원 개인정보보호 책임자

### Netlify
- **상태**: Manual Procedure
- **근거**: `DEPLOY_GUIDE_new.md` 배포 절차 존재
- **운영 가능 범위**: 정적 파일 배포·이전 배포 되돌리기(Rollback Guide §7)
- **제한사항**: GAS 배포 버전과 Netlify 배포 버전 간 자동 동기화 없음
- **미조치 시 위험**: 버전 불일치로 인한 기능 오작동
- **운영 전 필요 조치**: 배포 시 양쪽 버전 수동 대조 — P1
- **담당**: 배포 담당자

### Policy 검증
- **상태**: Confirmed(승인 경로 한정)
- **근거**: Commit5-2/5-2A, `_EXECUTION_LAYER_VERDICTS` 분리 검증됨
- **운영 가능 범위**: 승인 시 휴진일/의료진/검사실/장비/프로그램 제한 검증
- **제한사항**: Legacy 경로(변경/취소/완료)에는 Policy 검증 미적용
- **미조치 시 위험**: Legacy 경로로 Policy 위반 예약 발생 가능
- **운영 전 필요 조치**: Legacy Stage3 Phase B 결정 필요 — P1
- **담당**: PM

### Slot 관리
- **상태**: Partially Implemented
- **근거**: 승인 시 점유·중복·정원 검증 성숙(252 테스트). Legacy 취소 시 Slot 미반환 확인(`_actionUpdateStatus()` 코드 검색, Slot 관련 로직 0건)
- **운영 가능 범위**: 승인 경로의 정원 통제
- **제한사항**: 취소 후 정원 미반환 — 데이터 정합성 이상 누적 위험
- **미조치 시 위험**: 실제 가용 정원보다 시스템상 정원이 적게 표시되는 상태 지속
- **운영 전 필요 조치**: 수동 정합성 점검 절차 운영 또는 B-2 착수 — P0(정합성 이상 발생 시) / P1(예방)
- **담당**: PM/병원 운영팀

### 상태전이
- **상태**: Partially Implemented
- **근거**: `reservation_approval_states.py`(승인 경로만 전이 규칙 정의)
- **운영 가능 범위**: 예약접수→예약확정/거절
- **제한사항**: 변경/취소/완료는 전이 규칙 검증 없음(Legacy 자유 전이)
- **미조치 시 위험**: 비정상 상태 전이(예: 완료 후 재변경) 방지 불가
- **운영 전 필요 조치**: Legacy Stage3 Phase B — P1/P2
- **담당**: PM

### 관리자 인증·인가
- **상태**: Not Implemented(인증) / Confirmed(인가 모델만)
- **근거**: `X-User-Id` Mock, `roles.json` 5개 역할 정의·테스트됨
- **운영 가능 범위**: 내부망 한정 사용
- **제한사항**: 실 로그인 없음, `reservation:change`/`reservation:cancel` 권한 문자열은 정의만 있고 실제 검사 코드 없음
- **미조치 시 위험**: 내부망 접근 가능자 전원이 사실상 전권
- **운영 전 필요 조치**: 실 인증 구현 — **P0**
- **담당**: PM/병원 전산 담당

### 백업·복구
- **상태**: Confirmed(로컬 JSON) / Manual Procedure(Sheets)
- **근거**: `backup_policy.md`, `run_backup_restore_rehearsal.py` 9/9 PASS(2026-07-29 실측)
- **운영 가능 범위**: 로컬 JSON 19개 Entity 백업·복구
- **제한사항**: Sheets는 자체 버전 기록 의존, 보존기간/책임자/성공기준 미확정
- **미조치 시 위험**: Sheets 손상 시 복구 근거 부족
- **운영 전 필요 조치**: Sheets 백업 정책 확정 — P1
- **담당**: PM/병원 개인정보보호 책임자

### 장애대응
- **상태**: Confirmed(로컬 JSON/API 관련) / Design Only(GAS/Sheets 일부, Draft 코드 포함)
- **근거**: `CSHSP_Failure_Response_Manual.md` §1(A-G, Sprint H) + §1-2(H-U, Commit7-4 신설)
- **운영 가능 범위**: 21개 유형(A-U) 대응 절차 문서화 완료
- **제한사항**: 일부 오류 코드는 `[Draft]`(Phase B 전용, 미구현)로 표시됨 — 실제 발생하지 않음
- **미조치 시 위험**: 없음(문서 준비 완료, 단 실제 대응 훈련 여부는 별도)
- **운영 전 필요 조치**: 담당자 실제 지정, 훈련 — P1
- **담당**: 병원 운영팀

### Rollback
- **상태**: Manual Procedure
- **근거**: `docs/CSHSP_Rollback_Guide.md`(Commit7-5, 21개 섹션)
- **운영 가능 범위**: Git/Netlify/GAS/Sheets/각 Portal 장애 대응 절차 문서화
- **제한사항**: 운영재개 승인권자 미확정(Decision Required), 실제 수행 리허설 없음(문서만)
- **미조치 시 위험**: 실제 장애 시 절차 검증 안 된 상태로 첫 실행
- **운영 전 필요 조치**: 승인권자 지정, 최소 1회 리허설 권장 — P1
- **담당**: PM

### 운영 FAQ
- **상태**: Confirmed(문서 존재)
- **근거**: `docs/CSHSP_Operation_FAQ.md`(Commit7-5, A-G 36개 Q&A)
- **운영 가능 범위**: 신규 직원 온보딩, 1차 문의 대응
- **제한사항**: 없음(문서 자체 한정)
- **미조치 시 위험**: —
- **운영 전 필요 조치**: 없음
- **담당**: —

### 배포 체크리스트
- **상태**: Confirmed(문서 존재, Sprint2~6 반영 갱신 완료)
- **근거**: `src/deploy/production_checklist.md`(Commit7-4, 9개 카테고리)
- **운영 가능 범위**: 배포 전 점검 항목 전체
- **제한사항**: 실제 배포 시 항목별 체크 수행 여부는 운영자 책임
- **미조치 시 위험**: 없음(문서 한정)
- **운영 전 필요 조치**: 없음
- **담당**: 배포 담당자

### 감사·운영 기록
- **상태**: Partially Implemented
- **근거**: FastAPI 경유 승인/거절은 `audit_logs.json` 기록. Legacy 경로는 감사 코드 0건(코드 검색 확인)
- **운영 가능 범위**: 승인/거절 이력 추적
- **제한사항**: Legacy 상태변경(변경/취소/완료/메모)은 추적 불가. 구조화 로깅(Python `logging`) 미사용, `stderr` 출력만
- **미조치 시 위험**: 사고 발생 시 원인 추적 곤란
- **운영 전 필요 조치**: Legacy 감사로그 추가(Phase B) 또는 최소 수동 기록 절차 — P1
- **담당**: PM

## 9. Google Sheets SSOT 상태

Confirmed. ADR-013 근거, 전 참조 문서(ARCHITECTURE.md, Rollback Guide, FAQ, Operation Readiness Assessment)에서 일관되게 인용됨. 충돌 없음.

## 10. FastAPI 적용 범위

Confirmed(제한적). 승인·거절·Policy 검증·Slot 처리에만 적용. 생성(Reservation Portal)과 변경/취소/완료(Legacy Portal)는 FastAPI를 경유하지 않는다 — "모든 Portal 기능이 FastAPI를 통과하는 구조는 아니다"라는 PM 명시 사실과 일치, 전 문서 표현 일관.

## 11. GAS v3/v4 구분

Confirmed(v3=운영본) / Decision Required(v4=미확인). `ARCHITECTURE.md`, `DEPLOY_GUIDE_new.md` §2-0, `CSHSP_Rollback_Guide.md` §8, `CSHSP_Operation_FAQ.md` Q4 전부 동일하게 "v3가 현재 배포본, v4 실사용 여부 미확인, 확인 없이 전환 금지"로 기술 — 교차검증 결과 **충돌 없음**.

## 12. Policy 및 Slot 처리 현황

승인 경로는 성숙(§8 참조). Legacy 경로는 Policy 미적용, Slot 취소 시 미반환 — Sprint4~6에서 구조적으로 확정된 사실이며 Sprint7에서 코드 변경 없이 문서화만 진행됨.

## 13. Legacy Stage3 Phase B 현황

**Design Only** — `Legacy_Stage3_PhaseB_Design_v1.0.md`(Commit7-3)와 `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md`(Draft 상태)로 TO-BE 구조 권고안이 작성되었으나, **구현은 전혀 착수되지 않았다**. Migration Plan(B-0~B-6) 중 B-0(설계)만 완료. B-1 이후는 Decision Required 항목(§16, 최소 8·9번) 결정 후 별도 PM 승인 필요.

## 14. 관리자 인증·인가 현황

인증: Not Implemented(Mock만 존재). 인가: RBAC 모델 정의·테스트 완료이나 `reservation:change`/`reservation:cancel` 권한은 정의만 있고 실제 시행 코드 없음. Sprint4~7 전 기간 동안 이 상태는 변하지 않았다 — Sprint7 원칙상(신규 기능 금지) 의도적으로 다루지 않은 것이며, **가장 중요한 잔여 위험**으로 전 문서(Operation Readiness Assessment, Legacy Stage3 Design, Rollback Guide, FAQ)에 반복 등록되어 있다.

## 15. 운영 문서 준비 현황

Commit7-4에서 기존 7종 문서(관리자 매뉴얼 성격의 DEPLOY_GUIDE, 장애대응 매뉴얼, 배포 체크리스트, 백업 정책)를 Sprint2~6 반영해 갱신 완료. Commit7-5에서 Rollback Guide·FAQ 신규 작성 완료. **문서 준비 자체는 Commit7-2 평가(55/100) 대비 크게 개선됐으나, 이는 문서 커버리지의 개선이며 시스템 자체의 운영 준비도 개선을 의미하지 않는다**(§15 문서 표현 원칙 — 문서 완성 ≠ 운영 준비 완료).

## 16. 배포·백업·장애·Rollback 준비 현황

배포: Manual Procedure(체크리스트 존재, 자동화 없음). 백업: Confirmed(로컬)/Manual(Sheets). 장애대응: Confirmed(문서, A-U 21개 유형). Rollback: Manual Procedure(문서 존재, 실제 리허설 미실시). 4개 영역 모두 **문서는 갖춰졌으나 실제 운영환경에서 검증된 적은 없다.**

## 17. 검증 및 테스트 통합 결과

Sprint7 전체(Commit7-0~7-5)는 문서 작업이므로 신규 테스트가 발생하지 않았다. Commit7-2에서 인용된 기존 회귀 스위트 실측 결과(2026-07-29 재확인)가 Sprint7 기간 동안의 최신 테스트 근거다: Commit2(68)/3(49)/3A(59)/5-1(29)/5-2(47) FastAPI 테스트 252개 PASS, Admin Portal Parser(58)/Legacy Guard(24)/TD Cleanup(12) 테스트 PASS, 백업·복구 리허설 9/9 PASS. 이 문서 작성 중 추가 테스트 실행 없음(코드 변경이 없어 재실행 대상 없음).

## 18. 잔여 위험

정성 등급(높음/중간/낮음)만 사용, 수치 산정 없음.

| 위험ID | 위험 내용 | 관련 구성요소 | 발생가능성 | 영향도 | 우선순위 | 현재 통제 | 잔여 위험 | 운영 전 필수조치 | 담당/결정주체 | 완료 기준 | 운영 차단 여부 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 관리자 인증·인가 미구현 | Admin Portal | 높음 | 높음 | Critical | 내부망 한정 접근 가정 | 매우 높음 | 실 인증 구현 | PM/전산담당 | 로그인 기능 배포·검증 | **차단**(전체 운영) |
| R2 | GAS 직접호출 인증·인가 부족 | GAS | 높음 | 높음 | Critical | Web App URL 비공개 운용 | 높음 | 직접호출 통제 방식 결정 | PM/전산담당 | 통제방식 구현 또는 URL 노출 재확인 절차 확정 | 조건부 제한 |
| R3 | Legacy 클라이언트 차단 우회 가능 | Legacy Portal, GAS | 중간 | 높음 | High | Commit6-1 UI 차단(예약확정만) | 높음 | R2와 동일 해결 필요 | PM | R2 완료 | 조건부 제한 |
| R4 | 잔여 상태전이(변경/취소/완료) 서버 검증 부족 | Legacy Portal | 높음 | 중간 | High | 없음 | 높음 | Phase B 착수 여부 결정 | PM | Decision Required #7/16 §16 결정 | 조건부 제한 |
| R5 | 예약변경이 실제 일정 미반영(라벨만 변경) | Legacy Portal | 확인됨(상시) | 중간 | High | 없음(사실로 고지만) | 중간 | 실제 요구사항 확정, 기능 재설계 | PM/병원운영팀 | Decision Required #1~3 결정 | 조건부 제한(수기 보완 필요) |
| R6 | GAS v3/v4 운영본 혼동 | GAS, 배포 절차 | 낮음 | 높음 | Medium | 문서 전체 v3 명시, 전환 금지 원칙 | 낮음 | v4 실사용 여부 확정 | PM/전산담당 | v4 상태 공식 확인 | 아니오 |
| R7 | Sheets 장애·데이터 오염 | Google Sheets | 낮음 | 높음 | High | 버전 기록 의존 | 중간 | 백업 정책 확정 | PM/개인정보책임자 | Decision Required(backup_policy §5-2) 결정 | 조건부 제한 |
| R8 | Slot 충돌·취소후 미반환 | Slot 관리 | 중간 | 중간 | High | 승인 경로만 검증 | 중간 | 정합성 점검 절차 운영 또는 B-2 착수 | PM/운영팀 | 정기 점검 절차 수립 | 조건부 제한 |
| R9 | Policy 오판정·차단 | Policy 검증 | 낮음 | 중간 | Medium | 승인 경로 테스트 성숙(252개) | 낮음 | 없음(모니터링만) | 운영팀 | — | 아니오 |
| R10 | FastAPI 장애·Timeout | FastAPI | 낮음 | 중간 | Medium | 8초 Timeout(Admin Portal만) | 낮음 | Legacy/Reservation Portal Timeout 추가(향후) | 향후 Commit | — | 아니오 |
| R11 | Netlify-GAS 배포 버전 불일치 | 배포 절차 | 중간 | 중간 | Medium | 수동 대조(체크리스트) | 중간 | 배포 시 이중 확인 절차 준수 | 배포담당자 | 체크리스트 서명 | 아니오 |
| R12 | 운영 연락망 미확정 | 조직/거버넌스 | 확인됨 | 중간 | High | 문서에 자리만 마련 | 중간 | 실제 담당자 지정 | 병원 | 연락망 문서 기입 완료 | 조건부 제한 |
| R13 | Rollback 실행 책임 미확정 | 거버넌스 | 확인됨 | 중간 | High | 문서 절차만 존재 | 중간 | 책임자 지정 | PM | 지정 완료 | 조건부 제한 |
| R14 | 운영재개 최종 승인권자 미확정 | 거버넌스 | 확인됨 | 높음 | Critical | 없음 | 높음 | 승인권자 지정 | PM | 지정 완료 | **차단**(장애 후 재개 시) |
| R15 | Sheets 백업 책임자 미확정 | 거버넌스 | 확인됨 | 중간 | High | 없음 | 중간 | 책임자 지정 | PM/개인정보책임자 | 지정 완료 | 조건부 제한 |
| R16 | 백업 보존기간 미확정 | 거버넌스 | 확인됨 | 낮음 | Medium | 로컬 JSON만 확정(30일/1년) | 중간 | Sheets 보존기간 결정 | PM | 결정 완료 | 아니오 |
| R17 | 복구 성공기준 미확정 | 거버넌스 | 확인됨 | 중간 | High | 로컬 JSON만 확정(validator 0건) | 중간 | Sheets 성공기준 결정 | PM | 결정 완료 | 조건부 제한 |
| R18 | 운영 인력 교육·실훈련 미완료 가능성 | 조직 | 확인 필요 | 높음 | High | 문서 준비만 완료 | 높음(미확인) | 실제 교육·리허설 수행 여부 확인 | 병원운영팀 | 교육 완료 기록 | 조건부 제한 |
| R19 | 운영 데이터 기반 E2E 검증 부족 가능성 | 전체 시스템 | 확인 필요 | 높음 | High | 코드 테스트는 두터움(252+), 실 운영데이터 검증 기록 없음 | 높음(미확인) | Staging/Pilot 환경 실데이터 검증 | PM/개발팀 | 검증 완료 보고 | 조건부 제한(Pilot 한정 권장) |
| R20 | 감사로그·추적성 부족 | Legacy Portal | 확인됨(상시) | 중간 | High | FastAPI 경로만 감사 | 높음 | Legacy 감사로그 추가(Phase B) 또는 수동 기록 | PM | Phase B 결정 또는 수동절차 수립 | 조건부 제한 |

## 19. 기술부채

| ID | 내용 | 상태 | 근거 |
|---|---|---|---|
| TD-S5-01 | `_extractDetailMessage()` 사용 안 하는 코드 | Resolved(Commit6-2) | ROADMAP.md |
| TD-S5-02 | Legacy 통계 카드 데이터소스 불일치 | Resolved(Commit6-2) | ROADMAP.md |
| TD-S5-03 | `nav_new.js` 오래된 링크 | Deferred → Commit7-7(P2) | PROJECT_STATUS.md |
| TD-S5-04 | Legacy 승인 우회(예약확정) | Partial Resolved(Commit6-1) — 나머지 3개 전이는 Legacy Stage3 Phase B 대상 | ARCHITECTURE.md §7-4 |
| TD-S5-05 | sprint3_rbac 테스트 CSV 스냅숏 카운트 변동 | Deferred, 결함 아님(정상 누적 확인됨) → Commit7-7 | PROJECT_STATUS.md |

Sprint7에서 신규로 등록된 기술부채는 없다(전부 설계/평가/문서 산출물이며 코드 변경이 없었으므로).

## 20. Decision Required 통합 목록

| 결정ID | 결정 필요사항 | 현재 상태 | 결정 필요 이유 | 미결정 시 영향 | 권장 결정주체 | 결정 필요 시점 | 관련 문서 | 임시 통제방안 |
|---|---|---|---|---|---|---|---|---|
| D1 | 운영재개 최종 승인권자 | 미확정 | 장애 복구 후 서비스 재개 판단 필요 | 재개 지연 또는 무단 재개 위험 | PM | Pilot 착수 전 | Rollback Guide §18 | 임시로 PM이 승인 |
| D2 | Rollback 결정권자 | 미확정 | Rollback 개시 판단 주체 필요 | 대응 지연 | PM | Pilot 착수 전 | Rollback Guide §2 | PM 임시 겸임 |
| D3 | Rollback 실행 책임자 | 미확정 | 실제 명령 수행 주체 필요 | 대응 지연 | PM/전산담당 | Pilot 착수 전 | Rollback Guide §2 | 개발 담당자 임시 겸임 |
| D4 | Sheets 백업 책임자 | 미확정 | 정기 백업 수행 주체 필요 | 백업 누락 위험 | PM/개인정보책임자 | 운영 착수 전 | backup_policy.md §5-2 | 없음(불가피 시 수동 사본만 임시 권고) |
| D5 | Sheets 복구 책임자 | 미확정 | 장애 시 복구 수행 주체 필요 | 복구 지연 | PM/전산담당 | 운영 착수 전 | backup_policy.md §5-2 | 없음 |
| D6 | 백업 주기 | 로컬 JSON만 확정(일 1회), Sheets 미확정 | Sheets는 버전기록 의존, 별도 주기 정책 없음 | 손실 범위 불명확 | PM | 운영 착수 전 | backup_policy.md §5-2 | Google 자체 버전기록에 잠정 의존 |
| D7 | 백업 보존기간 | 로컬 JSON만 확정(30일/1년), Sheets 미확정 | Workspace 관리자 설정에 따라 다름, 미확인 | 장기 복구 불가 가능 | PM | 운영 착수 전 | backup_policy.md §5-2 | 없음 |
| D8 | 복구 성공기준 | 로컬 JSON만 확정(validator 0건), Sheets 미확정 | 복구 완료 판정 기준 부재 | 불완전 복구 상태로 재개 위험 | PM | 운영 착수 전 | backup_policy.md §5-2 | 없음 |
| D9 | 실제 운영 연락망 | 미확정(문서에 자리만 마련) | 장애 시 신고 대상 특정 필요 | 보고 지연 | 병원 | 운영 착수 전 | Failure_Response_Manual §3 | 없음 |
| D10 | 장애 상위보고 체계 | P1/P2 기준은 문서화, 실제 보고 라인 미확정 | 누구에게 보고할지 불명 | 보고 누락 | PM/병원 | 운영 착수 전 | Failure_Response_Manual | PM 임시 단일 창구 |
| D11 | GAS 공식 재배포 절차 | 화면 조작 절차 [확인 필요] | Apps Script UI 직접 확인 필요, 문서화 안 됨 | 재배포 시 실수 위험(과거 미반영 사고 이력) | 전산담당 | Rollback 필요 시점 전 | Rollback Guide §8 | "새 버전"으로만 배포 원칙 준수 |
| D12 | GAS v4 전환 여부 | 미확정(v3 유지 중) | v4 실사용 여부 자체가 미확인 | 잘못된 버전 배포 위험 | PM/전산담당 | 전환 검토 시점 | ARCHITECTURE.md, DEPLOY_GUIDE_new.md §2-0 | 확인 전까지 v3 유지 |
| D13 | 관리자 인증·인가 구현 방식 | 미착수(Mock) | 실 로그인 방식(자체/SSO 등) 미정 | 보안 취약 상태 지속 | PM/전산담당 | 별도 Sprint 착수 전 | Operation_Readiness_Assessment §4 Gap#2 | 내부망 한정 운영으로 임시 완화 |
| D14 | GAS 직접호출 통제 방식 | 미착수 | Web App URL 노출 시 무인가 접근 가능 | 데이터 무단 접근/수정 위험 | PM/전산담당 | 별도 Sprint 착수 전 | Legacy_Stage3_PhaseB_Design §15 Risk | URL 비공개 운용(현재 유일한 통제) |
| D15 | Legacy 기능 종료 또는 전환 시점 | 미확정(Phase B B-1 이후 논의) | 3개 전이 기능의 Admin Portal 이관 여부/시점 | 무기한 이원화 지속 | PM | Phase B 착수 검토 시 | Legacy_Stage3_PhaseB_Design §14/17 | 현행 유지(Legacy 계속 사용) |
| D16 | 예약변경 기능의 실제 구현 방향 | 미확정(현재 라벨 변경뿐) | 실제 일정 변경 요구사항·Slot 재배정 규칙 미정 | 운영자가 "변경완료"로 오인할 위험 지속 | PM/병원운영팀 | Phase B B-3 착수 전 | Legacy_Stage3_PhaseB_Design §16 D1~D3 | FAQ/매뉴얼에 "라벨 변경뿐" 명확히 고지(완료됨, Commit7-4/7-5) |
| D17 | 운영 데이터 검증(E2E) 책임자 | 미확정 | Pilot 전 실데이터 기반 검증 주체 필요 | 미검증 상태로 운영 투입 위험 | PM/개발팀 | Pilot 착수 전 | 본 문서 §18 R19 | 없음 |
| D18 | 운영 재개 전 승인 체크리스트 서명 주체 | 미확정 | Rollback 완료 후 재개 승인 문서에 서명할 주체 필요 | 책임 소재 불분명 | PM | Pilot 착수 전 | Rollback Guide §21 | PM 임시 서명 |

**이 통합표에서 어떤 항목도 임의로 확정되지 않았다.**

## 21. 운영 전 필수조치

| 조치ID | 우선순위 | 조치 내용 | 근거 | 책임주체 | 선행조건 | 완료증빙 | 목표시점 | 미완료 시 운영 제한 |
|---|---|---|---|---|---|---|---|---|
| A1 | P0 | 관리자 실 인증 구현 | R1 | PM/전산담당(Decision Required, 담당 미정) | D13 결정 | 로그인 기능 배포·테스트 통과 | Decision Required(일정 미정) | 전체 운영 금지, 내부망 한정도 고위험 |
| A2 | P0 | GAS 직접호출 통제 방식 결정·적용 | R2/R3 | PM/전산담당(Decision Required) | D14 결정 | 통제 적용 확인 | Decision Required(일정 미정) | Legacy 우회 위험 지속 — Pilot도 고위험 |
| A3 | P0 | 운영재개 최종 승인권자 지정 | R14 | PM(Decision Required) | 없음(즉시 가능) | 문서 서명란 기입 | Decision Required(일정 미정) | 장애 후 재개 판단 불가 |
| A4 | P1 | Sheets 백업 정책 확정(D4~D8) | R7, R15~17 | PM/개인정보책임자(Decision Required) | 없음 | 정책 문서 확정 | Decision Required(일정 미정) | 제한 운영(수동 사본 대체) 가능 |
| A5 | P1 | 운영 연락망·상위보고 체계 확정(D9/D10) | R12 | 병원(Decision Required) | 없음 | 연락망 문서 기입 | Decision Required(일정 미정) | 제한 운영 가능(PM 단일 창구 임시) |
| A6 | P1 | Rollback 결정권자·실행책임자 지정(D2/D3) | R13 | PM(Decision Required) | 없음 | 지정 문서화 | Decision Required(일정 미정) | 제한 운영 가능(PM 임시 겸임) |
| A7 | P1 | 운영 데이터 기반 E2E 검증 수행 | R19 | PM/개발팀(Decision Required) | Staging 환경 준비 | 검증 결과 보고서 | Decision Required(일정 미정) | Pilot 한정 권장, 전체 운영 제한 |
| A8 | P1 | 운영 인력 교육·리허설 수행 | R18 | 병원운영팀(Decision Required) | 문서(FAQ/매뉴얼) 완료(완료됨) | 교육 완료 기록 | Decision Required(일정 미정) | 제한 운영 가능(경험자 한정) |
| A9 | P2 | Legacy Stage3 Phase B 착수 여부 결정 | R4/R5/R20 | PM(Decision Required) | D15/D16 결정 | 착수 승인 또는 보류 결정 | 다음 Sprint 후보 | 현행 유지 가능(제한적 위험 감수) |
| A10 | P2 | GAS v4 실사용 여부 공식 확인(D12) | R6 | 전산담당(Decision Required) | 없음 | 확인 결과 문서화 | 다음 Sprint 후보 | 현행 v3 유지로 회피 가능 |
| A11 | P2 | Netlify-GAS 버전 이중 확인 절차 정착 | R11 | 배포담당자 | 없음 | 배포 체크리스트 서명 이력 | 다음 배포부터 | 배포 시마다 수동 확인으로 대체 |
| A12 | P3 | TD-S5-03/05 정리 | — | 개발팀 | 없음 | Commit7-7 완료 | 다음 Sprint(Commit7-7) | 없음(경미) |

## 22. 운영 준비도 최종 판정

| 영역 | 판정 | 근거 | 충족된 조건 | 미충족 조건 | 운영 영향 | 필수 선행조치 |
|---|---|---|---|---|---|---|
| 기능 준비도 | CONDITIONALLY READY | 승인/거절 경로 매우 성숙(252 테스트), 나머지 3개 전이는 검증 없음 | 승인·거절·생성 경로 | 변경/취소/완료 서버검증 | 승인 중심 운영은 가능, Legacy 기능은 리스크 감수 필요 | A9 |
| 데이터 준비도 | CONDITIONALLY READY | Sheets SSOT 구조 명확, Slot 미반환 문제 존재 | 정상 흐름 데이터 정합성 | 취소 후 정합성 | 정기 수동 점검 필요 | A4, A9 |
| 보안 준비도 | **NOT READY** | 관리자 인증 미구현, GAS 무인증 확인 | RBAC 모델만 | 실 인증, GAS 접근통제 | 내부망 외부 유출 시 심각한 위험 | A1, A2 |
| 배포 준비도 | CONDITIONALLY READY | 체크리스트·가이드 정비 완료, 자동화 없음 | 수동 절차 문서화 | 자동 검증 | 사람 의존적, 절차 미준수 위험 | A11 |
| 장애 대응 준비도 | CONDITIONALLY READY | 21개 유형 문서화 완료, 실제 리허설 없음 | 절차 문서 | 실제 훈련 이력 | 최초 장애 시 절차 낯설 위험 | A8 |
| 백업·복구 준비도 | CONDITIONALLY READY | 로컬 JSON 확정·검증됨(9/9 PASS), Sheets 미확정 | 로컬 JSON 백업 | Sheets 백업 정책 | Sheets 손상 시 대응 지연 | A4 |
| 운영 인력 준비도 | **확인 필요(판정 보류)** | 문서는 준비됐으나 실제 교육·숙지 여부 확인 기록 없음 | 문서 자료 | 실제 교육 이력 | 미확인 상태로 운영 투입 시 위험 | A8 |
| 문서 준비도 | READY | 7종 기존 문서 갱신 + Rollback Guide/FAQ 신규, 교차검증 충돌 없음 | 전 영역 문서 커버 | 없음 | 없음 | — |
| 거버넌스·승인 준비도 | **NOT READY** | 승인권자/책임자 다수 미지정(D1~D5, D9, D10, D18) | Decision Required 항목화는 완료 | 실제 지정 | 장애 시 의사결정 지연 | A3, A5, A6 |

## 23. 전체 운영 준비도 최종 판정

**전체 판정: CONDITIONALLY READY (제한적 조건부) — 단, 보안 준비도(NOT READY)와 거버넌스 준비도(NOT READY)가 전체 판정을 제약한다.**

문서 준비도가 READY라는 사실이 시스템 전체의 운영 준비 완료를 의미하지 않는다. 특히 **관리자 인증 미구현(A1)과 GAS 직접호출 무인가 상태(A2)는 완화되지 않은 채 Sprint7 전 기간 유지**되었으며, 이는 Sprint7 원칙(신규 기능 금지)에 따라 의도적으로 다루지 않은 것이지 경미한 문제가 아니다. 이 두 조건이 해결되지 않은 상태에서 전체 운영(공개 접근 가능 환경)을 시작하는 것은 권장하지 않는다.

## 24. 조건부 운영 가능 범위

- **내부망 한정, 소수 인원(운영팀)만 접근하는 제한적 Pilot** — 승인/거절 중심 운영, Legacy 변경/취소/완료는 기존 방식대로 계속 사용(신규 위험 아님, 기존에도 사용 중이던 경로)
- 위 경우에도 A3(운영재개 승인권자), A5(연락망), A6(Rollback 책임자) 최소 지정 후 시작 권장

## 25. 운영 금지 또는 제한 범위

- **외부 공개 접근 가능한 형태의 전체 운영**: 인증 미구현(A1) 해결 전까지 금지
- **GAS Web App URL의 외부 노출 가능성이 있는 환경**: 통제 방식(A2) 결정 전까지 제한
- **Sheets 백업 정책 미확정 상태에서의 대량 데이터 처리**: A4 완료 전까지 제한(대규모 일괄 처리는 수동 사본 후 진행 권고)

## 26. 다음 Sprint 진입조건

다음 Sprint는 아래 항목이 PM 승인을 받기 전까지 시작하지 않는다.

- Sprint7 Closeout PM 승인
- P0 위험(R1, R2, R14) 처리방향 승인
- 관리자 인증·인가 구현 우선순위 결정
- GAS 직접호출 통제 방향 결정
- GAS v3 운영본 공식 확인(및 v4 사용 여부 결정)
- Legacy 상태전이 전환 범위 승인(D15)
- 실제 예약변경 기능 요구사항 확정(D16)
- Sheets 백업·복구 정책 확정(D4~D8)
- 운영 책임자 및 연락망 확정(D9, D1~D3)
- 운영환경 검증 계획 승인(A7)
- Pilot 범위 및 성공기준 승인
- Push·Deploy 별도 승인

## 27. 다음 Sprint 권장 우선순위

실제 저장소 근거(§18 위험 순위)에 따른 제안이며, 착수는 하지 않는다.

1. **Security & Authorization Hardening** — R1(관리자 인증), 가장 높은 위험도
2. **GAS Direct-call Control** — R2/R3, 두 번째로 높은 위험도이자 여러 다른 위험(R4/R5)의 전제조건
3. **Legacy Transition Server Validation** — R4/R20, Legacy Stage3 Phase B B-1~B-2 착수 검토
4. **Real Reservation Rescheduling** — R5/D16, 실제 요구사항 확정 후 설계
5. **Backup/Recovery Operationalization** — R7/R15~17, Sheets 백업 정책 실행
6. **Staging E2E & Pilot Readiness** — R18/R19, 실제 검증·교육 수행

## 28. Sprint7 종료 승인조건

- 본 문서(§22~23)의 판정 내용을 PM이 확인
- §21 P0 조치(A1~A3)의 처리 방향(즉시 착수 / 조건부 Pilot로 진행 / 보류)에 대한 PM 결정
- §26 다음 Sprint 진입조건 승인
- 이 문서 자체의 Commit(본 Commit7-6) 승인

## 29. 최종 결론

Sprint7("Operation Readiness Sprint")은 계획된 6개 Commit(7-0~7-5) 전부를 완료했다. 목표했던 "운영 준비를 위한 문서·절차·평가 정비"는 실질적으로 달성되었다 — 평가(Commit7-2), 설계(Commit7-3), 문서 현행화(Commit7-4), Rollback/FAQ(Commit7-5)까지 실측 근거를 기반으로 일관되게 작성되었으며 상호 교차검증에서 충돌이 발견되지 않았다.

그러나 Sprint7의 산출물은 **문서와 설계에 한정**되며, Sprint7 시작 시점부터 존재했던 두 가지 근본 위험 — **관리자 실 인증 미구현**과 **GAS 직접호출 무인가 상태** — 는 Sprint7 원칙(신규 기능 금지)에 따라 의도적으로 해결되지 않은 채 그대로 남아 있다. 따라서 Sprint7의 완료가 곧 "운영 준비 완료"를 의미하지 않으며, 전체 판정은 **CONDITIONALLY READY**(제한적 조건 하에서만)로 제한한다.

## 30. 승인·결정 기록란

| 항목 | 결정 | 결정자 | 일자 | 비고 |
|---|---|---|---|---|
| Sprint7 Closeout 승인 여부 | (미기입) | | | PM 확인란 |
| P0 조치(A1~A3) 처리 방향 | (미기입) | | | |
| 다음 Sprint 착수 승인 | (미기입) | | | |
| 기타 | | | | |

---

## 교차검증 결과 (Section 17 절차)

1. Commit7-0~7-5 산출물 반영 여부: 전 6개 Commit §7 표에 반영 — 확인.
2. 실제 Commit Hash와 문서 표기 일치: `git log --oneline`으로 재확인, 7개 전부 일치.
3. Google Sheets SSOT 일관성: 전 문서 일치, 충돌 없음.
4. Portal별 역할 일관성: 3-Portal 역할 구분 전 문서 일치.
5. FastAPI 적용 범위 일관성: "일부 기능만 경유" 원칙 전 문서 일치.
6. GAS v3/v4 구분 일관성: 일치, 충돌 없음(§11).
7. Policy/Slot 처리 현황: Operation Readiness Assessment §3-1/3-4와 일치.
8. Legacy 제한사항: Commit7-3/7-4/7-5 서술과 본 문서 §8 일치, 누락 없음.
9. 관리자 인증·인가 제한사항: 전 문서 "Mock/미구현"으로 일관.
10. 장애대응 절차: Failure_Response_Manual A-U 21개 유형 §8 반영.
11. 백업·복구 정책: backup_policy.md §5 Decision Required 항목 그대로 인용, 임의 확정 없음.
12. Rollback 절차: Rollback Guide 21개 섹션 구조 §8/§16 반영.
13. 운영재개 승인 Gate: D1/A3로 일관 반영.
14. Decision Required 항목: 18개 항목 통합, 원 문서 대비 누락 없음(교차 대조 완료).
15. 배포 상태: Manual Procedure로 일관.
16. Push 상태: 미실시로 본 문서 전체 일관.
17. 운영 준비도 판정 근거: §22 각 영역에 근거 명시.
18. 다음 Sprint 진입조건: §26에 명시, PM 승인 전 착수 안 함.
19. 미구현 기능의 잘못된 완료 표시 여부: 재검토 결과 없음(전 항목에서 Not Implemented/Design Only/Decision Required 명확히 구분).
20. 문서 간 충돌 여부: **발견된 충돌 없음.**

## 대상 밖 발견사항

이번 통합 작업 중 범위 밖 문제는 발견되지 않았다. `docs/RELEASE_READINESS_REPORT_v0.9.0.md`, `PILOT_READINESS_REVIEW.md`(둘 다 untracked, Sprint H~Sprint2 시절 문서로 추정)는 이번 참조 대상에 포함되지 않았으며 — Sprint7 범위(Commit7-0~7-5 산출물과 PM 지정 참조문서)를 벗어나므로 이번 Commit에서 검토·수정하지 않았다. 필요 시 별도 검토를 제안한다(임의 처리하지 않음).

## 완료 조건 준수 확인

이 문서 작성 중 어떤 코드·설정·API·Business Rule·Google Sheets 구조·운영 데이터도 변경하지 않았다. 신규 테스트를 실행하지 않았으며, 기존 문서(Commit7-0~7-5 산출물 포함)를 수정하지 않고 인용만 했다. `ADR-015_Slot_Status_Policy_Draft.md`와 `tests/sprint3_rbac_test_result.csv`는 읽지 않았으며 전혀 참조하지 않았다. Push, Deploy, 다음 Sprint 착수 없음. Sprint7의 최종 종료는 이 문서가 아니라 PM 승인으로 확정된다.
