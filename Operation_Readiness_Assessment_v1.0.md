# Operation Readiness Assessment v1.0

> **기준선(Baseline)**: `bccd04c` — `docs: synchronize project ssot documents` (Sprint7 Commit7-1)
> **작성일**: 2026-07-29
> **목적**: 현재 시스템이 실제 천안의료원 운영환경에 투입 가능한 수준인지 실제 코드·문서·테스트를 기준으로 객관적으로 평가한다. 구현 없음, 추측 없음.

---

## 1. 평가 목적

Sprint4~6에서 완성된 예약 승인/Slot/Policy 기능이 신규 개발이 아니라 **실제 운영 투입 가능 여부** 관점에서 얼마나 준비됐는지 측정한다. 평가 결과는 Commit7-3(Legacy Stage3 Phase B 설계)·7-4~7-6(운영 문서/Pilot 준비)의 우선순위를 정하는 근거가 된다.

## 2. 평가 기준

각 항목을 다음 3가지 증거로만 판단한다(추측 금지).
1. **실제 코드**(존재 여부, 호출 경로, 테스트 커버리지)
2. **실제 문서**(존재 여부, 최신성 — 이 세션에서 실제로 열어 확인)
3. **실제 테스트 결과**(재실행 또는 최근 확정된 결과 인용, 날짜/Commit 명시)

---

## 3. 평가 결과

### 3-1. ① 운영 절차

| 절차 | 현재 구현 | 검증 상태 |
|---|---|---|
| 예약 생성 | `reservation_v3_new.html` → GAS `action=create` 직접 호출(FastAPI 미경유) | DEV-003/DEV-004 시절 테스트, Sprint H 회귀 스위트로 간접 커버 |
| 예약 승인 | Admin Portal → FastAPI `/api/admin/reservations/{no}/approve` → Slot 점유+Policy 검증(휴진일/의료진/검사실/장비/프로그램 제한)+Audit | **매우 성숙** — Commit2(68)/3(49)/3A(59)/5-1(29)/5-2(47) = 252개 테스트 PASS(2026-07-29 최종 재확인), 실제 브라우저 QA 13개 시나리오 완료(Commit5-3.2) |
| 예약 거절 | Admin Portal → FastAPI `/api/admin/reservations/{no}/reject` | 위 테스트 스위트에 포함, 성숙 |
| **예약 변경(일정변경)** | Legacy Portal `#statusSel` 드롭다운 직접 선택 → Sheets 직접 쓰기 | **FastAPI 검증 전무** — `reservation_approval_states.py`가 원래부터 "이 전이는 Legacy가 전담"으로 설계(§4 코드 인용). 전용 자동화 테스트 없음(Commit6-1 가드 테스트에서 "무영향 확인"용으로만 간접 커버) |
| **예약 취소** | 위와 동일 경로 | 위와 동일 — 검증·전용 테스트 없음 |
| **검진 완료** | 위와 동일 경로 | 위와 동일 — 검증·전용 테스트 없음 |
| 운영자 업무 흐름 | Admin Portal(승인/거절/대시보드/통계/상담관리/감사로그/AI지원) + Legacy Portal(그 외 상태변경/메모/CSV) 이원화 | Admin Portal은 Parser(`parseApiError`)+8초 Timeout까지 갖춤(Commit5-3.2), Legacy Portal은 Timeout 0건, 오류 형식이 옛 `{ok,error}` 그대로 |

**핵심 발견**: 6개 예약 상태 전이 중 3개(승인/거절/생성)는 성숙, 3개(변경/취소/검진완료)는 **FastAPI 검증도 전용 테스트도 없다** — `roles.json`에는 `reservation:change`/`reservation:cancel` 권한 문자열이 이미 정의돼 있으나(ROLE-STAFF) 이를 실제로 검사하는 FastAPI 엔드포인트는 존재하지 않는다(코드 검색으로 확인, 권한 모델이 구현보다 앞서 있음).

### 3-2. ② 시스템

| 항목 | 평가 |
|---|---|
| 데이터 흐름 | Sheets-직접 경로(생성/Legacy 쓰기)와 FastAPI-경유 경로(승인/거절)가 구조적으로 분리(ADR-013). 이중 백엔드 리스크는 예약 확정 전이에 한해서만 Sprint6 Commit6-1로 완화됨(ARCHITECTURE.md §7-4) |
| Cache 구조 | 서버측 캐시 없음(매 요청 Sheets 재조회). 클라이언트측: Admin Portal은 매 조회 시 재요청(캐시 없음), Legacy Portal은 `this.cache`(메모리, `loadAll()` 시점 전체 스냅샷, TD-S5-02로 통계 카드도 이 캐시 사용하도록 통일됨). 규모가 작은 단일 병원 운영에는 무리 없으나 별도 캐시 무효화 정책은 없음 |
| Sheets 연계 | GAS `_actionList()`가 페이지네이션 없이 전체 반환 확인(코드 재확인, Commit6-2에서 활용). LockService로 쓰기 직렬화 |
| 오류 처리 | Backend가 4가지 형식(순수 문자열/`{code,message}`/Pydantic 배열/`{verdict,reasons}`)을 혼용(Sprint5 Design Freeze §2-1에서 이미 정리). Admin Portal은 `parseApiError()`로 표준화(Commit5-3.1/5-3.2), **Legacy/Reservation Portal은 여전히 표준화 안 됨**(구 `{ok,error}` 계약, `alert()`/자체 `toast()`) |
| Timeout 처리 | Admin Portal: 8초 AbortController(Commit5-3.2). **Legacy Portal·Reservation Portal: Timeout 처리 전무**(코드 검색 재확인, `AbortController` 0건) |

### 3-3. ③ 운영 환경

| 항목 | 평가 |
|---|---|
| Backup | `src/deploy/backup_policy.md`(Sprint H) 존재 — **로컬 JSON `data/`만 대상, Google Sheets는 다루지 않음**(파일 전체에 GAS/Sheets 언급 0건, 코드 검색 확인) |
| Restore | `tests/run_backup_restore_rehearsal.py` **실제 재실행 결과 9/9 PASS**(2026-07-29, 이번 평가에서 직접 실행) — 단 로컬 JSON 대상, Sheets 복구 절차는 별도로 없음(Google 자체 버전 기록에 암묵적으로 의존 중이나 문서화된 정책 없음) |
| Release | `src/deploy/production_checklist.md`(Sprint H, 47줄, A~F 6개 섹션 — 인프라/환경변수/데이터/기능검증/운영준비/일일점검) 존재. `PROJECT_STATUS.md` §2-1에 v1.0.0-pilot(2026-07-12) 시점 Release Checklist 결과도 존재. **둘 다 Sprint2~6(Admin Portal/Slot/Policy/Approval API) 반영 안 됨** — `CSHSP_GAS_WEBAPP_URL` 환경변수(FastAPI가 Sheets에 접근하는 필수 값)가 이 문서들 어디에도 언급되지 않음(코드 검색으로 재확인, 실제로 FastAPI가 이 값을 요구함) |
| Rollback | **독립 문서 없음**(파일 검색으로 확인, "Rollback"/"롤백" 이름의 문서 0건). Git 기반 커밋 되돌리기는 가능(ADR-012)하나 GAS 버전 롤백·Sheets 데이터 롤백 절차는 문서화되지 않음 |

### 3-4. ④ 보안

| 항목 | 평가 |
|---|---|
| 권한(RBAC) | `roles.json` 5개 역할(DIRECTOR/ADMIN/STAFF/CRM/AI-AGENT), `_has_permission()` 기반. Sprint3 Commit1에서 전 엔드포인트 도입, 정적 검사로 재확인됨(throwIfForbidden 호출 10곳). **단, `reservation:change`/`reservation:cancel` 권한은 정의만 있고 실제로 검사하는 엔드포인트가 없음**(§3-1과 동일 근거) |
| 인증 | **Mock만 존재**(`X-User-Id` 헤더 + `users.json` 조회, 실 로그인 없음) — `ARCHITECTURE.md` §6/`production_checklist.md` §B 양쪽 모두 "운영 전 필수(미구현)"으로 일관되게 기록됨. Sprint4~7 어느 기간에도 구현되지 않음(범위 밖 유지) |
| 감사 가능성 | FastAPI 경유 승인/거절은 `audit_logs.json`에 전부 기록(`RESERVATION_APPROVED`/`REJECTED`/`SLOT_FULL`/`SLOT_RELEASED` 등). **Legacy Portal의 상태변경(변경/취소/검진완료/메모 저장)은 감사로그에 전혀 남지 않음**(`admin_reservations_v2_new.html`/`google_sheets_service_v2_new.js`/`sheets_api_v3_final.gs` 전부에서 `audit` 관련 코드 0건, 코드 검색 확인) |
| 운영 로그 | Sprint4 Commit5-2의 `_server_log()`가 Policy 실패를 `stderr`에 출력하나, **구조화 로깅 프레임워크(Python `logging` 모듈 등) 사용례가 이 코드베이스 전체에 없음**(Commit3A 조사에서 이미 확인된 사실 재확인). 로그 수집·보존·로테이션 정책 문서 없음(백업 로그 `tools/logs/backup.log`는 백업 전용, 애플리케이션 로그와 무관) |

### 3-5. ⑤ 운영 문서

| 문서 | 존재 여부 | 최신성 |
|---|---|---|
| 관리자 매뉴얼 | **부분 존재** — `docs/DEPLOY_GUIDE_new.md`(416줄, GAS/Netlify 배포+Pilot 테스트 절차)가 있으나 대시보드 중심이며 Admin Portal/승인 기능은 다루지 않음 | Sprint2(Dashboard v3)/DEV-003 시절, Sprint4~6 미반영 |
| 장애 대응 | **존재** — `docs/CSHSP_Failure_Response_Manual.md`(62줄, API서버 무응답/데이터손상/채팅오류/AI이상응답/알림미발송/RateLimit/포트충돌 7개 시나리오) | Sprint H 시절, **GAS/Sheets 관련 시나리오 0건**(코드 검색 확인) — 새 장애 유형(Sheets 연동 끊김, Policy 검증 실패 등) 없음 |
| FAQ | **없음**(파일 검색으로 확인, 프로젝트 전체에 "FAQ" 이름의 문서 0건) |  |
| 체크리스트 | **존재 다수** — `src/deploy/production_checklist.md`, `docs/CSHSP_Pilot_Daily_Checklist.md`(46줄), `docs/CSHSP_Pilot_Stop_Criteria.md`(39줄), `docs/CSHSP_GoLive_Decision_Criteria.md`(44줄) | 전부 Sprint H 시절, Sheets/GAS/Admin Portal 언급 0건 |

**핵심 발견(이번 평가의 가장 중요한 정정)**: Sprint7 Design Freeze v1.0(§4-2)에서 "운영 문서가 대부분 없다"고 전제했던 것은 **부정확했다**. 실제로는 Sprint H 시절 작성된 실질적 운영 문서 7종(총 663줄 이상)이 이미 존재한다. 문제는 "문서 부재"가 아니라 **"Sprint2~6(Google Sheets SSOT 전환, Admin Portal, Slot/Policy, 승인 API)이 이 문서들에 전혀 반영되지 않았다"**는 것이다 — `CSHSP_GAS_WEBAPP_URL`이라는, FastAPI가 실제로 요구하는 필수 환경변수가 배포 문서 어디에도 등장하지 않는 것이 대표 증거다. Commit7-4/7-5는 "신규 작성"이 아니라 **"기존 7종 문서의 Sheets/Admin Portal 반영 갱신"**으로 재정의해야 한다.

---

## 4. Gap Analysis

| # | 영역 | 현재 수준 | 목표 수준 | 부족한 부분 | 권장 작업 | 우선순위 |
|---|---|---|---|---|---|---|
| 1 | 운영 절차 | 예약변경/취소/검진완료가 FastAPI 검증·감사·전용 테스트 전무, Legacy 직접 Sheets 쓰기 | 최소한 감사로그 확보 또는 Admin Portal 기능 흡수 | Admin Portal에 대응 기능 없음(Sprint6 Design Freeze §1-1에서 이미 확인된 구조적 이유) | Commit7-3(Legacy Stage3 Phase B **설계**)에서 정식 다룸 | **Critical** |
| 2 | 보안 | 관리자 인증이 Mock(X-User-Id 헤더)뿐 | 실 로그인/세션 인증 | 신뢰 경계가 내부망에만 의존 | Sprint7 범위 밖(신규기능 금지) — 위험으로 문서화만, 별도 Sprint 필요성 명기 | **Critical** |
| 3 | 운영 문서 | 기존 7종 문서가 Sheets/GAS/Admin Portal 전혀 반영 안 됨(`CSHSP_GAS_WEBAPP_URL` 미언급 등) | Sprint2~6 반영된 최신 배포·장애대응 문서 | 배포 시 필수 환경변수 누락 위험 | Commit7-4/7-5에서 기존 문서 **갱신**(신규 작성 아님) | **Critical** |
| 4 | 시스템 | Legacy/Reservation Portal Timeout 처리 없음 | Admin Portal 수준(8초 AbortController) | 네트워크 무응답 시 무기한 대기 가능 | 코드 변경은 Sprint7 범위 밖 — Gap으로 기록, 향후 Portal 개선 Commit 후보 등록 | High |
| 5 | 운영 환경 | Rollback 절차 독립 문서 없음 | GAS 버전/FastAPI 커밋/Sheets 데이터 각각의 롤백 절차 문서화 | 장애 시 대응 지연 위험 | Commit7-5(Rollback Guide 신규) | High |
| 6 | 운영 환경 | Sheets 백업 정책 없음(로컬 JSON만 커버) | Sheets 버전 이력 활용 정책 명문화 | Sheets 데이터 손상 시 복구 근거 부재 | Commit7-5(Backup 정책 보강) | High |
| 7 | 보안 | 구조화 로깅 없음(print/stderr만) | 최소한 로그 수집·보존 정책 문서화 | 장애 원인 추적 어려움 | Commit7-4(장애 대응 매뉴얼 갱신 시 "현재는 stderr뿐" 명시) | Medium |
| 8 | 운영 환경 | Release Checklist가 2026-07-12 시점 것만 존재 | Sprint4~6 반영된 최신 Checklist | 신규 기능(승인/Slot/Policy) 배포 검증 항목 없음 | Commit7-5(Release Checklist 독립 문서화) | Medium |
| 9 | 운영 문서 | FAQ 없음 | 운영자 대상 자주 묻는 질문 정리 | 신규 직원 온보딩 자료 부재 | Commit7-4에서 함께 작성 검토 | Medium |
| 10 | 기술부채 | TD-S5-03(`nav_new.js` 오래된 링크)/TD-S5-05(테스트 CSV 스냅숏) | 해소 | — | Commit7-7(이미 계획됨) | Low |
| 11 | 운영 환경 | 장애 대응 매뉴얼의 "연락망" 섹션이 Sprint H부터 공란 | 실제 담당자 지정 | 운영 조직 정보는 코드 밖 정보 | 운영 착수 시점에 병원 측 지정 필요(문서에 자리만 마련, 이번엔 채울 수 없음) | Low |

---

## 5. Operation Readiness Checklist

### 5-1. Backend/FastAPI/Sheets 연결
- [ ] `CSHSP_GAS_WEBAPP_URL` 운영 서버 환경변수 설정 확인(현재 어떤 배포 문서에도 명시 안 됨 — Gap #3)
- [x] Backend 6개 회귀 스위트 PASS(2026-07-29 최종 재확인: Commit5-2 47/47, Commit3A 59/59, Commit3 49/49, Commit2 68/68, Commit5-1 29/29, SprintB 38/38)
- [x] Admin Portal Parser/Legacy Guard/TD Cleanup 테스트 PASS(Parser 58/58, Legacy Guard 24/24, TD Cleanup 12/12)
- [ ] Apps Script 배포 버전이 최신인지 확인("새 버전" 배포 원칙 — STEP1.5 사고 재발 방지)

### 5-2. 관리자 권한/인증
- [x] RBAC 역할·권한 매핑(`roles.json`) 존재 및 테스트됨
- [ ] `reservation:change`/`reservation:cancel` 권한이 정의만 있고 실제 사용처 없음 — 운영 전 정리 또는 제거 여부 결정 필요
- [ ] 관리자 실 인증(로그인) — **미구현, Sprint7 범위 밖**(Critical Gap #2, 별도 Sprint 필요)
- [ ] 더미 계정(USR-0001~0003) 정리 여부 결정

### 5-3. Backup/Restore/Rollback
- [x] 로컬 JSON Backup/Restore 리허설 PASS(9/9, 2026-07-29 실행)
- [ ] Sheets 백업 정책 문서화(Gap #6)
- [ ] Rollback Guide 작성(Gap #5)

### 5-4. Release
- [ ] Release Checklist Sprint4~6 반영 갱신(Gap #8)
- [ ] Release Note 확인(Sprint4~7 각 Closeout Report 존재 — `Sprint6_Closeout_Report_v1.0.md` 등)

### 5-5. 운영 문서
- [ ] `docs/DEPLOY_GUIDE_new.md`, `docs/CSHSP_Failure_Response_Manual.md`, `src/deploy/production_checklist.md` 등 기존 7종 Sheets/Admin Portal 반영 갱신(Gap #3, #7)
- [ ] FAQ 작성(Gap #9)
- [ ] 담당자 연락망 실제 기입(Gap #11, 운영 착수 시점)

---

## 6. Readiness Score

| 영역 | 점수(100점 기준) | 근거 |
|---|---|---|
| 운영 절차 | **65** | 6개 핵심 전이 중 3개(생성/승인/거절)는 성숙하고 매우 두텁게 테스트됨(252개 테스트). 나머지 3개(변경/취소/검진완료)는 FastAPI 검증·감사·전용 테스트가 전무해 절반의 절차 표면에 공백이 있다. |
| 시스템 안정성 | **72** | Admin Portal 경로(Parser+Timeout+Policy)는 견고. Legacy/Reservation Portal 경로는 Timeout 0건·오류 형식 미표준화. 데이터 흐름 자체(Sheets SSOT, LockService, 페이지네이션 없는 전체 조회)는 구조적으로 안정적. |
| 문서 | **55** | "0에서 시작"이 아니라 실질적 문서 7종(660줄+)이 이미 있으나 전부 Sprint2~6 미반영이라는 정확한 결함이 있다. 문서의 존재 자체는 긍정 요인, 최신성 결여는 부정 요인으로 상쇄. |
| 운영 지원 | **40** | 실 인증 미구현, 구조화 로깅 없음, Legacy 경로 감사 불가, FAQ 없음, 연락망 공란 — 5개 항목이 전부 실측으로 확인된 공백이라 낮게 평가. |
| Release 준비 | **58** | Git 기반 버전관리·회귀 테스트는 매우 탄탄(전 스위트 재확인 PASS). Rollback Guide 부재, Release Checklist 미갱신이 상쇄 요인. |
| **평균** | **58** | 단순 평균 (65+72+55+40+58)/5 |

**해석**: 58/100은 "핵심 기능(승인 흐름)은 운영 투입 가능한 수준으로 완성됐으나, 그 주변(나머지 전이·인증·로깅·문서 최신화)이 따라오지 못한 상태"를 의미한다. 신규 기능 개발 없이 Sprint7 P0~P1 항목만 완료해도 대부분의 Critical/High Gap이 해소되어 점수가 유의미하게 오를 것으로 예상되나, **이 예상치 자체는 추측이므로 Score에는 반영하지 않았다** — Commit7-2 재평가는 각 후속 Commit 완료 시점에 실측으로 갱신한다.

---

## 7. 권장 우선순위

1. **Critical — 즉시 Commit7-3에서 다룸**: 예약변경/취소/검진완료의 FastAPI 검증·감사 공백(Legacy Stage3 Phase B 설계).
2. **Critical — Commit7-4/7-5에서 다룸**: 기존 7종 운영 문서를 Sheets/Admin Portal 반영해 갱신(`CSHSP_GAS_WEBAPP_URL` 등 필수 정보 보강). 신규 작성이 아니라 갱신임을 명확히 한다.
3. **Critical — Sprint7 범위 밖으로 명시 이월**: 관리자 실 인증 구현. Sprint7 원칙(신규 기능 금지)과 충돌하므로 이번 Sprint에서 구현하지 않되, 다음 Sprint의 최우선 후보로 문서에 남긴다.
4. **High — Commit7-5**: Rollback Guide 신규 작성, Sheets 백업 정책 보강.
5. **High — 기록만(코드 변경 없음)**: Legacy/Reservation Portal Timeout 부재를 Gap으로 남기고, 향후 Portal 개선 Commit 후보로 등록.
6. **Medium — Commit7-4/7-5**: 구조화 로깅 현황 명문화, Release Checklist 독립 문서화, FAQ 작성.
7. **Low — Commit7-7(이미 계획)**: TD-S5-03/05.

## 8. Commit7-3 준비사항

- Legacy Stage3 Phase B 설계 시 **Gap #1(예약변경/취소/검진완료 검증 공백)을 1차 입력값**으로 사용한다.
- `roles.json`의 `reservation:change`/`reservation:cancel` 권한이 이미 정의돼 있다는 사실(§3-4)을 설계에 반영 — 새 권한 모델을 만들 필요 없이 기존 문자열을 재사용할 수 있다.
- 완전 해소(Admin Portal에 3개 전이 기능 신설)는 새 FastAPI 엔드포인트가 필요한 **Backend 구조 변경**이므로 Sprint7 원칙 9("Backend/FastAPI 구조 변경 금지, 별도 승인 전")에 따라 Commit7-3은 **설계 문서까지만** 작성하고 구현하지 않는다.
- Commit7-4(운영 매뉴얼)는 이번 평가에서 발견한 "기존 문서 갱신" 방향으로 재설계해 보고한다.

---

## 완료 조건 준수 확인

이 문서 작성 중 어떤 코드 파일도 수정하지 않았다(Read/Grep/기존 테스트 재실행만 수행 — `run_backup_restore_rehearsal.py`는 읽기 전용 리허설이며 `data/` 원본을 변경하지 않는다, 코드 자체도 무수정). Commit/Push/Deploy 없음. Business Rule/Backend/FastAPI/Portal 구조 변경 없음.
