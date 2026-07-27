# Sprint 3 Final Report v1.0 — Operator First

- 대상: Single Admin Portal(`app/pages/admin_portal_new.html`) + `src/api/routes_admin_portal.py`
- 기간: Sprint 3(Commit 1~6)
- 작성: Commit 6(Final Integration QA) 종료 시점
- 승인 근거: PM FINAL APPROVAL(Sprint 3 Development Start) — P1=RBAC, P2=CRM통합, P3=Audit, P4=AI지원, P5=운영자UX, P6=통합QA

## 1. Sprint 목표 대비 결과

| PM 우선순위 | 목표 | Commit | 결과 |
|---|---|---|---|
| P1 | RBAC(전 엔드포인트 Authentication→RoleCheck→Endpoint) | Commit 1(`803ada9`) | 완료 |
| P2 | CRM 통합(신규 생성 아님, 상태전이 OPEN→IN_PROGRESS→CLOSED만) | Commit 2(`382f06b`) | 완료 |
| P3 | Audit Log 연결(기존 `GET /api/audit-logs` 재사용) | Commit 3(`af8b942`) | 완료 |
| P4 | AI 상담 지원 기반(기존 `GET /api/dashboard/ai` 재사용) | Commit 4(`101940f`) | 완료 |
| P5 | 운영자 UX 개선(헤더 사용자 표시/토스트/Enter 조회) | Commit 5(`36cd11f`) | 완료 |
| P6 | 통합 QA | Commit 6(본 커밋) | 완료 |

## 2. Commit 이력

| Commit | 해시 | 요약 |
|---|---|---|
| 1 | `803ada9` | RBAC — `_has_permission()`/`_build_require_permission()` 도입, 기존 4개 엔드포인트(dashboard/reservations/detail/statistics)에 권한 검사 연결 |
| 2 | `382f06b` | CRM 통합 — `GET /api/admin/consultations`, `POST /api/admin/consultations/{id}/status`(순차 전이만), 3단계 이름 마스킹(Operator/Supervisor/Admin) |
| 3 | `af8b942` | Audit Log — Portal이 기존 `GET /api/audit-logs`를 직접 호출하도록 프론트엔드만 연결, 신규 백엔드 없음 |
| 4 | `101940f` | AI 상담 지원 기반 — Portal이 기존 `GET /api/dashboard/ai`를 직접 호출, 신규 백엔드 없음 |
| 5 | `36cd11f` | 운영자 UX — 헤더 사용자 배지, 토스트 알림(alert 대체), 3곳 Enter 키 즉시 조회 |
| 6 | (본 커밋) | 통합 QA — 전체 회귀 스위트 재검증 + 4역할×6탭 브라우저 시나리오 + 마무리 문서 |

## 3. PM 결정사항 이행 확인

1. **CRM은 통합만, 신규 생성 아님** — 기존 `data/crm.json` 재사용, 상담 생성/삭제 API 없음(코드에 존재하지 않음, 정적 검사로 확인).
2. **CRM 쓰기 범위 = 순차 상태전이만** — `_CRM_STATUS_ORDER`로 OPEN→IN_PROGRESS→CLOSED 외 전이 시 409. 예약 수정/삭제, 고객정보 수정 API 없음.
3. **우선순위 P1=RBAC,P2=CRM,P3=Audit,P4=AI,P5=UX** — Commit 순서로 그대로 이행.
4. **마스킹 정책** — `summary`는 항상 원문 표시, 이름은 `_crm_masking_tier()`로 3단계(Operator 마스킹/Supervisor 전체이름/Admin 원문) 적용. 브라우저 QA로 ROLE-CRM(Operator)="테○○○", ROLE-DIRECTOR(Supervisor)="테스트김" 확인. ROLE-ADMIN 계정이 현재 데이터셋에 없어 Admin 티어는 코드 경로 검토로 확인(Supervisor와 동일하게 마스킹 미적용 분기, Sprint 3 전체 기간 동일 조건).
5. **Audit Log 신규 백엔드 금지** — `git diff --name-only HEAD` 기준 Commit 3에서 프로덕션 `.py` 변경 0건, 이번 통합 QA에서도 재확인.
6. **AI 상담 지원 신규 백엔드 금지** — Commit 4에서 프로덕션 `.py` 변경 0건, 재확인.
7. **Authentication→RoleCheck→Endpoint 순서** — `_build_require_permission()`이 `_build_require_user()`를 `Depends()` 체이닝, 401(인증)이 403(권한)보다 항상 우선 발생함을 RBAC 테스트 및 브라우저 시나리오로 재확인.

## 4. 최종 검증 결과

### 4.1 자동화 회귀(전체)
`tests/run_sprint3_full_regression_summary.py` 실행 — 총 20개 스위트(기존 Sprint A/B/D/E/F/G/H/I + Sprint 1~3 전체) 중 **순수 PASS 18, 기존 알려진 결함(Sprint 3 무관 확인) 2, 미확인 FAIL 0**.
- FAIL 2건은 Sprint 1 Commit 4에서 이미 진단된 사전 존재 결함(Sprint G 문진 스키마 이슈, Sprint I 콘솔 cp949 인코딩 버그)이며 Sprint 3 코드와 무관함을 이번에도 재확인.
- 결과 CSV: `tests/sprint3_full_regression_summary.csv`

### 4.2 Sprint 3 신규 테스트(누계)
| 구분 | 파일 | 건수 |
|---|---|---|
| RBAC | `tests/run_sprint3_rbac_qa.py` | 22 PASS |
| CRM 통합 | `tests/run_sprint3_crm_qa.py` | 49 PASS |
| Audit | `tests/run_sprint3_audit_qa.py` | 13 PASS |
| AI 상담 지원 | `tests/run_sprint3_ai_support_qa.py` | 18 PASS |
| 운영자 UX | `tests/run_sprint3_ux_qa.py` | 28 PASS |
| **합계** | | **130 PASS / 0 FAIL** |

### 4.3 브라우저 통합 시나리오(임시 uvicorn:8600 + http.server:4000, 샌드박스 데이터, 종료 후 삭제)
4개 역할(DIRECTOR/STAFF/CRM/AI-AGENT) × 6개 탭(Dashboard/예약조회/통계/상담관리/감사로그/AI지원) 전수 조합을 실제 UI 클릭·조회로 검증.

- **DIRECTOR**(dashboard/statistics/reservation/audit:view): 상담관리·감사로그 정상 조회, CRM 이름 전체표시(Supervisor 티어) 확인.
- **STAFF**(reservation/dashboard:view): 통계 403, 상담관리 403(crm:manage/crm:log/audit:view 없음), 감사로그는 reservation:view로 200(기존 로직 그대로) — 모두 기대값과 일치.
- **CRM**(reservation/crm:manage 등): Dashboard 403, 통계 403, 상담관리 정상(이름 마스킹 "테○○○" 확인).
- **AI-AGENT**(reservation:request만 보유): Dashboard/통계/예약조회/감사로그 전부 403, 상담관리는 200(crm:log 보유), AI지원은 제한 없이 200 — 모두 기대값과 일치.
- CRM 상태변경: ROLE-CRM으로 OPEN→IN_PROGRESS 성공 시 초록 토스트, ROLE-DIRECTOR(crm:manage 없음)로 시도 시 alert 없이 빨간 토스트로 권한 거부 메시지 표시.
- 예약조회/감사로그 Enter 키 즉시 조회 — 네트워크 요청으로 정상 파라미터 전달 확인.
- 예약조회 실데이터는 Sheets(GAS) 연동 미설정(`CSHSP_GAS_WEBAPP_URL` 미설정, 세션 전체 정책상 의도적으로 설정 안 함)으로 503 — 설계된 동작이며 결함 아님.
- 전 과정 브라우저 콘솔 오류 0건.
- 세션 종료 후 임시 서버 프로세스 강제 종료, 샌드박스 데이터 삭제 완료. 운영 데이터/실 Sheets 접근 없음.

## 5. 알려진 제약(결함 아님, 설계된 범위)

- 예약 목록/상세는 GAS(Google Sheets) 연동이 필요하며, 이 프로젝트 전체 정책상 `CSHSP_GAS_WEBAPP_URL`을 세션 중 설정하지 않으므로 Portal에서 실데이터 없이 503만 재현 가능(기존 Sprint 1부터 동일).
- CRM 이름 마스킹 Admin 티어는 현재 활성 사용자 데이터셋에 ROLE-ADMIN 계정이 없어 브라우저로 직접 재현하지 못했으며, 코드 분기(`_crm_masking_tier` → `"admin"` → 마스킹 미적용)로 확인함.
- Portal은 여전히 조회 중심이며, CRM 상태전이 외의 쓰기 기능(예약 승인/거절/취소 등)은 이 Sprint 범위에 포함되지 않음(기존 관리자 화면이 계속 담당).

## 6. Push / Deploy / 운영데이터 변경

Sprint 3 전 Commit(1~6)에 걸쳐 push, deploy, 운영 데이터(실 Google Sheets, 운영 `data/` 원본) 변경 없음. 모든 자동화 테스트는 `shutil.copytree`로 생성한 샌드박스 데이터만 사용했고, 브라우저 QA도 임시 서버 + 샌드박스 조합으로 수행 후 즉시 정리했다.
