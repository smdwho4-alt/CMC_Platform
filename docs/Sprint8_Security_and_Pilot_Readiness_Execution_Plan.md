# Sprint8 Security and Pilot Readiness Execution Plan

> 작성: Sprint8 Commit8-0(2026-07-31) — 신규 독립 문서.
> 기준선: `222f53a5090fe66d276a360dcdc0d08e57a8f97e`("docs: consolidate sprint7 closeout and operational readiness") — Sprint7 최종 종료 커밋과 실제 HEAD 일치 확인됨.
> 이 문서는 **구현 완료 보고서가 아니라 구현 전 실행계획·의사결정 자료**다. 이번 Commit(8-0)에서는 코드를 변경하지 않는다.

---

## 1. 문서 개요

Sprint7 Closeout(§22~23)은 전체 운영 준비도를 **CONDITIONALLY READY**로 판정하되, 보안 준비도와 거버넌스 준비도를 **NOT READY**로 명시했다. 이 문서는 그 두 영역(관리자 인증·인가, GAS 직접호출 통제)을 중심으로 Sprint8에서 무엇을, 어떤 순서로, 어떤 승인 절차를 거쳐 해결할지 계획한다.

## 2. 작성 목적

§10(문서 작성 목적) 12개 항목을 충족한다 — Sprint8 기준선 확정, 보안 강화 목표·범위 확정, 인증·인가 대안 비교, GAS 통제 대안 비교, Legacy 서버 검증 범위 확정, 예약변경 요구사항 정의 방향 제시, 백업·복구 확정 항목 제시, Staging E2E 계획, 제한적 Pilot 조건 정의, Commit 단위 실행계획, Decision Required 통합, Push·Deploy Gate 정의.

## 3. 적용 범위

Sprint8 전체의 실행계획 수립(대안 비교·의사결정안·위험등록부·Commit 계획). 코드 구현은 Commit8-1 이후 별도 PM 승인을 받은 뒤 착수한다.

## 4. 제외 범위

- 이번 Commit에서 코드·설정·API·테스트·Business Rule·Sheets·Apps Script·Netlify 변경 없음
- 관리자 인증 기능 구현 없음(설계·대안비교까지만)
- Legacy 기능 변경 없음
- Push, Deploy 없음
- Commit8-1 이후 작업 착수 없음

## 5. Sprint7 종료 기준선

`docs/Sprint7_Closeout_and_Operational_Readiness_Consolidation.md`(Commit `222f53a`) 기준. 전체 판정 **CONDITIONALLY READY**, 영역별: 기능/데이터/배포/장애대응/백업복구=CONDITIONALLY READY, 보안/거버넌스=**NOT READY**, 운영인력=판정보류, 문서=READY. P0 조치 3건(A1 관리자 인증, A2 GAS 접근통제, A3 운영재개 승인권자)이 Sprint8 착수의 직접 근거다.

## 6. 현재 저장소·Branch·HEAD

저장소: `CMC_Platform`(origin `smdwho4-alt/CMC_Platform`). Branch: `main`. 작업 전 HEAD: `222f53a5090fe66d276a360dcdc0d08e57a8f97e`(Sprint7 종료 커밋과 일치, `git log`로 실측 확인, Hash를 맹신하지 않고 재확인함). Local이 origin보다 41개 커밋 앞선 상태(미Push, 오류 아님 — 세션 전체에서 Push 보류 방침 유지 중).

## 7. 시스템 구성요소별 현재 상태

Sprint7 Closeout §8과 동일하며 이번 코드 재조사로 재확인됨. 변동 없음(코드 변경이 Sprint7 이후 없었으므로).

## 8. 실제 인증·인가 구조 (코드 재확인)

- **인증**: `src/api/api_server.py`의 `require_user()` — `X-User-Id` 헤더 값으로 `data/users.json`에서 사용자를 조회하고 `status == "ACTIVE"`만 확인한다. 비밀번호·토큰·서명 검증 **없음**(코드 확인). 코드 주석에 "Sprint E에서 실제 인증(JWT/세션)으로 교체 예정"이라는 문구가 있어, 설계 당시부터 임시 조치로 의도되었음을 알 수 있다(실제 교체는 Sprint E~7 어느 시점에도 수행되지 않았다).
- **인가**: `has_perm()`/`need_perm()`이 `data/roles.json`의 역할별 `permissions` 배열을 확인한다. `reservation:view`, `reservation:change`, `slot:manage`, `patient:view` 등 일부 엔드포인트에 실제로 적용되어 있다(코드 확인, `api_server.py` L213/242/296/301/323/416/429).
- **중요 재확인 사항(Sprint7 문서와의 충돌, 상세 §17)**: `src/reservation/reservation_engine.py`의 `cancel_reservation()`(L445)/`change_reservation()`(L502)은 `_has_permission(actor_user_id, "reservation:cancel"/"reservation:change", data_dir)`을 실제로 검사한다. 그러나 이 함수들이 연결된 `/api/reservations/{rid}/cancel|change|complete|no-show` 엔드포인트(`api_server.py` L281~302)는 **`data/reservations.json`(로컬 JSON, ADR-013 이후 예약 SSOT 아님)을 대상**으로 하며, `app/pages/*.html`·`app/js/*.js` 전체 검색 결과 **어떤 Portal UI도 이 엔드포인트를 호출하지 않는다**(0건, grep 재확인). 즉 이 인증·인가 코드는 실재하지만 현재 사용 중인 Sheets 기반 예약 흐름과는 연결되어 있지 않은 **미사용(Orphaned) 경로**다.

## 9. 관리자 Portal 보안 현황

Admin Portal(`admin_portal_new.html`)은 `X-User-Id` 헤더를 프론트엔드 코드에서 직접 설정하는 구조로 추정되며(Mock 인증과 일치), 실제 로그인 화면이나 자격증명 검증 UI가 없다. HTTPS 여부는 배포 환경(Netlify/서버) 설정에 의존하며 이 저장소 코드만으로는 확인 불가 — **[확인 필요]**.

## 10. FastAPI 인증·인가 적용 범위

Mock 인증(`require_user`)은 `routes_admin_portal.py`(Admin Portal 전용, `/api/admin-portal/*`, `/api/admin/*`)와 `api_server.py`의 구버전 엔드포인트(`/api/reservations/*`, `/api/slots/*`, `/api/patients/*` 등)에 적용된다. **Reservation Portal의 예약 생성(GAS 직접 호출)과 Legacy Portal의 상태변경(GAS 직접 호출)은 FastAPI를 전혀 경유하지 않으므로 이 인증 체계의 보호 범위 밖이다.**

## 11. GAS 직접호출 구조와 위험

`app/apps_script/sheets_api_v3_final.gs`의 `doGet`(L211)/`doPost`(L225) 진입점을 재확인한 결과, 호출자 인증(API Key/Token/서명/세션) 관련 코드는 **0건**이다(`token`/`signature`/`hmac`/`apiKey`/`Authorization` 키워드 전체 검색). Web App URL만 알면 `action` 파라미터로 어떤 CRUD 액션이든 직접 호출 가능하다. 이는 Sprint7 문서(Commit7-3/7-5)의 서술과 일치하며 코드로 재확인됨.

## 12. Legacy 상태전이 구조와 위험

§14 표 참조. 예약확정만 Commit6-1의 클라이언트 UI 가드로 차단(우회 가능), 나머지 3개 전이(변경/취소/완료)는 UI 차단조차 없다.

## 13. 예약변경 기능의 실제 현황

`_actionUpdateStatus(no, status, confirmedAt)`(GAS)는 `일정변경` 상태에 대해 별도 side-effect가 없다 — 즉 상태 라벨(`예약상태` 컬럼)만 바뀌고 `희망검진일`/`희망시간` 컬럼은 그대로다(Commit7-3에서 코드로 확인된 사실, 이번 세션에서 재검증하지 않았으나 GAS 파일 구조상 여전히 유효). 실제 일정 변경은 `_actionUpdate()`(별도 action)로만 가능하나 Legacy Portal UI가 이를 호출하는 코드가 없다(Commit7-3 확인 사항, 이번 문서에서 그대로 승계).

## 14. Slot 처리 현황

승인 경로(Admin Portal→FastAPI)는 Slot 점유·중복·정원 검증이 성숙하다(252개 테스트, Commit5-2 등). Legacy Portal의 취소 처리는 `_actionUpdateStatus()`에 Slot 관련 로직이 전혀 없어(코드 확인, Commit7-3에서 이미 확인, 이번에 재확인하지 않음 — 파일 미변경) 취소 후 정원이 반환되지 않는다.

## 15. Google Sheets SSOT와 데이터 통제

ADR-013(2026-07-27) 재확인 — Google Sheets가 예약 Master Data. `data/reservations.json`은 "신규 예약의 공식 원장으로는 더 이상 사용하지 않되 기존 기능 호환·테스트 Fixture·마이그레이션 검증·Rollback 참고 용도로 유지"(ADR-013 원문 인용). §8에서 발견한 구버전 FastAPI cancel/change 엔드포인트가 바로 이 비-SSOT 데이터를 대상으로 하는 잔재다.

## 16. GAS v3/v4 구분

`sheets_api_v3_final.gs`(527줄)가 확인된 운영 배포본. `sheets_api_v4_deploy_new.gs`(497줄)는 파일 자체 헤더에 "핵심 로직(doGet/doPost/CRUD/DateFix) — v3와 동일, 변경 없음"이라고 명시하지만, **동일 헤더에 6가지 변경사항이 나열되어 있다**: CONFIG 블록 분리, doGet CORS preflight(OPTIONS) 우회 처리 추가, POST Content-Type 경고, **`_actionList` 결과에 개인정보(phone/birth) 응답 포함 여부 선택자 추가**, API_VERSION 상수 추가, 배포 전 체크리스트 주석. 즉 "핵심 CRUD 로직은 동일"하나 "완전히 무변경"은 아니며, 특히 PII 응답 선택자 변경은 v4 전환 검토 시 개인정보 노출 범위 관점에서 별도 검토가 필요하다(신규 발견, 이번 Commit8-0에서 확인). v3→v4 전환은 여전히 확인 없이 수행하지 않는다.

## 17. 감사로그·추적성 현황

FastAPI 경유 승인/거절: `audit_logs.json`에 기록됨(확인됨). Legacy Portal의 상태변경(변경/취소/완료/메모): `admin_reservations_v2_new.html`에서 "audit" 키워드 0건(재확인 완료, grep 결과). §8에서 발견한 구버전 FastAPI cancel/change 엔드포인트는 감사로그 연결 여부를 이번 Commit에서 상세 확인하지 않았다 — **[확인 필요]**(어차피 미사용 경로이므로 우선순위 낮음).

## 18. Sprint8 목표

1. 관리자 실 인증·인가 도입 경로 확정(구현은 Commit8-2)
2. GAS 직접호출 통제 방식 확정(구현은 Commit8-3)
3. Legacy 3개 전이(변경/취소/완료)의 서버 검증 범위 확정 및 우선순위별 적용(Commit8-4)
4. 예약변경의 실제 요구사항 정의 방향 제시(구현 여부는 요구사항 확정 후 별도 결정, Commit8-5)
5. Sheets 백업·복구 운영체계 확정(Commit8-6)
6. Staging 환경 기반 E2E 검증 및 제한적 Pilot 준비도 평가(Commit8-7)

## 19. Sprint8 비목표

- 전체 운영(외부 공개) 전환 — Sprint8 범위 밖, 별도 승인 대상
- 신규 Business 기능 추가(예: 신규 검진 프로그램, 신규 Portal)
- Reservation Portal의 FastAPI 전면 마이그레이션(예약 생성 경로 자체는 Sprint8에서 다루지 않음, 필요 시 별도 Sprint)
- 로컬 JSON 예약 엔진(`reservation_engine.py`)의 구버전 cancel/change 엔드포인트 활성화 — 오히려 §17의 발견을 근거로 이 경로를 계속 쓸지, 제거할지는 Decision Required(D26)로만 등록

## 20. 관리자 인증·인가 구현 대안

### 대안 A. FastAPI 중심 관리자 인증·인가
- **구조**: FastAPI 자체에 로그인 엔드포인트(ID/PW 또는 해시 비교) + 세션/JWT 발급, 기존 `require_user`/`has_perm`을 실 검증으로 교체
- **인증 주체**: FastAPI 서버
- **인가 처리 위치**: 기존 `has_perm()`/`roles.json` 구조 재사용
- **Session/Token 관리**: 서버 발급 JWT(짧은 만료) 또는 서버측 세션 스토어(`session_store.py` 패턴 재사용 가능, 이미 AI 채팅 세션에 사용 중인 유사 구조)
- **사용자·역할 관리**: 기존 `users.json`/`roles.json` 구조 확장(비밀번호 해시 필드 추가)
- **감사로그**: 기존 `append_audit()` 재사용, 로그인/로그아웃 이벤트 추가
- **장점**: 기존 구조(RBAC, roles.json, need_perm) 그대로 재사용 가능, 외부 의존성 없음, 코드 주석에 이미 "Sprint E에서 교체 예정" 지점으로 명시되어 있어 설계 의도와 일치
- **단점**: 비밀번호 저장·해시·재설정 절차를 직접 구현·운영해야 함(보안 책임이 병원 측/개발팀에 전가)
- **보안위험**: 자체 구현 인증의 구현 결함 위험(해싱 알고리즘, 세션 고정, 무차별 대입 방지 등을 직접 챙겨야 함)
- **구현 난이도**: 중간(기존 구조 재사용 가능하나 신규 로그인 플로우·비밀번호 관리 필요)
- **운영 난이도**: 중간(비밀번호 재설정 등 운영 프로세스 필요)
- **기존 구조 영향**: 낮음(require_user 내부 구현만 교체, 호출부 API 계약 유지 가능)
- **Pilot 적용 가능성**: 높음
- **전체 운영 적용 가능성**: 가능(단, 보안 검토 필요)
- **선행 의사결정**: 비밀번호 정책, 계정 관리 주체(D2)
- **권장 여부**: **권장(1순위 후보)** — 기존 구조와의 정합성이 가장 높음

### 대안 B. 외부 Identity Provider 기반 인증
- **구조**: OAuth2/OIDC(예: 병원 조직 계정, Google Workspace, Azure AD 등) 연동
- **인증 주체**: 외부 IdP
- **인가 처리 위치**: FastAPI가 IdP의 클레임(예: 그룹/역할)을 `roles.json` 역할에 매핑
- **Session/Token**: IdP 발급 ID Token/Access Token 검증
- **사용자·역할 관리**: IdP 측(병원 조직 계정 시스템)
- **감사로그**: 기존 방식 유지 가능
- **장점**: 비밀번호 직접 관리 부담 없음, 병원 기존 계정 체계 재사용 가능성
- **단점**: 병원 측에 IdP가 실제로 존재하는지, 연동 가능한지 **[확인 필요]** — 이 저장소만으로는 확인 불가. 신규 외부 연동은 구현·검증 범위가 큼
- **보안위험**: IdP 설정 오류 시 광범위한 영향, 연동 코드 자체의 신규 취약점 가능성
- **구현 난이도**: 높음
- **운영 난이도**: 낮음(IdP가 계정 관리를 담당하면 낮아짐) — 단 최초 연동 난이도는 높음
- **기존 구조 영향**: 중간~높음(신규 의존성 추가)
- **Pilot 적용 가능성**: 낮음(연동 검증에 시간 소요)
- **전체 운영 적용 가능성**: 가능(장기적으로는 유리할 수 있음)
- **선행 의사결정**: 병원 측 IdP 존재 여부·연동 가능 여부 확인(D1)
- **권장 여부**: 중장기 후보로만 등록, Sprint8 1순위 아님(병원 측 IdP 존재 여부 확인 전까지 실행 불가)

### 대안 C. 병원 내부망·VPN 제한과 서버 인증 병행
- **구조**: 네트워크 계층 접근 제한(VPN/내부망 IP 화이트리스트) + 대안 A의 서버 인증을 함께 적용
- **인증 주체**: 네트워크 계층 + FastAPI
- **인가 처리 위치**: 기존 구조 유지
- **Session/Token**: 대안 A와 동일
- **사용자·역할 관리**: 대안 A와 동일 + 네트워크 접근 목록 별도 관리
- **감사로그**: 기존 방식 + 접근 IP 기록(신규 검토 필요)
- **장점**: 심층 방어(Defense in Depth) — 인증 계층이 뚫려도 네트워크 계층이 추가 방어선
- **단점**: 네트워크 인프라(VPN/방화벽) 구성이 이 저장소 범위 밖(병원 인프라팀 협업 필요), 원격/이동 접근 시 불편
- **보안위험**: 낮음(A 단독보다 위험 완화)
- **구현 난이도**: 인프라 구성은 저장소 밖이라 이 프로젝트 관점에서는 낮음(설정 문서화 정도), 실제 네트워크 구성은 별도 난이도 존재
- **운영 난이도**: 중간(VPN 계정 관리 추가)
- **기존 구조 영향**: 낮음
- **Pilot 적용 가능성**: 높음(Pilot은 어차피 제한된 인원·환경이므로 자연스럽게 결합 가능)
- **전체 운영 적용 가능성**: 가능
- **선행 의사결정**: 병원 네트워크 인프라의 VPN/내부망 격리 가능 여부(D3)
- **권장 여부**: **대안 A와 병행 권장**(단독으로는 불충분 — 네트워크 계층만으로 인증을 대체하지 않는다는 원칙과 일치시키기 위해 반드시 서버 인증과 함께 적용)

### 대안 D. 단기 Pilot용 제한적 임시 통제
- **구조**: 실 인증 구현 전, 극소수 인원 한정 IP 접근 제한 + 강화된 운영 절차(예: URL 비공개, Mock 인증 유지하되 접근 인원 최소화)
- **인증 주체**: 사실상 통제 없음(운영 절차로만 완화)
- **인가 처리 위치**: 기존 Mock 구조 그대로
- **Session/Token**: 없음(Mock 유지)
- **사용자·역할 관리**: 기존 유지
- **감사로그**: 기존 유지
- **장점**: 즉시 적용 가능, 추가 개발 불필요
- **단점**: **근본적인 보안 위험 해소 없음** — 임시방편일 뿐
- **보안위험**: 여전히 높음(§ R1 위험 그대로 잔존)
- **구현 난이도**: 매우 낮음
- **운영 난이도**: 낮음
- **기존 구조 영향**: 없음
- **Pilot 적용 가능성**: 조건부 가능(다른 대안 구현 전 임시 가교로만)
- **전체 운영 적용 가능성**: **불가**(최종 보안체계로 사용 금지)
- **선행 의사결정**: 없음(즉시 적용 가능하나 임시조치임을 반드시 명시)
- **권장 여부**: **임시 가교로만 권장, 최종 통제로 표현하지 않음** — 대안 A(+C) 구현 전까지의 과도기적 조치로만 사용

**권장안**: 대안 A(FastAPI 중심 인증)를 우선 구현하고, 가능하면 대안 C(네트워크 제한)를 Pilot 기간 병행한다. 대안 B는 병원 IdP 존재 여부 확인 후 중장기 검토. 대안 D는 대안 A 구현 완료 전까지의 임시 가교로만 사용하며 최종 통제로 간주하지 않는다. **최종 결정은 Decision Required(§31 D1~D5)로 남긴다.**

## 21. GAS 직접호출 통제 대안

| # | 대안 | 실효성 | 제한사항 | 기존 구조 영향 | 우회 가능성 |
|---|---|---|---|---|---|
| 1 | 브라우저 GAS 직접호출 제거, FastAPI Proxy 일원화 | 높음(근본 해결) | Reservation Portal(생성)·Legacy Portal(상태변경) 양쪽 다 FastAPI 신규 엔드포인트 필요 — 구현 범위 큼 | 큼(두 Portal 모두 호출 방식 변경) | 낮음(Proxy가 인증 강제 시) |
| 2 | GAS 요청 서명 검증(HMAC 등) | 중간~높음 | GAS `doGet`/`doPost`에 서명 검증 로직 추가 필요, 클라이언트가 서명을 계산해야 하므로 **서명 키를 클라이언트에 둘 수 없음**(원칙 위반) → 결국 FastAPI가 서명을 대신 생성하는 Proxy 구조와 결합해야 실효적 | 중간 | 클라이언트 단독 구현 시 우회 가능(Secret 노출 위험), Proxy와 결합 시 낮음 |
| 3 | 단기수명 Token/JWT 검증 | 중간~높음 | Token 발급 주체가 필요(결국 FastAPI가 발급) — 대안 1/2와 사실상 결합됨 | 중간 | Token 미검증 경로 남으면 우회 가능 |
| 4 | 허용 Origin 검증 | **낮음(단독 사용 금지)** | Origin 헤더는 클라이언트가 위조 가능, GAS는 브라우저가 아닌 임의 클라이언트의 직접 호출을 막지 못함 | 낮음 | **높음** — 인증 대체 수단으로 사용 금지(§13 주의사항과 일치) |
| 5 | 요청 Timestamp·Nonce·Replay 방지 | 중간(보조 수단) | 단독으로는 최초 요청 자체를 막지 못함, 서명/Token과 결합 시에만 유효 | 중간 | 결합 없이는 낮은 실효성 |
| 6 | 관리자 작업 역할·권한 검증 | 중간(보조 수단) | GAS 자체에 역할 개념이 없어 신규 구현 필요, 결국 FastAPI Proxy가 담당하는 편이 기존 `roles.json` 재사용 가능 | 중간 | Proxy 없이 GAS에서 직접 구현 시 검증 어려움 |
| 7 | 호출별 감사로그 | 낮음(탐지용, 예방 아님) | 사후 탐지만 가능, 우회 자체를 막지 못함 | 낮음 | 무관(예방 수단 아님) |
| 8 | GAS 배포 접근권한 제한(Google 계정 단위) | 중간(보조) | Web App 자체는 "누구나 액세스" 설정이어야 외부 웹앱으로 동작(Google Apps Script 특성상 호출자 인증 불가) — 이 대안은 **개발/배포 권한** 제한이지 **호출자 인증**이 아님, 혼동 주의 | 낮음 | 무관(다른 계층의 통제) |
| 9 | Legacy 경로 단계적 종료(Phase B) | 높음(장기) | `Legacy_Stage3_PhaseB_Design_v1.0.md` B-1~B-6 계획 존재, 구현 없이는 즉시 효과 없음 | 큼(장기 마이그레이션) | 전환 완료 전까지는 기존 위험 그대로 |
| 10 | Pilot 기간 내부망·접근대상 제한 | 중간(임시) | 근본 해결 아님, Pilot 범위 한정 완화책 | 없음(운영 절차) | Web App URL 유출 시 여전히 우회 가능 |

**핵심 결론**: 대안 4(Origin 검증)와 대안 8(GAS 배포 권한)은 **단독으로는 인증을 대체할 수 없다**(원칙과 일치, §13 주의사항 준수). 가장 실효적인 조합은 **대안 1(FastAPI Proxy 일원화) + 대안 2/3(서명 또는 Token, FastAPI가 발급) + 대안 7(감사로그)**이며, 이는 사실상 GAS 직접호출 자체를 없애고 모든 Sheets 접근을 FastAPI가 중계하는 구조다. 이 구조는 Reservation Portal(생성 경로)과 Legacy Portal(상태변경 경로) 양쪽 모두의 호출 방식 변경을 요구하므로 **구현 범위가 크고 별도 Sprint 단위 작업**이 필요하다 — Sprint8에서는 설계·우선순위만 확정하고 실제 전환은 Commit8-3 이후 단계적으로 진행한다(우선순위: Legacy Portal의 무감사 전이부터, §22).

## 22. Legacy 상태전이 검증 범위

| 항목 | 예약확정 | 예약변경 | 예약취소 | 검진완료 |
|---|---|---|---|---|
| 현재 호출 경로 | Legacy Portal → GAS `updateStatus`(client-side 차단, 우회 가능) | Legacy Portal → GAS `updateStatus` | Legacy Portal → GAS `updateStatus` | Legacy Portal → GAS `updateStatus` |
| 현재 UI | `admin_reservations_v2_new.html` `#statusSel` | 동일 | 동일 | 동일 |
| 현재 API/GAS action | `action=updateStatus` | `action=updateStatus` | `action=updateStatus` | `action=updateStatus` |
| FastAPI 관여 | 있음(Admin Portal 경로로는 가능, Legacy 직접 호출 시 없음) | 없음 | 없음 | 없음 |
| 정책검증 여부 | Admin Portal 경로만 있음, Legacy 직접호출 시 없음 | 없음 | 없음 | 없음 |
| 역할·권한 검증 | Legacy 직접호출 시 없음(GAS 자체가 무인증) | 없음 | 없음 | 없음 |
| Sheets 변경 내용 | `예약상태`+`예약확정일` | `예약상태`만(희망일시 불변, §13) | `예약상태`만 | `예약상태`+`접수시간`+`검진시작`+`검진종료` |
| Slot 영향 | 없음(GAS 자체는 무관, Admin Portal 경로에서만 점유 처리) | 없음 | **없음(미반환, 알려진 결함)** | 없음 |
| 감사로그 | Legacy 직접호출 시 없음 | 없음 | 없음 | 없음 |
| 우회 가능성 | 있음(GAS 직접호출) | 해당없음(애초에 서버 차단이 없음) | 해당없음 | 해당없음 |
| 목표 호출 경로 | Admin Portal 경유로 일원화(이미 대부분 달성) | FastAPI 신규 엔드포인트(요구사항 확정 후) | FastAPI 신규 엔드포인트 | FastAPI 신규 엔드포인트 |
| 서버 검증 요구사항 | GAS 통제(§21)로 우회 자체 차단 | Slot 재배정 로직 신규 필요(요구사항 미확정) | Slot 반환 로직 필요 | 상태 전이 규칙(완료 후 재변경 금지 등) |
| 실패 시 처리 | 기존 Admin Portal 오류 계약 재사용 | 미정(요구사항 확정 후) | 기존 계약 재사용 가능 | 기존 계약 재사용 가능 |
| Rollback 요구사항 | 기존 Rollback Guide §8/§13 | 신규 설계 필요 | Slot 반환 실패 시 보상처리 필요 | 완료 취소 가능 여부 결정 필요(D 항목) |
| 구현 우선순위 | 낮음(이미 부분 해소) | **낮음**(요구사항 자체 미확정) | **높음**(Slot 미반환은 이미 확인된 결함) | 중간 |
| 운영 전 필수 여부 | 아니오(현행 유지 가능) | 아니오(Pilot은 기존 방식 유지 가능) | 권장(정합성 위험 완화) | 아니오 |

### 예약변경 별도 검토
- **현재 상태 라벨만 변경되는지**: 그렇다(§13, `_actionUpdateStatus`에 side-effect 없음 확인).
- **예약일자·시간·검진 프로그램 변경 요구사항**: **미확정** — 병원 운영팀의 실제 업무 요구사항(변경 허용 시점, 횟수 제한, 당일 변경 허용 여부)이 정의되지 않았다(Legacy_Stage3_PhaseB_Design §16 Decision Required #1~3 그대로 승계).
- **기존 Slot 반환**: 미구현.
- **신규 Slot 확보**: 미구현.
- **중간 실패 시 원자성/보상처리**: 설계 없음(요구사항 확정 후 설계 필요).
- **중복예약 방지**: 승인 경로의 기존 로직(Commit3A) 재사용 가능성 있음 — 구현 시 검토.
- **수검자 알림**: 현재 알림 메커니즘 자체가 이 프로젝트 범위에서 확인되지 않음 — **[확인 필요]**.
- **변경이력 저장**: 감사로그 미구현(§17).
- **관리자 권한검증**: `reservation:change` 권한 문자열은 `roles.json`에 정의되어 있으나(§8) 현재 사용 중인 Sheets 경로에는 연결되어 있지 않다.

**실제 요구사항이 미확정이므로 이번 문서에서 예약변경 기능을 "설계 완료"로 표현하지 않는다.**

## 23. 실제 예약변경 기능 정의 방향

1. 병원 운영팀과 함께 §22 하위 항목(변경 허용 시점/횟수/당일 변경/취소 사유 필수 여부 등, Legacy_Stage3_PhaseB_Design §16 D1~D4)을 먼저 확정한다.
2. 요구사항 확정 전에는 코드 설계에 착수하지 않는다(임의 가정 금지 원칙).
3. 요구사항 확정 후 Commit8-5에서 설계 또는 최소 구현 범위를 PM과 재조정한다.

## 24. 백업·복구 운영체계 확정안

Sprint7 backup_policy.md §5-2의 Decision Required(D4~D8, Sprint7 Closeout 인용)를 그대로 승계한다. Sprint8 Commit8-6에서 다음을 확정 목표로 한다: 백업 책임자, 복구 책임자, 백업 주기(Sheets), 보존기간(Sheets), 복구 성공기준(Sheets). 이번 Commit8-0에서는 목표만 설정하며 확정하지 않는다.

## 25. Staging E2E 검증계획

- **환경 구성**: 운영 Sheets와 분리된 별도 테스트용 Sheets/GAS 배포(Staging 전용) 구성 필요 — **현재 이 저장소에 Staging 환경 구성 여부 확인 안 됨, [확인 필요]**
- **검증 대상**: 관리자 인증 도입 후 기존 승인/거절 흐름 회귀 없음, GAS 통제 도입 후 Legacy/Reservation Portal 정상 동작, Slot/Policy 검증 회귀 없음
- **데이터 기준**: 비식별 테스트 데이터만 사용, 실제 운영 개인정보 사용 금지
- **완료 기준**: 기존 회귀 스위트(252개+) 전체 PASS 유지 + 신규 보안 기능 테스트 PASS
- **선행조건**: Commit8-2/8-3 구현 완료

## 26. 제한적 Pilot 범위

§27(Pilot 준비계획) 통합.

- **Pilot 목적**: 실 운영 투입 전 제한된 조건에서 시스템 동작 검증
- **대상 Portal**: Admin Portal(승인/거절) 우선, Legacy Portal은 기존 방식 유지(신규 위험 추가 아님)
- **대상 기능**: 예약 승인/거절, 조회 — 예약변경 등 미확정 기능은 Pilot 범위에서 제외
- **대상 사용자**: 병원 지정 소수 운영 인력(인원수 **[확인 필요]**, 병원이 결정)
- **대상 데이터**: **1차로 비식별/테스트 데이터 기반 Staging 검증을 우선**하며, 실제 운영 개인정보 사용은 별도 승인 전 금지로 제안
- **운영시간/적용기간/일일 처리량 제한**: 병원 운영팀과 협의 필요 — **[확인 필요]**
- **접근통제**: §20 대안 A(+C) 적용 후 진행 권장
- **모니터링**: 현재 구조화 로깅 없음(§17, stderr만) — Pilot 중 최소한 수동 점검 절차 필요
- **장애 연락망**: D9(Sprint7 Closeout 승계) 확정 필요
- **백업/복구/Rollback**: 기존 Rollback Guide 절차 재사용, §24 확정 후 강화
- **중단기준**: §28
- **성공기준**: §27(다음 절)
- **최종 승인권자**: **[확인 필요]**, Decision Required(D23)
- **데이터 폐기 또는 보존**: Pilot 종료 후 테스트 데이터 처리 방침 — **[확인 필요]**
- **Pilot 종료 후 평가**: Commit8-8(Sprint8 Closeout)에서 수행

## 27. Pilot 성공기준

- 관리자 인증 도입 후 기존 회귀 테스트 전체 PASS 유지
- Pilot 기간 중 인증 우회·무단 접근 사례 0건
- Pilot 기간 중 Slot/Policy 오작동으로 인한 예약 오류 0건
- 장애 발생 시 Rollback Guide 절차로 실제 복구 성공(최소 1회 리허설 권장)
- Pilot 참여 인력의 주요 기능(승인/거절) 정상 사용 확인

## 28. Pilot 중단기준

- 인증 우회 또는 무단 접근이 실제로 발생한 경우 — 즉시 중단
- 개인정보 노출 의심 사례 발생 — 즉시 중단
- 정원 초과 예약 등 데이터 정합성 심각 이상 발생 — 즉시 중단
- 복구 불가능한 장애 발생 — 즉시 중단, Rollback Guide §18 기준 적용

## 29. 운영재개 승인 Gate

Sprint7 Closeout D1(운영재개 최종 승인권자, 미확정)을 승계한다. Sprint8에서 Commit8-6/8-7 완료 시점까지 이 결정이 없으면 Pilot 자체를 시작하지 않는다 — Sprint7 Closeout A3와 동일 조치를 Sprint8 착수 전제조건으로 재확인한다.

## 30. Rollback Gate

기존 `docs/CSHSP_Rollback_Guide.md` 절차를 그대로 적용하며, Sprint8에서 신규 구현(인증, GAS 통제)이 추가되는 만큼 **인증 관련 장애 시나리오**(예: 인증 서버 장애로 전원 접근 불가)를 Commit8-2 설계 시 Rollback Guide에 추가 반영할 필요가 있다 — 이번 Commit에서는 기존 문서를 수정하지 않고 향후 과제로만 기록한다.

## 31. Decision Required

| ID | 결정 필요사항 | 현재 상태 | 이유 | 미결정 시 영향 | 권장안 | 대안 | 권장 결정주체 | 결정 필요시점 | 임시 통제방안 | 관련 Commit | 관련 문서 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 관리자 인증방식 | 미확정 | §20 대안 4종 존재 | 구현 착수 불가 | 대안 A(+C 병행) | 대안 B(장기) | PM | Commit8-1 착수 전 | 대안 D(임시 가교, 최종 아님) | 8-1/8-2 | 본 문서 §20 |
| D2 | 관리자 계정 관리주체 | 미확정 | 계정 발급·해지 프로세스 필요 | 계정 관리 공백 | 병원 전산담당 제안 | IdP 채택 시 병원 조직계정 관리팀 | PM/병원 | Commit8-2 착수 전 | 현재 users.json 수동 관리 유지 | 8-2 | 본 문서 §20 |
| D3 | 역할·권한 모델 확장 여부 | roles.json 기존 5개 역할 유지 중 | 신규 기능(변경/취소/완료)에 필요한 권한 재검토 필요 | Legacy 검증 설계 지연 | 기존 permission 문자열 재사용(reservation:change/cancel) | 신규 권한 신설(예: reservation:complete) | PM | Commit8-4 착수 전 | 없음 | 8-4 | Legacy_Stage3_PhaseB_Design §16 |
| D4 | Session/Token 정책 | 미확정 | 만료시간·재발급 방식 필요 | 구현 세부설계 불가 | 짧은 만료 JWT(예: 서버측 검증) | 서버측 세션 스토어 | PM/개발팀 | Commit8-1 착수 전 | 없음 | 8-1 | 본 문서 §20 |
| D5 | 비밀번호 정책 적용 주체 | 미확정 | 정책 수립 필요(길이/복잡도/재설정) | 계정 보안 수준 불명확 | 병원 전산 표준 있으면 그것을 따름 | 프로젝트 자체 기준 수립 | 병원/PM | Commit8-2 착수 전 | 없음 | 8-2 | 본 문서 §20 |
| D6 | GAS 직접호출 제거 여부 | 미확정 | §21 대안 비교 결과 근본해결은 제거뿐 | 우회위험 지속 | 단계적 제거(Legacy부터) | 유지+서명검증 병행 | PM | Commit8-3 착수 전 | URL 비공개 유지 | 8-3 | 본 문서 §21 |
| D7 | GAS 요청 검증방식 | 미확정 | 서명/Token 중 택일 필요 | 구현 설계 불가 | FastAPI 발급 Token 검증(Proxy 구조와 결합) | HMAC 서명 | PM/개발팀 | Commit8-3 착수 전 | 없음 | 8-3 | 본 문서 §21 |
| D8 | FastAPI Proxy 적용 범위 | 미확정 | 예약생성/Legacy상태변경 중 우선순위 필요 | 구현 순서 불명확 | Legacy(무감사 위험 더 큼) 우선 | 예약생성 우선 | PM | Commit8-3 착수 전 | 없음 | 8-3 | 본 문서 §21/22 |
| D9 | Legacy 기능 종료·전환 시점 | 미확정 | Phase B B-1 이후 일정 필요 | 무기한 이원화 지속 | Commit8-4 결과 따라 재검토 | 현행 유지 | PM | Commit8-4 이후 | 현행 유지 | 8-4 | Legacy_Stage3_PhaseB_Design §14/17 |
| D10 | 예약변경 실제 업무 요구사항 | 미확정 | §22/23 참조 | 기능 방향 자체 불명 | 병원 운영팀 인터뷰로 확정 | 라벨 변경만 유지(기능 축소) | PM/병원운영팀 | Commit8-5 착수 전 | 현행(라벨만 변경) 유지, FAQ에 고지됨 | 8-5 | 본 문서 §23 |
| D11 | Slot 반환·재할당 정책 | 미확정 | 취소 시 즉시반환 vs 유예, 변경 시 재배정 알고리즘 필요 | 설계 불가 | 취소는 즉시 반환(단순), 변경은 D10 이후 재검토 | 유예 반환 | PM/병원운영팀 | Commit8-4/8-5 착수 전 | 없음 | 8-4/8-5 | Legacy_Stage3_PhaseB_Design §16 |
| D12 | 감사로그 보존기간 | 미확정 | 기존 backup_policy.md도 이 항목 없음 | 장기 추적성 정책 불명 | 로컬 JSON 감사로그 정책(1년, backup_policy §1)과 통일 | 별도 기간 설정 | PM | Commit8-6 착수 전 | 현행(무기한 보관 중, 삭제 정책 없음) | 8-6 | backup_policy.md |
| D13 | 운영 로그 접근권한 | 미확정 | 구조화 로깅 도입 시 접근 범위 필요 | 로그 오남용 위험 | 개발팀+PM 한정 | 전체 운영팀 | PM | Commit8-2 착수 전 | 없음 | 8-2 | 본 문서 §17 |
| D14 | GAS v3 유지 또는 v4 전환 여부 | v3 유지 중 | v4는 PII 응답 선택자 등 미세 차이 존재(§16) | 잘못된 버전 배포 위험 | 확인 전까지 v3 유지 | v4 검토 후 전환 | PM/전산담당 | 전환 검토 시점(비긴급) | v3 유지 | — | 본 문서 §16 |
| D15 | Staging 환경 구성방식 | 미확정, 존재 여부 자체 확인 필요 | E2E 검증 전제조건 | Commit8-7 착수 불가 | 별도 Sheets/GAS Staging 배포 | 로컬 Mock만으로 대체(제한적) | PM/개발팀 | Commit8-7 착수 전 | 없음 | 8-7 | 본 문서 §25 |
| D16 | Pilot 대상과 범위 | 미확정(제안만, §26) | 병원 운영 결정 필요 | Pilot 시작 불가 | 본 문서 §26 제안안 | 범위 축소/확대 | 병원/PM | Pilot 착수 전 | 없음 | 8-7/8-8 | 본 문서 §26 |
| D17 | Pilot 데이터 기준 | 비식별 우선 제안 | 실 PII 사용 시 별도 승인 필요 | 개인정보 오남용 위험 | 비식별/테스트 데이터 우선 | 즉시 실데이터(비권장) | PM/개인정보책임자 | Pilot 착수 전 | 비식별만 허용 | 8-7 | 본 문서 §26 |
| D18 | Pilot 성공·중단기준 | 초안 제시(§27/28) | 병원 승인 필요 | 판단 기준 불명 | 본 문서 §27/28 | 기준 조정 | PM/병원 | Pilot 착수 전 | 본 문서 초안 잠정 적용 | 8-7/8-8 | 본 문서 §27/28 |
| D19 | 백업 책임자 | 미확정(Sprint7 승계) | backup_policy §5-2 | 백업 누락 위험 | — | — | PM/개인정보책임자 | 운영 착수 전 | 없음 | 8-6 | backup_policy.md |
| D20 | 복구 책임자 | 미확정(Sprint7 승계) | 동일 | 복구 지연 | — | — | PM/전산담당 | 운영 착수 전 | 없음 | 8-6 | backup_policy.md |
| D21 | Rollback 결정권자 | 미확정(Sprint7 승계) | Rollback Guide §2 | 대응 지연 | — | — | PM | Pilot 착수 전 | PM 임시 겸임 | 8-6 | Rollback Guide |
| D22 | Rollback 실행책임자 | 미확정(Sprint7 승계) | 동일 | 대응 지연 | — | — | PM/전산담당 | Pilot 착수 전 | 개발 담당자 임시 겸임 | 8-6 | Rollback Guide |
| D23 | Pilot 최종 승인권자 | 미확정 | §26 | Pilot 시작 판단 불가 | — | — | PM | Pilot 착수 전 | PM 임시 | 8-7 | 본 문서 §26 |
| D24 | 장애 상위보고 체계 | 미확정(Sprint7 승계) | Failure_Response_Manual | 보고 누락 | — | — | PM/병원 | 운영 착수 전 | PM 단일 창구 | 8-6 | Failure_Response_Manual.md |
| D25 | Push 승인권자 | 미확정 | 세션 전체 정책상 매 Push 별도 승인 필요 | Push 시점 혼선 | PM | — | PM | Push 필요 시점마다 | PM 개별 승인 | 전체 | 본 문서 §35 |
| D26 | Netlify Deploy 승인권자 | 미확정 | 동일 | Deploy 시점 혼선 | PM | — | PM | Deploy 필요 시점마다 | PM 개별 승인 | 전체 | 본 문서 §35 |
| D27 | GAS Deploy 승인권자 | 미확정 | 동일, 과거 미반영 배포 사고 이력(STEP1.5) 존재 | GAS 재배포 시 혼선·사고 재발 위험 | PM | — | PM | GAS Deploy 필요 시점마다 | PM 개별 승인 + "새 버전" 배포 원칙 준수 | 8-3 | Rollback Guide §8 |
| D28 | 구버전 FastAPI cancel/change 엔드포인트(§8, 로컬 JSON 대상) 처리 방향 | 미확정(신규 발견) | 미사용 상태이나 코드는 실재, 향후 혼동 위험 | 유지 시 문서화 부담, 제거 시 기존 기능 삭제에 해당 | Sprint8에서는 그대로 유지(제거는 "기존 기능 삭제 금지" 원칙 위반 소지) | 명시적으로 Deprecated 주석만 추가(코드 변경 최소화, 별도 Commit 승인 필요) | PM | Commit8-1 이후 검토 | 문서에 "미사용 경로"로만 기록(완료됨, 본 문서 §8) | 8-1 이후 | 본 문서 §8 |

**어떤 항목도 이 문서에서 임의로 확정하지 않았다.**

## 32. Sprint8 위험등록부

정성 등급만 사용.

| ID | 위험 내용 | 근거 | 관련 구성요소 | 가능성 | 영향도 | 우선순위 | 현재 통제 | 잔여위험 | 대응방향 | 운영 전 필수조치 | 담당/결정주체 | 완료기준 | 운영 차단 여부 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SR1 | 관리자 실인증 미구현 | §8 코드 확인 | Admin Portal | 높음 | 높음 | Critical | 내부망 가정 | 매우높음 | 대안 A 구현(Commit8-2) | 실 인증 배포 | PM/전산 | 로그인 배포·검증 | 차단(전체운영) |
| SR2 | 역할·권한 검증 부족 | §8, reservation:change 등 일부만 적용 | FastAPI 전반 | 중간 | 중간 | High | 부분 적용 | 중간 | 신규 엔드포인트에 need_perm 일관 적용 | 코드 리뷰 기준 수립 | 개발팀 | 체크리스트 반영 | 조건부 |
| SR3 | GAS 직접호출 우회 | §11 코드 확인 | GAS | 높음 | 높음 | Critical | URL 비공개 | 높음 | 대안 조합(§21) 적용 | 통제 방식 결정·구현 | PM/전산 | 구현 완료 | 조건부 제한 |
| SR4 | 클라이언트 Secret 노출 가능성 | 설계 원칙(§13 주의사항) | 프론트엔드 코드 | 낮음(원칙상 금지) | 높음(발생 시) | High | 원칙으로만 금지, 코드 감사 미실시 | 낮음~중간(미확인) | 구현 시 Secret 클라이언트 배치 금지 검증 | 코드 리뷰 시 확인 | 개발팀 | 코드 감사 통과 | 조건부 |
| SR5 | Legacy 상태전이 우회 | §12/22 | Legacy Portal | 중간 | 높음 | High | UI 차단(예약확정만) | 높음 | Phase B 우선순위 조정(취소부터) | Commit8-4 결정 | PM | Decision Required 완료 | 조건부 |
| SR6 | 예약변경 실제 일정 미반영 | §13 | Legacy Portal | 확인됨(상시) | 중간 | High | 문서 고지만(FAQ 완료) | 중간 | D10 확정 후 재설계 | 요구사항 확정 | PM/병원 | D10 결정 | 조건부(고지 유지) |
| SR7 | Slot 중복·미반환 | §14 | Slot 관리 | 중간 | 중간 | High | 승인경로만 검증 | 중간 | 취소 경로 우선 개선(Commit8-4) | Slot 반환 로직 | PM/개발팀 | 구현·테스트 통과 | 조건부 |
| SR8 | Sheets 동시성 및 데이터 오염 | ADR-013, LockService 존재 | Google Sheets | 낮음 | 높음 | High | LockService(쓰기 직렬화) | 낮음~중간 | 백업정책 확정(§24) | D19~D20 결정 | PM | 정책 확정 | 조건부 |
| SR9 | 감사로그 부족 | §17 | Legacy Portal | 확인됨(상시) | 중간 | High | FastAPI 경로만 기록 | 높음 | Proxy 구조 도입 시 로그 통합 | Commit8-3/8-4 | PM | 구현 완료 | 조건부 |
| SR10 | GAS v3/v4 혼선 | §16(신규 미세차이 발견) | GAS 배포 | 낮음 | 높음 | Medium | 문서 v3 고정 명시 | 낮음 | D14 확정 | v4 공식 확인 | PM/전산 | 확인 완료 | 아니오 |
| SR11 | Netlify-GAS 버전 불일치 | Sprint7 승계 | 배포 절차 | 중간 | 중간 | Medium | 수동 대조 | 중간 | 체크리스트 준수 | 배포 시 이중확인 | 배포담당자 | 서명 확인 | 아니오 |
| SR12 | FastAPI 장애·Timeout | Sprint7 승계 | FastAPI | 낮음 | 중간 | Medium | Admin Portal만 8초 Timeout | 낮음 | Legacy/Reservation Portal Timeout 추가(범위 밖) | — | 향후 Commit | — | 아니오 |
| SR13 | 인증 도입 후 기존 기능 회귀 | 신규(Commit8-2 도입 예정) | 전체 API | 중간 | 높음 | Critical | 없음(아직 미구현) | 미확인 | Staging E2E 필수화(Commit8-7) | 회귀 테스트 전체 PASS | 개발팀 | 테스트 결과 | 조건부(E2E 전 Pilot 금지) |
| SR14 | Pilot에 운영 개인정보 사용 | §26 원칙 | Pilot 운영 | 낮음(원칙상 금지) | 매우높음(발생 시) | Critical | 비식별 우선 원칙(제안) | 낮음~중간(승인 전) | D17 확정, 원칙 준수 강제 | 승인 절차 수립 | PM/개인정보책임자 | 승인·정책 확정 | 조건부 |
| SR15 | 백업·복구 책임 미확정 | Sprint7 승계 | 거버넌스 | 확인됨 | 중간 | High | 없음 | 중간 | D19/D20 확정 | 지정 | PM | 지정 완료 | 조건부 |
| SR16 | Rollback 책임 미확정 | Sprint7 승계 | 거버넌스 | 확인됨 | 중간 | High | 없음 | 중간 | D21/D22 확정 | 지정 | PM | 지정 완료 | 조건부 |
| SR17 | 운영 연락망 미확정 | Sprint7 승계 | 거버넌스 | 확인됨 | 중간 | High | 문서 자리만 마련 | 중간 | D24 확정 | 지정 | 병원 | 지정 완료 | 조건부 |
| SR18 | 보안 구현 전 외부 공개 | 전체 판정 근거 | 전체 시스템 | 낮음(원칙상 금지) | 매우높음 | Critical | 내부망 가정, 강제 통제 없음 | 미확인 | 배포 절차에 명시적 게이트 추가 | Gate 승인 없이 공개 금지 원칙 | PM | Gate 체계 운영 | **차단** |
| SR19 | 테스트가 문서 수준에 머무를 위험 | Sprint7 Closeout R19 승계 | 전체 검증 | 확인 필요 | 높음 | High | 코드 테스트는 두터움, 실환경 검증 없음 | 높음(미확인) | Staging E2E 실제 수행(Commit8-7) | 검증 결과 보고 | PM/개발팀 | 보고서 완료 | 조건부 |
| SR20 | Push·Deploy 승인 없는 변경 반영 | 세션 정책 | 거버넌스 | 낮음(원칙 준수 중) | 높음(발생 시) | Critical | 전 세션 무Push 유지 중(41 commits ahead) | 낮음 | D25~D27 승인주체 명시 | 매 Push/Deploy 개별 승인 | PM | 절차 준수 | 조건부(원칙 유지로 통제) |

## 33. Sprint8 Commit 단위 실행계획

### Commit8-0(본 Commit)
- **목적**: 기준선 확인, 보안·Pilot 실행계획, Decision Required 통합
- **작업범위**: 문서 1건 작성
- **제외범위**: 코드 전체
- **예상 변경파일**: `docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md`
- **선행조건**: Sprint7 종료 커밋 확인(완료)
- **주요검증**: 문서 교차검증, PII/Secret 검사
- **완료기준**: PM 승인
- **위험**: 없음(문서 작업)
- **PM 승인 Gate**: 필요
- **Push/Deploy**: 없음

### Commit8-1
- **목적**: 관리자 인증·인가 상세설계, Threat Model, 테스트계획
- **작업범위**: 설계 문서만(대안 A 기준 상세 설계, D1~D5 결정 반영)
- **제외범위**: 실제 코드 구현
- **예상 변경파일**: 신규 설계 문서(파일명 미정, PM 승인 후 확정)
- **선행조건**: D1(인증방식), D4(Session/Token 정책) 결정
- **주요검증**: Threat Model 검토, 기존 구조 영향도 분석
- **완료기준**: PM 승인
- **위험**: 없음(설계 단계)
- **PM 승인 Gate**: **필수**(Commit8-2 착수 전)
- **Push/Deploy**: 없음

### Commit8-2
- **목적**: 관리자 인증·인가 최소 구현
- **작업범위**: 로그인 엔드포인트, 계정/역할/Session 또는 Token 처리, `require_user` 교체
- **제외범위**: 외부 IdP 연동(대안 B, 별도 결정 시)
- **예상 변경파일**: `src/api/api_server.py`, `src/api/routes_admin_portal.py`, 신규 인증 모듈, `data/users.json` 스키마 확장(비밀번호 필드 등, PM 승인 필요)
- **선행조건**: Commit8-1 PM 승인
- **주요검증**: 단위·통합 테스트, 기존 RBAC 테스트 회귀 확인
- **완료기준**: 신규 테스트 PASS + 기존 회귀 테스트 PASS
- **위험**: SR1, SR13
- **PM 승인 Gate**: 필수
- **Push/Deploy**: 없음(로컬 검증까지만)

### Commit8-3
- **목적**: GAS 직접호출 통제 구현
- **작업범위**: FastAPI Proxy 또는 승인된 검증방식 적용(D6~D8 결정에 따름)
- **제외범위**: Legacy Portal UI 전면 개편(호출 방식만 변경)
- **예상 변경파일**: GAS 신규 검증 로직 또는 FastAPI 신규 Proxy 엔드포인트, Legacy Portal 호출부
- **선행조건**: Commit8-2 완료, D6~D8 결정
- **주요검증**: Replay 방지, 권한검증, 감사로그 테스트
- **완료기준**: 신규 테스트 PASS
- **위험**: SR3, SR9
- **PM 승인 Gate**: 필수(GAS Deploy는 D27 별도 승인)
- **Push/Deploy**: GAS Deploy는 별도 승인 필요, Netlify/Git Push 없음

### Commit8-4
- **목적**: Legacy 상태전이 서버 검증(예약확정·취소·검진완료 우선)
- **작업범위**: §22 표 기준, Slot 반환 로직(취소) 우선 구현
- **제외범위**: 예약변경(요구사항 미확정으로 제외, Commit8-5로 이월)
- **예상 변경파일**: 신규 FastAPI 엔드포인트, `reservation_engine.py` 또는 신규 서비스 모듈
- **선행조건**: Commit8-3 완료, D9/D11 결정
- **주요검증**: Policy/Slot/감사로그 테스트
- **완료기준**: 신규 테스트 PASS
- **위험**: SR5, SR7
- **PM 승인 Gate**: 필수
- **Push/Deploy**: 없음

### Commit8-5
- **목적**: 실제 예약변경 설계 또는 구현(요구사항 확정 여부에 따라 범위 조정)
- **작업범위**: D10 결정 결과에 따름 — 요구사항 미확정 시 설계까지만
- **제외범위**: 요구사항 미확정 상태에서의 구현 착수
- **예상 변경파일**: 미정(요구사항 확정 후 결정)
- **선행조건**: D10, D11 결정
- **주요검증**: 미정
- **완료기준**: PM 승인
- **위험**: SR6
- **PM 승인 Gate**: 필수
- **Push/Deploy**: 없음

### Commit8-6
- **목적**: 백업·복구·Rollback 운영체계 확정
- **작업범위**: D19~D22, D24 결정 반영, 문서 갱신, 복구 리허설
- **제외범위**: 코드 변경
- **예상 변경파일**: `src/deploy/backup_policy.md`, `docs/CSHSP_Rollback_Guide.md`(갱신, 영향도 사전 보고 후)
- **선행조건**: 책임자 지정(D19~D22)
- **주요검증**: 복구 리허설 재실행
- **완료기준**: 리허설 PASS + 정책 문서 확정
- **위험**: SR8, SR15, SR16
- **PM 승인 Gate**: 필수
- **Push/Deploy**: 없음

### Commit8-7
- **목적**: Staging E2E 검증, 보안 회귀검증, 제한적 Pilot 준비도 평가
- **작업범위**: D15(Staging 구성) 결정 반영, 전체 회귀 재실행
- **제외범위**: 실제 Pilot 착수(다음 Commit)
- **예상 변경파일**: 테스트 결과 문서
- **선행조건**: Commit8-2~8-6 완료
- **주요검증**: 전체 회귀 스위트 + 신규 보안 테스트
- **완료기준**: 전체 PASS
- **위험**: SR13, SR19
- **PM 승인 Gate**: 필수
- **Push/Deploy**: 없음

### Commit8-8
- **목적**: Sprint8 Closeout, Pilot 승인자료, 잔여 위험 및 다음 Sprint 진입조건
- **작업범위**: Sprint7 Closeout과 동일 형식의 통합 문서
- **제외범위**: Pilot 실제 착수(별도 승인 필요)
- **예상 변경파일**: 신규 Closeout 문서
- **선행조건**: Commit8-1~8-7 완료
- **주요검증**: 전체 교차검증
- **완료기준**: PM 승인
- **위험**: 전체 위험등록부 재평가
- **PM 승인 Gate**: 필수
- **Push/Deploy**: 없음(Pilot 승인은 별도)

**이번 Commit(8-0)에서는 Commit8-1 이후 작업을 실제로 시작하지 않는다.**

## 34. 검증계획

Commit별로 §33에 명시된 "주요검증"을 따른다. 공통 원칙: 신규 기능은 기존 회귀 스위트(252개+ FastAPI 테스트, Admin Portal Parser/Legacy Guard/TD Cleanup 테스트, 백업 리허설)를 전부 재실행하여 회귀가 없음을 확인한 뒤에만 다음 Commit으로 진행한다.

## 35. Push·Deploy 통제

| 구분 | 승인주체(제안) | 비고 |
|---|---|---|
| Git Push | PM(D25) | 매 Push 시점 개별 승인, 세션 전체 정책과 일치 |
| Netlify Deploy | PM(D26) | 정적 파일 배포, 별도 승인 |
| GAS Deploy | PM(D27) | 과거 미반영 배포 사고 이력(STEP1.5) 존재 — "새 버전"으로만 배포 원칙 재확인 |

세 가지는 서로 다른 시점에 독립적으로 승인받으며, 하나의 승인이 나머지를 포함하지 않는다.

## 36. Sprint8 완료기준

Commit8-1~8-8 전체가 PM 승인을 받고, §32 위험등록부의 Critical 등급 항목(SR1, SR3, SR13, SR14, SR18, SR20)이 "차단" 또는 "조건부"에서 실질적으로 완화된 것이 §36 재평가(Commit8-8)에서 확인될 때 Sprint8을 종료 후보로 본다. 이 문서(Commit8-0) 자체는 Sprint8을 종료시키지 않는다.

## 37. 미확정 사항

- 병원 측 외부 IdP 존재 여부(D1 관련)
- 병원 네트워크 인프라의 VPN/내부망 격리 가능 여부(대안 C 관련)
- Staging 환경 실제 구성 여부(D15)
- Pilot 대상 인원·기간·처리량 한도(D16)
- 수검자 알림 메커니즘 존재 여부(§22)
- 구버전 FastAPI cancel/change 엔드포인트(§8/D28) 최종 처리 방향

이 사항들은 모두 [확인 필요] 또는 Decision Required로 표시되어 있으며 이번 문서에서 임의로 확정하지 않았다.

## 38. PM 승인 요청사항

1. §20 관리자 인증 대안 중 **대안 A(+대안 C 병행)**를 Sprint8 기본 방향으로 승인할지
2. §21 GAS 통제 대안 중 **FastAPI Proxy 일원화 + 서명/Token 검증** 조합을 기본 방향으로 승인할지
3. §31 Decision Required 중 Commit8-1 착수에 필요한 최소 항목(D1, D4)의 결정 일정
4. §33 Commit8-1 착수를 위한 PM 승인 여부
5. §28 Pilot 중단기준, §27 Pilot 성공기준 초안에 대한 병원 측 확인 필요 여부

---

## 교차검증 결과

1. Sprint7 종료보고서와의 일관성: §22~23 판정, P0 조치(A1~A3) 전부 본 문서 §5/§18~19에 반영 — 일치.
2. 실제 코드 근거와 문서 표현 일치 여부: §8/§11/§13/§16/§17 전부 이번 Commit에서 직접 재확인한 코드 근거 기반 — 일치, 단 §8/§16에서 기존 Sprint7 서술 대비 정밀화된 사실 발견(아래 충돌기록).
3. 관리자 인증 상태 표현: Not Implemented(Mock)로 일관.
4. GAS 직접호출 위험 표현: 무인증으로 일관, 코드 재확인.
5. FastAPI 적용 범위: "일부 엔드포인트만, Legacy/Reservation Portal은 미경유"로 일관.
6. Legacy 상태전이 설명: §12/22 Sprint7 서술과 일치, 세분화됨.
7. 예약변경 실제 기능 설명: "라벨만 변경"으로 일관.
8. Slot 처리 설명: 취소 시 미반환으로 일관.
9. GAS v3/v4 구분: v3=운영본 일관 유지, v4 미세 차이는 신규 발견으로 추가.
10. Decision Required 누락 검사: Sprint7 Closeout의 관련 D항목(D1~D18) 전부 본 문서에 승계·재번호 부여됨, 누락 없음.
11. 위험등록부 누락 검사: Sprint7 Closeout R1~R20과 본 문서 SR1~SR20 매핑 확인, 신규 위험(SR4/SR13/SR19/SR20 일부)은 Sprint8 신규 작업(인증 도입)에 따른 정당한 추가.
12. Pilot 승인 Gate: §29/§33 Commit8-7/8-8에 반영, 자동 진입 없음.
13. Push·Deploy 별도 승인 표현: §35에서 3개 항목 개별 승인으로 명시.

### 충돌기록

- **충돌 ID**: CF-01
- **관련 문서**: `Operation_Readiness_Assessment_v1.0.md` §3-1, `Sprint7_Closeout_and_Operational_Readiness_Consolidation.md` §8(구성요소 상태표)
- **관련 코드**: `src/api/api_server.py` L281-302, `src/reservation/reservation_engine.py` L445-600
- **문서상 내용**: "예약변경/취소/검진완료가 FastAPI 검증·감사·전용 테스트 전무"
- **실제 확인 내용**: FastAPI에 `/api/reservations/{rid}/cancel|change|complete|no-show` 엔드포인트가 실제로 존재하고 권한 검사(`reservation:cancel`/`reservation:change`) 코드도 있으나, 대상 데이터가 `data/reservations.json`(ADR-013 이후 비-SSOT)이고 어떤 Portal UI도 호출하지 않는 미사용 경로임
- **확인되지 않은 부분**: 이 엔드포인트가 애초에 어느 Sprint에서 왜 만들어졌는지(구 아키텍처 잔재로 추정되나 커밋 이력 상세 추적은 이번 Commit 범위 밖), 감사로그 연결 여부
- **보안·운영 영향**: 낮음(실사용되지 않으므로 즉각적 위험은 아니나, 문서가 "엔드포인트 자체가 없다"고 부정확하게 서술하면 향후 담당자가 "이미 구현되어 있다"고 오인해 이 경로를 그대로 활성화할 위험이 있음 — 이 경로는 비-SSOT 데이터를 다루므로 그대로 활성화하면 오히려 위험)
- **필요한 결정**: D28(§31) — 유지/Deprecated 표시/제거 중 결정
- **이번 Commit 처리 여부**: 문서에 정확히 반영만 함(§8), 코드 변경 없음, 최종 처리는 D28로 이월

- **충돌 ID**: CF-02
- **관련 문서**: `docs/CSHSP_Rollback_Guide.md` §8, `docs/DEPLOY_GUIDE_new.md` §2-0, `ARCHITECTURE.md`
- **관련 코드**: `app/apps_script/sheets_api_v4_deploy_new.gs` 헤더 주석
- **문서상 내용**: "v4는 핵심 로직이 v3와 동일, 변경 없음"
- **실제 확인 내용**: 핵심 CRUD 로직은 동일하나 CORS preflight 처리, PII 응답 선택자 등 6가지 부가 변경사항이 파일 자체 헤더에 명시되어 있음
- **확인되지 않은 부분**: 이 변경사항들이 실제로 운영에 영향을 주는지(미배포 상태이므로 실증 불가)
- **보안·운영 영향**: 낮음(v3 유지 중이므로 즉각 위험 아님), 단 향후 v4 전환 검토 시 PII 응답 선택자 항목은 개인정보 노출 범위 재검토 필요
- **필요한 결정**: D14(§31)
- **이번 Commit 처리 여부**: 문서에 정확히 반영만 함(§16), 기존 문서(Rollback Guide 등) 수정하지 않음(범위 밖 — 필요 시 별도 Commit에서 정밀화 제안)

## 완료 조건 준수 확인

이 문서 작성 중 애플리케이션 코드·테스트 코드·설정·API·Business Rule·Google Sheets 구조·Apps Script·Netlify 설정·운영 데이터를 변경하지 않았다(코드는 Read/Grep으로만 조사). 인증 기능을 구현하지 않았다. 보호 대상 파일(`ADR-015_Slot_Status_Policy_Draft.md`, `tests/sprint3_rbac_test_result.csv`)은 읽지 않았다. 미확정 정책을 임의로 확정하지 않았다. Push, Deploy, Commit8-1 이후 작업 착수 없음.
