# Sprint8 관리자 인증·인가 상세설계 및 Threat Model

> 작성: Sprint8 Commit8-1(2026-07-31) — 신규 독립 문서.
> 기준선: `32ff81fbb77443687d2ff48bdbb2321743480c74`("docs: establish sprint8 security and pilot readiness plan")
> 이 문서는 **설계·계획 문서이며 구현 완료 보고서가 아니다.** 이번 Commit에서 인증 코드는 구현하지 않는다.

---

## 1. 문서 목적

Commit8-0에서 승인된 기본방향(대안 A: FastAPI 중심 인증·인가 + 대안 C: 내부망/VPN 병행, 서버 관리형 세션)을 실제 저장소 구조에 맞게 상세 설계하고, Threat Model과 테스트계획을 수립하여 Commit8-2(최소 구현) 착수 여부를 PM이 판단할 수 있는 근거를 제공한다.

## 2. 적용 범위

관리자 인증·인가 상세 아키텍처, Trust Boundary, 세션 설계, 사용자·역할·권한 모델, X-User-Id Mock 제거·격리 계획, FastAPI-GAS 서버 간 인증 경계, 감사로그 설계, Threat Model, 테스트계획, Commit8-2 진입 Gate.

## 3. 제외 범위

인증 코드 구현, 테스트 코드 작성, 설정·환경변수 변경, API 실제 변경, Secret 생성, Google Sheets/Apps Script/Netlify 변경, Push, Deploy, Pilot 시작, Commit8-2 착수.

## 4. 승인 기준선

Commit `32ff81fbb77443687d2ff48bdbb2321743480c74`("docs: establish sprint8 security and pilot readiness plan") — 현재 HEAD와 일치 확인됨(재검증 완료). Commit8-0 신규 문서 `docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md` 존재 확인됨.

## 5. 참조 문서

`docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md`, `docs/Sprint7_Closeout_and_Operational_Readiness_Consolidation.md`, `Operation_Readiness_Assessment_v1.0.md`, `Legacy_Stage3_PhaseB_Design_v1.0.md`, `ARCHITECTURE.md`, `DECISIONS.md`(ADR-013), `docs/CSHSP_Rollback_Guide.md`, `docs/CSHSP_Failure_Response_Manual.md`, `docs/DEPLOY_GUIDE_new.md`, `src/deploy/backup_policy.md`, `src/deploy/production_checklist.md` — 전부 실경로 존재 확인 완료(§22 검증 참조).

## 6. 코드 근거

`src/api/api_server.py`, `src/api/routes_admin_portal.py`, `src/services/sheets_readonly_service.py`, `src/services/sheets_write_service.py`, `src/reservation/reservation_engine.py`, `src/reservation/reservation_audit.py`, `data/roles.json`, `.env.example`, `app/apps_script/sheets_api_v3_final.gs`/`v4_deploy_new.gs`, `app/pages/admin_portal_new.html`, `app/pages/admin_reservations_v2_new.html` — 이번 Commit에서 직접 Read/Grep으로 재확인.

## 7. 사실·평가·계획 구분 원칙

이 문서에서 "확인됨"은 코드로 직접 재확인한 사실, "설계"는 이번 Commit에서 제시하는 목표 상태(미구현), "권장"은 여러 대안 중 저자의 제안(최종 결정 아님), "[확인 필요]"는 이 저장소만으로 판단 불가능한 사항, "Decision Required"는 PM/병원의 결정이 필요한 사항이다.

## 8. 현재 인증 상태

**확인됨**: `src/api/api_server.py`의 `require_user()`(L162)가 `X-User-Id` 헤더 값을 `data/users.json` 사용자 목록과 대조하고 `status=="ACTIVE"`만 확인한다. 비밀번호·토큰·서명 검증 코드는 저장소 전체에서 0건(grep 재확인: `password`/`bcrypt`/`hashlib`/`passlib` 키워드 매치 없음). 로그인/로그아웃 API 엔드포인트도 0건(`/login`, `/logout` 경로 매치 없음). 코드 주석(L13)에 "Sprint E에서 실제 인증(JWT/세션)으로 교체 예정"이라는 문구가 있어, 현재 상태가 설계 당시부터 임시 조치로 의도되었음이 코드로 확인된다.

## 9. 현재 인가 상태

**확인됨**: `has_perm()`/`need_perm()`(`api_server.py` L170-177)이 `data/roles.json`의 역할별 `permissions` 배열을 확인한다. `reservation:view`, `reservation:change`, `slot:manage`, `patient:view`, `notification:draft`, `notification:send`, `audit:view` 등 일부 엔드포인트에 실제 적용되어 있다(코드 라인 재확인). `routes_admin_portal.py`에도 별도의 `need_perm` 유사 구현이 있다(L82).

## 10. 현재 사용자·역할·권한 구조

`data/roles.json`에 DIRECTOR/ADMIN/STAFF/CRM/AI-AGENT 5개 역할(Sprint7 문서 승계, 이번에 파일 존재만 재확인). 사용자는 `data/users.json`에 저장되며 `id`, `status`, `roleId` 필드로 식별·활성상태·역할이 결정된다(코드로 확인된 필드만 기술, 스키마 전체는 확인 안 함— [확인 필요]).

## 11. 현재 감사로그 상태

**확인됨**: `src/reservation/reservation_audit.py`의 `append_audit(data_dir, action, entity_type, entity_id, actor_user_id, before, after, channel, note)`가 `data/audit_logs.json`에 기록을 추가한다. `action`은 사전 등록된 `AUDIT_EVENTS` 목록에 있어야만 허용된다(화이트리스트 방식). 레코드는 `id`(`AUD-YYYYMMDD-NNNN`), `timestamp`, `actorUserId`, `actorRole`, `action` 등을 포함한다(코드 확인). 이 메커니즘은 승인/거절에는 연결되어 있으나 Legacy Portal 상태변경에는 연결되어 있지 않다(Sprint7 문서에서 이미 확인된 사실, 이번에 재확인하지 않음 — 파일 미변경이므로 유효).

## 12. 현재 FastAPI–GAS 호출 경계

**중요 재확인 사항(Commit8-0 대비 정밀화)**: `routes_admin_portal.py`가 `sheets_readonly_service`(`ping`/`list_reservations`/`get_reservation`/`get_summary`)와 `sheets_write_service`(`update_status`)를 import해 사용한다(코드 확인, L45-46). 즉 **Admin Portal의 승인/거절/조회 흐름은 이미 FastAPI가 서버측에서 GAS를 호출하는 구조이며, 브라우저가 직접 GAS를 호출하지 않는다.** `sheets_write_service._WRITE_ACTIONS = ("updateStatus",)`로 쓰기 액션이 1개로 화이트리스트 제한되어 있다(코드 확인, 최소권한 원칙이 이미 부분 적용됨). 두 서비스 모두 `CSHSP_GAS_WEBAPP_URL` 환경변수로 GAS URL을 얻으며, 이 값 자체가 유일한 "자격증명"이다 — GAS 쪽에는 이 호출이 FastAPI로부터 온 것인지 검증하는 별도 수단이 없다(§13과 동일한 근본 한계가 서버 간 호출에도 적용됨).

## 13. 현재 브라우저–GAS 직접호출 위험

**확인됨**(grep 재확인): `app/pages/admin_dashboard_v2_new.html`, `admin_dashboard_v3_new.html`(구버전 Dashboard), `admin_reservations_v2_new.html`(Legacy Portal), `reservation_v2_new.html`, `reservation_v3_new.html`(Reservation Portal)이 `google_sheets_service_v2_new.js` 등을 통해 GAS Web App URL을 브라우저에서 직접 호출한다. **`admin_portal_new.html`(현재 사용 중인 Admin Portal)은 이런 직접호출 코드가 0건**이다(grep 재확인, §12와 일치). GAS(`doGet`/`doPost`)는 호출자가 브라우저든 FastAPI든 구분하지 않으므로, Web App URL이 유출되면 어느 경로로든 무인증 접근이 가능하다(Commit7-3/Commit8-0에서 이미 확인된 사실, 이번에 코드 재확인).

## 14. 문서와 코드 간 충돌

이번 Commit에서 신규로 발견된 충돌은 없다(Commit8-0에서 이미 CF-01/CF-02로 기록됨). 다만 아래를 **정밀화 사항**으로 기록한다(충돌은 아니나 기존 서술의 해상도를 높임):

- **정밀화-01**: Commit8-0 §21은 "GAS 직접호출 통제"를 위해 "FastAPI Proxy 일원화"를 신규 구축 대상으로 서술했으나, 실제로는 Admin Portal 승인/거절/조회 경로에 한해 이 Proxy 구조가 **이미 존재**한다(§12). 남은 작업은 이 기존 Proxy 경로에 서버 간 인증을 추가하는 것과, Legacy/Reservation Portal을 동일 패턴으로 전환하는 것으로 범위가 좁혀진다.
- **정밀화-02**: `.env.example`에 `CSHSP_GAS_WEBAPP_URL`이 없다(실제 코드는 이 값을 필수로 요구함, §12). Sprint7 Commit7-4에서 이 환경변수 누락 문제가 배포 문서 4종에는 반영되었으나 `.env.example`은 그 4종에 포함되지 않아 누락이 남아있다. 이번 Commit에서는 `.env.example`을 수정하지 않는다(대상 외 문서) — 별도 정리 필요 사항으로만 기록한다.

## 15. 목표 보안 아키텍처

```mermaid
flowchart LR
  subgraph 외부망["외부 네트워크(Trust Boundary 1)"]
    ADMIN[관리자 단말/브라우저]
  end
  subgraph 내부망["병원 내부망/VPN(Trust Boundary 1 통과 후, 가정)"]
    ADMIN
  end
  subgraph EDGE["Netlify 정적 Admin Portal(Trust Boundary 2)"]
    PORTAL[admin_portal_new.html]
  end
  subgraph SERVER["FastAPI(Trust Boundary 3: 브라우저 세션 vs 서버 세션)"]
    AUTH[인증 처리계층 - 신규]
    SESS[(세션 저장소 - 신규)]
    PERM[인가: has_perm/need_perm - 기존]
    SVC[sheets_readonly/write_service - 기존]
  end
  subgraph DATA["사용자·역할·권한 저장소(기존, data/*.json)"]
    USERS[(users.json)]
    ROLES[(roles.json)]
  end
  subgraph AUDIT["감사로그 저장소(기존 확장)"]
    AUDITLOG[(audit_logs.json)]
  end
  subgraph GASB["Trust Boundary 4: FastAPI - GAS"]
    GAS[Google Apps Script]
  end
  SHEETS[(Google Sheets - SSOT)]

  ADMIN -->|HTTPS, 가정 [확인 필요]| PORTAL
  PORTAL -->|로그인 요청| AUTH
  AUTH -->|세션 생성/검증| SESS
  AUTH -->|사용자 조회| USERS
  PERM -->|역할·권한 조회| ROLES
  AUTH --> PERM
  PERM -->|승인된 요청만| SVC
  SVC -->|서버 간 인증 - 신규 설계 대상| GAS
  GAS --> SHEETS
  AUTH -.감사기록.-> AUDITLOG
  PERM -.감사기록.-> AUDITLOG
  SVC -.감사기록.-> AUDITLOG
```

**범례**: 실선 화살표는 확인된 기존 흐름 또는 이번에 설계하는 목표 흐름, "신규"로 표시된 구성요소는 Commit8-2 이후 구현 대상, "기존"은 이미 코드로 확인된 구성요소. HTTPS 종료 지점은 이 저장소 코드로 확인할 수 없어 가정으로 표시했다(§37).

## 16. Trust Boundary

| # | 경계 | 현재 상태 | 목표 상태 |
|---|---|---|---|
| 1 | 관리자 단말 ↔ 외부 네트워크 | 통제 없음(코드로 확인 불가) | 대안 C(내부망/VPN) 적용 검토 |
| 2 | Netlify 정적 콘텐츠 ↔ FastAPI | 인증 없이 API 직접 호출 가능(Mock만) | 서버 관리형 세션 인증 |
| 3 | 브라우저 세션 ↔ 서버 세션 | 세션 개념 없음(Mock 헤더만) | HttpOnly/Secure 쿠키 + 서버측 세션 상태 |
| 4 | FastAPI ↔ GAS | 환경변수 URL만(자격증명 아님), 서버측 Proxy는 Admin Portal 경로에 일부 존재(§12) | 서비스 간 인증(서명/Token) 추가 |
| 5 | GAS ↔ Google Sheets | GAS 자체 권한(Google 계정), LockService로 직렬화 | 변경 없음(Sprint8 범위 밖) |
| 6 | 개발·Staging·운영환경 | 분리 여부 확인 안 됨(`.env` 기반 추정, [확인 필요]) | 환경별 Mock 활성화 정책 분리(§34) |
| 7 | 일반 사용자 Portal ↔ 관리자 Portal | 코드상 분리(별도 HTML/라우터)되어 있으나 인증 수준은 동일(Mock) | 관리자만 실 인증 요구 |
| 8 | Mock 인증 ↔ 운영 인증 | 미분리(동일 코드 경로) | 환경변수 기반 명시적 분리(§34) |

## 17. 관리자 로그인 흐름 (설계)

1. 관리자가 Admin Portal 로그인 화면에서 자격증명 입력(구현 방식은 D1 계열 결정 후 확정)
2. FastAPI가 `data/users.json`(또는 결정된 계정 저장소, DR8-1-01)에서 사용자 조회 및 자격증명 검증
3. 검증 성공 시 신규 세션 ID 발급(로그인 성공 시 항상 재발급, Session Fixation 방지)
4. 세션 상태(사용자ID, 역할, 발급시각, 유휴/절대 만료시각)를 서버측에 저장(DR8-1-07)
5. HttpOnly+Secure+SameSite 쿠키로 세션 ID만 브라우저에 전달(사용자 정보·권한 자체는 쿠키에 담지 않음)
6. 로그인 성공 감사로그 기록(§33)

## 18. 관리자 로그아웃 흐름 (설계)

1. 관리자가 로그아웃 요청
2. 서버측 세션 즉시 폐기(무효화, 삭제)
3. 클라이언트 쿠키 만료 지시(Set-Cookie 만료)
4. 로그아웃 감사로그 기록
5. 로그아웃 후 동일 세션 ID로 재요청 시 401 처리(§18 테스트 A 참조)

## 19. 세션 생성·갱신·만료·폐기 흐름 (설계)

- **생성**: 로그인 성공 시(§17)
- **갱신**: 유효 요청마다 유휴시간 타이머 갱신(절대 유효시간은 갱신 안 됨, DR8-1-08/09)
- **만료**: 유휴시간 또는 절대 유효시간 초과 시 서버측에서 무효 처리, 다음 요청에서 401
- **폐기**: 로그아웃, 계정 비활성화, 역할 변경(재검증 필요 시), 관리자에 의한 강제 폐기(전체 세션 무효화 기능 필요, DR8-1-06과 연관)

## 20. 인증 실패 처리 (설계)

401 반환, 실패 원인은 사용자에게 최소 정보만 노출("자격증명이 올바르지 않습니다" 수준, 계정 존재 여부를 노출하지 않음 — 현재 Mock 코드는 `f"유효하지 않은 사용자: {x_user_id}"`처럼 식별자를 그대로 노출하는데, 이는 실 인증 전환 시 지양해야 할 패턴으로 별도 기록). 반복 실패는 감사로그 기록 + 계정 잠금 정책 검토(DR8-1-12/13).

## 21. 권한거부 처리 (설계)

403 반환, 요청한 권한명은 로그에는 기록하되 응답 본문에는 필요한 최소 정보만(현재 `api_server.py` L177처럼 `f"권한 없음: {perm} 필요 (현재 역할 ...)"`을 그대로 반환하는 방식은 정보 노출 관점에서 재검토 대상 — 기본 거부(Deny by default) 원칙은 이미 코드 구조(`need_perm`이 예외 아니면 통과 안 시킴)와 일치하므로 유지).

## 22. 계정 비활성화 처리 (설계)

계정 `status`가 `ACTIVE`가 아니게 되는 즉시(현재도 `require_user`가 이 값을 확인함, §8) 해당 계정의 모든 활성 세션을 서버측에서 무효화해야 한다(현재는 세션 개념 자체가 없어 이 처리도 없음 — 신규 설계 대상).

## 23. 역할·권한 변경 처리 (설계)

역할이 변경되면 기존 세션의 권한 정보를 재검증하거나 세션을 폐기해야 한다(그렇지 않으면 강등된 관리자가 이전 권한으로 계속 동작 가능 — Threat T-04). 두 가지 방식(즉시 폐기 vs 다음 요청 시 재검증) 중 택일은 Decision Required로 남긴다(구현 난이도상 즉시 폐기가 더 단순 — 권장).

## 24. 사용자·역할·권한 관리모델

| 항목 | 현재 상태 | 목표/Decision Required |
|---|---|---|
| 사용자 식별자 | `id`(예: `USR-xxxx`, `users.json`) | 유지 |
| 계정 상태 | `status`(ACTIVE 등, 확인됨) | 유지 + 세션 연동(§22) |
| 역할 | `roleId`(단일 역할로 추정, 코드상 `user.get("roleId")` 단수 필드) | **다중 역할 미지원으로 확인됨** — 필요시 향후 검토(Sprint8 범위 밖) |
| 권한 | `roles.json`의 `permissions` 배열, `"*"` 와일드카드 지원 확인됨 | 유지 |
| 역할 상속 | 코드상 확인 안 됨(단순 배열 매칭으로 보임) | [확인 필요] |
| 권한 부여/회수 방식 | `roles.json` 직접 편집으로 추정(전용 API 없음, grep 결과 역할 관리 엔드포인트 미확인) | Decision Required(DR8-1-06) |
| 계정 비활성화 | `status` 필드 변경(수동으로 추정) | §22 세션 연동 추가 |
| 퇴직·부서이동 처리 | 코드/문서에 절차 없음 | Decision Required(DR8-1-05) |
| 최소권한 | 역할별 permissions 배열로 구현되어 있음(원칙 자체는 이미 반영) | 신규 역할 추가 시 최소권한 재검토 |
| 직무분리 | 승인/거절 권한과 Slot 관리 권한이 코드상 분리되어 있음(`reservation:*` vs `slot:manage`) | 유지 |
| 관리자 계정 생성 | 전용 API 없음(추정, `users.json` 직접 편집) | Decision Required(DR8-1-04) |
| 서비스 계정과 사람 계정 분리 | 현재 미분리(FastAPI-GAS 호출은 사람 계정과 무관한 URL 기반, §12) | §35 설계로 분리 |
| 개발·Staging·운영계정 분리 | 확인 안 됨 | Decision Required(DR8-1-24) |

## 25. 서버 관리형 세션 설계

### 세션 저장소 대안 비교

| 대안 | 구조 | 장점 | 단점 | 다중 인스턴스 | 장애영향 | 운영난이도 | 보안위험 | 현재 저장소 영향 | Pilot 적합성 | 전체운영 적합성 | 권장 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 애플리케이션 메모리 | 프로세스 내 dict 등 | 구현 최단 | 재시작 시 전체 세션 소실, 다중 인스턴스 불가 | 미지원 | 큼(재시작=전원 로그아웃) | 낮음 | 낮음(외부 노출 없음) | 없음 | 낮음(운영 중 재시작 시 불편) | 부적합 | 비권장(단, 최초 프로토타입 검증용으로만) |
| 파일 기반(기존 `session_store.py` 패턴 재사용) | `sessions.json`류 파일, 이미 AI 채팅 세션에 사용 중인 `FileSessionStore` 패턴 확인됨(`routes_agents.py` L41/78) | **기존 코드 패턴 재사용 가능**(신규 학습비용 낮음), 재시작에도 세션 유지 | 파일 락 필요(기존 `file_lock.py` 재사용 가능), 다중 서버 인스턴스 확장 시 한계 | 제한적(단일 서버 파일 시스템 공유 시에만) | 중간 | 낮음(기존 백업 정책 재사용 가능) | 중간(파일 접근권한 관리 필요) | 낮음(패턴만 재사용, 신규 파일) | 높음 | 가능(단일 서버 운영 규모에는 적합) | **권장(1순위)** — 단일 병원, 소규모 운영 규모와 기존 아키텍처 철학(신규 외부 의존성 최소화)에 부합 |
| 기존 데이터 저장구조(`data/*.json`) 직접 활용 | Core Data Layer Entity로 신규 `Session` 추가 | 기존 `file_lock.py`/`DataLock` 재사용 | 세션은 다른 Entity보다 훨씬 빈번히 쓰기 발생 — 락 경합 위험 | 파일 기반과 동일 | 중간 | 낮음 | 중간 | 중간(신규 Entity 추가는 스키마 영향) | 중간 | 가능 | 파일 기반(전용 파일)과 유사하나 락 경합 우려로 차순위 |
| Redis 등 별도 세션 저장소 | 외부 인메모리 스토어 | 다중 인스턴스 지원, 고성능 | **이 저장소에 Redis 관련 코드/설정이 존재하지 않음(확인됨, 존재한다고 표현하지 않음)** — 신규 인프라 도입 필요 | 지원 | 낮음(Redis 자체 이중화 시) | 높음(신규 인프라 운영 부담) | 중간(네트워크 노출 관리 필요) | 큼(신규 서버 구성) | 낮음(Pilot 규모에 과함) | 장기적으로 유리할 수 있음 | 비권장(현재 규모 대비 과설계) |

**권장안**: 파일 기반(기존 `session_store.py`/`file_lock.py` 패턴 재사용). 최종 결정은 DR8-1-07.

### 기타 세션 설계 항목

- **세션 생성 조건**: 자격증명 검증 성공 시에만(§17)
- **세션 ID 생성 원칙**: 암호학적으로 안전한 난수 기반(구체 알고리즘은 Commit8-2 구현 설계 대상, 이번 문서에서는 "예측 불가능해야 한다"는 요구사항만 명시)
- **로그인 성공 시 재발급**: 필수(§17 STEP3, Session Fixation 방지, Threat T-05)
- **서버측 저장정보**: 사용자ID, 역할, 발급시각, 마지막 활동시각, 만료시각(유휴/절대 모두), 세션 상태(활성/폐기)
- **브라우저 Cookie 저장정보**: 세션 ID만(사용자 정보·권한 정보는 저장 금지 — PM 승인사항 준수)
- **Cookie Path/Domain**: Admin Portal 경로로 최소화 권장(구체 값은 배포 도메인 확정 후 결정, [확인 필요])
- **유휴시간/절대 유효시간**: 아래 별도 비교
- **동시 로그인 정책**: 미정(DR8-1-11) — 검진센터 관리자 소수 인원 특성상 단일 세션 강제도 검토 가능하나 업무 편의성(여러 창 사용 등) 상충 가능
- **비정상 세션 탐지**: 이번 Sprint 범위에서는 미설계(향후 과제)
- **세션 저장소 장애**: 파일 기반 채택 시 기존 `file_lock.py` 장애 처리 패턴 재사용, 장애 시 신규 로그인/세션 검증 실패 → 관리자 작업 중단(PM 승인 원칙 "보안 우회보다 작업 중단" 준수)
- **세션 정리**: 만료된 세션의 파일 정리 배치 필요(주기 결정은 Decision Required 아님, 구현 세부사항)
- **CSRF Token과의 관계**: §27에서 별도 설계

### 유휴시간·절대 유효시간·재인증 조건 대안 비교

| 대안 | 유휴시간 | 절대 유효시간 | 재인증 조건 | 보안 | 운영 편의성(검진센터 특성상) | 권장 |
|---|---|---|---|---|---|---|
| 대안 1(엄격) | 15분 | 4시간(반나절 근무 단위) | 절대 만료 시 항상 재로그인 | 높음 | 낮음(잦은 재로그인으로 업무 중단 가능) | 고보안 요구 시 |
| 대안 2(중간, 권장) | 30분 | 8시간(1일 근무 단위) | 절대 만료 또는 역할변경 시 재로그인 | 중간 | 중간(1일 1회 로그인 수준) | **권장** — 검진센터 업무 특성(반나절~하루 단위 연속 사용)과 보안의 균형 |
| 대안 3(느슨) | 60분 | 24시간 | 절대 만료 시만 | 낮음 | 높음 | 비권장(공용 단말 사용 가능성 고려 시 위험) |

**최종값은 Decision Required(DR8-1-08/09)로 남긴다.** 검진센터 관리자 업무 특성(공용 PC 사용 여부 등, [확인 필요])에 따라 조정 필요.

## 26. Cookie 보안속성

| 속성 | 설계값 | 근거 |
|---|---|---|
| HttpOnly | 필수 적용 | PM 승인사항, XSS를 통한 세션 탈취 방지(Threat T-08) |
| Secure | 필수 적용 | PM 승인사항, 평문 전송 방지 — **HTTPS 배포가 전제**되어야 하며 현재 배포 환경의 HTTPS 여부는 [확인 필요](§37) |
| SameSite | `Strict` 또는 `Lax` 중 택일(권장: `Lax` — 관리자가 외부 링크로 진입하는 시나리오는 없다고 가정되나 완전 차단은 UX 저해 가능, [확인 필요] 후 `Strict`로 강화 검토) | CSRF 방어 보완(§27) |
| Path | Admin Portal 경로로 제한 권장 | 최소 노출 |
| Domain | 배포 도메인 확정 후 결정 | [확인 필요] |

## 27. CSRF 방어

세션 쿠키 기반 인증은 CSRF에 노출되므로 상태변경 요청(승인/거절/변경 등 POST/PUT/DELETE)에 CSRF Token 검증을 추가한다. 설계: 로그인 시 CSRF Token 발급(세션과 연결) → 프론트엔드가 요청 헤더 또는 폼 필드에 포함 → 서버가 세션의 Token과 대조. `SameSite=Lax` 이상과 병행하여 심층 방어를 구성한다(SameSite 단독으로는 모든 브라우저·시나리오를 커버하지 못하므로 Token 병행 필요).

## 28. Session Fixation 방어

로그인 성공 시 항상 신규 세션 ID 재발급(§17, §25) — 로그인 전 발급된 세션 ID를 로그인 후에도 그대로 사용하지 않는다.

## 29. Session 탈취 대응

HttpOnly(XSS 통한 탈취 방지) + Secure(전송 중 탈취 방지) + 유휴/절대 시간 제한(탈취된 세션의 유효기간 최소화) + 이상 징후 시 수동 강제 폐기 기능(§19)의 조합으로 대응한다. 자동 이상탐지(IP 변경 감지 등)는 이번 Sprint 설계 범위 밖(향후 과제).

## 30. 권한상승 방어

서버측이 세션에 저장된 역할 정보만을 신뢰하고, 클라이언트가 요청에 포함시키는 어떤 역할·권한 주장도 신뢰하지 않는다(PM 승인 원칙과 일치, 기존 `has_perm()`도 이미 서버측 `roles.json` 조회 방식이라 이 원칙에 부합함 — 유지). 역할 변경 시 기존 세션 재검증(§23).

## 31. Replay 방어

관리자 브라우저 세션 자체는 쿠키 기반이라 고전적 Replay(요청 재전송) 방어가 상태변경 API의 CSRF Token 1회성/세션 바인딩으로 부분 커버된다. FastAPI-GAS 서버 간 호출의 Replay 방어는 별도로 §35에서 설계한다(Timestamp/Nonce).

## 32. Brute Force 및 로그인 남용 대응

로그인 실패 횟수 제한 및 계정 잠금 정책이 필요하다(현재 코드에 이런 메커니즘 0건, `RateLimit` 클래스는 AI 채팅용으로만 존재하며 로그인에는 적용되지 않음 — 확인됨). 정책 값(임계치, 잠금시간)은 Decision Required(DR8-1-12/13)로 남긴다.

## 33. 감사로그 설계

기존 `append_audit()`(§11)을 재사용하고, `AUDIT_EVENTS` 화이트리스트에 아래 신규 이벤트를 추가하는 방식을 권장한다(신규 로거를 만들지 않음 — 기존 구조 재사용 원칙 준수).

### 신규 감사 이벤트(최소)

로그인 성공/실패/반복실패, 로그아웃, 세션 생성/재발급/만료/강제폐기, 계정 비활성화, 역할변경, 권한변경, 인증되지 않은 요청, 권한거부, CSRF 검증실패, Replay 의심, 관리자 상태변경 요청, FastAPI-GAS 호출, GAS 응답실패, Sheets 변경 성공/실패, Mock 인증 사용시도, 보안설정 변경, 감사로그 접근.

### 로그 필드(검토)

Event ID, Event Type, Timestamp, Request ID/Correlation ID(현재 코드에 이 개념 없음 — 신규 도입 필요), Actor ID, Role, Action, Target Type, Target ID, Result, Failure Reason Code, Source IP 처리정책([확인 필요], 현재 IP 로깅 코드 없음), User-Agent 처리정책(현재 없음), Session ID의 안전한 식별값(원문 아닌 해시 등), Environment, API Path, 관련 GAS Action, 관련 Sheets 변경결과.

### 원문 기록 금지/최소화 대상

비밀번호, Session ID 원문, CSRF Token, Service Token, HMAC Secret, 개인정보 전체값, 주민등록번호, 건강검진 결과, 불필요한 요청 본문 전체 — **기존 `_server_log()`(Commit5-2)가 이미 "PII-safe 필드만" 원칙으로 구현되어 있어 동일 원칙을 신규 이벤트에도 적용**한다.

감사로그 보존기간, 접근권한, 저장소, 위·변조 방지 방식은 Decision Required(DR8-1-18~20)로 관리한다.

## 34. X-User-Id Mock 제거·격리계획

| 항목 | 내용 |
|---|---|
| 현재 처리 위치 | `api_server.py` `require_user()`(L162), `routes_admin_portal.py` 동일 패턴(L53) |
| 현재 신뢰 경계 | 헤더 값을 그대로 신뢰(위조 가능, Threat T-01) |
| 위조 가능성 | 매우 높음 — HTTP 헤더는 클라이언트가 임의로 설정 가능 |
| 영향받는 API | `require_user`를 사용하는 모든 엔드포인트(Admin Portal 관련 대부분) |
| 개발·테스트에서 필요한 이유 | 실 로그인 없이 다양한 역할 시나리오를 빠르게 테스트하기 위해(기존 테스트 스위트 252개+가 이 방식에 의존) |
| 운영환경에서 위험한 이유 | 누구나 임의의 `X-User-Id`로 관리자 권한을 사칭 가능(Threat T-01, T-02) |
| 환경별 활성화 정책(설계) | 환경변수(예: `CSHSP_ENV=development/staging/production`, 신규 도입 필요 — 현재 이런 변수 없음, [확인 필요]로 표시)로 분기, `production`에서는 Mock 경로 자체가 컴파일/런타임에 비활성화 |
| 기본 비활성화 원칙 | Mock은 명시적으로 `development`/`test` 환경에서만 활성화, 그 외에는 기본 차단 |
| 운영 빌드 포함 여부 | 운영 배포 시 Mock 인증 코드 경로가 아예 도달 불가능하도록 설계(단순 조건문보다 실패-안전 구조 권장 — 환경변수 오설정 시에도 안전 측으로 동작해야 함) |
| 운영환경 요청 차단 방식 | `X-User-Id` 헤더가 운영환경에서 수신되면 그 자체를 감사로그(Mock 인증 사용시도)로 기록하고 401 반환 |
| Mock 활성화 실패안전 원칙 | 환경 판별 실패 시 **Mock 비활성화(운영 취급)를 기본값**으로 — "확인 안 되면 안전한 쪽" 원칙 |
| 테스트 대체방식 | 기존 테스트는 `require_user`를 테스트 환경에서 Dependency Override(FastAPI 표준 패턴)로 대체하거나, 테스트 전용 환경변수로 Mock을 유지 — 기존 252개+ 테스트가 이 경로에 의존하므로 **테스트 인프라 자체의 인증 방식을 바꾸는 것이지 실제 신뢰 경계를 낮추는 것이 아님**을 명확히 함 |
| 제거 또는 격리 순서 | ① 환경 분기 도입 → ② 운영환경에서 Mock 차단(코드) → ③ 실 인증 도입(Commit8-2) → ④ 테스트 인프라 전환 → ⑤ 최종적으로 Mock 코드 자체 삭제 여부 결정(Decision Required, DR8-1-21) |
| 회귀검증 | 기존 252개+ 테스트가 계속 PASS해야 함(§40) |
| Rollback 시 재활성화 금지 | **PM 승인사항** — 인증 관련 Rollback이 필요한 경우에도 Mock으로 되돌리지 않는다(§38, §56 Rollback 고려사항과 연계, 대신 서비스 중단을 택한다) |
| 완료 기준 | 운영환경에서 `X-User-Id` 단독으로는 어떤 보호된 엔드포인트도 통과하지 못함을 테스트로 확인 |

## 35. FastAPI–GAS 서버 간 인증설계

§12에서 확인했듯 Admin Portal 경로는 이미 서버측 Proxy(`sheets_readonly_service`/`sheets_write_service`)를 사용 중이다. 아래는 이 기존 서버 간 호출에 인증을 추가하는 대안이다.

| 대안 | 인증주체 | 자격증명 발급 | 저장위치 | 서명방식 | Replay방지 | GAS 구현영향 | FastAPI 구현영향 | 우회가능성 | 권장 |
|---|---|---|---|---|---|---|---|---|---|
| 1) HMAC 서명 | FastAPI(발급 없음, 사전 공유 Secret) | 배포 시 수동 설정(환경변수) | FastAPI: 서버 환경변수 / GAS: Script Properties(암호화 저장, Google 제공 기능) | 요청 본문+Timestamp를 Secret으로 HMAC 서명, GAS가 동일 계산으로 대조 | Timestamp+Nonce 추가 시 가능 | 중간(GAS에 서명 검증 로직 추가 필요) | 낮음(기존 서비스에 서명 생성만 추가) | 낮음(Secret 유출 전까지) | **권장(1순위)** — 외부 인프라 불필요, GAS Script Properties가 이미 Google이 제공하는 안전한 Secret 저장 방식 |
| 2) 단기수명 서비스 Token | FastAPI(자체 발급) | FastAPI가 자체 발급·검증 | 유사(환경변수 기반 시드) | Token 자체가 서명 성격 | Token 만료로 자연 방지 | 중간(GAS가 Token 검증) | 중간(Token 발급 로직 신규) | 낮음 | 대안(1과 유사 효과, 구현 복잡도만 약간 높음) |
| 3) JWT 기반 서비스 인증 | FastAPI(자체 발급) | 자체 발급 | 동일 | JWT 서명 | exp 클레임 | 중간 | 중간(JWT 라이브러리 신규 의존성) | 낮음 | 대안(신규 의존성 추가가 단점) |
| 4) 내부망/Origin 제한만 | 없음(네트워크 계층) | 해당없음 | 해당없음 | 없음 | 없음 | 없음 | 없음 | **높음 — 단독 사용 금지**(PM 승인사항, §21 Commit8-0에서 이미 부적합 판정) | 보완 수단으로만 |
| 5) GAS 배포 접근권한 제한 | Google 계정(배포 권한) | 해당없음 | 해당없음 | 없음 | 없음 | 없음 | 없음 | 호출자 인증과 무관한 계층(혼동 주의, Commit8-0에서 이미 지적) | 보완 수단으로만(개발 권한 제한 목적) |
| 6) 임시 Pilot 통제 | 없음(운영절차) | 해당없음 | 해당없음 | 없음 | 없음 | 없음 | 없음 | 매우 높음 | Commit8-2 이전 임시 가교로만, 최종 통제 아님 |

**권장안**: 대안 1(HMAC 서명, GAS Script Properties 활용). 서버 간 자격증명(Secret)은 관리자 브라우저 세션·쿠키와 완전히 분리된 별도 환경변수/Script Properties로 관리하며, 클라이언트 코드·Netlify 공개 번들·GitHub에는 어떤 형태로도 포함하지 않는다. **최종 결정은 Decision Required(DR8-1-15/16/17)로 남긴다.**

## 36. Secret 관리원칙

- 서버 간 인증 Secret은 FastAPI 서버 환경변수 + GAS Script Properties로만 저장(코드에 하드코딩 금지)
- 클라이언트(브라우저) 코드, Netlify 공개 번들, GitHub 저장소에는 어떤 Secret도 포함하지 않는다(기존 세션 전체의 일관된 원칙, 재확인)
- 관리자 세션 자격증명(쿠키의 세션 ID)과 서버 간 자격증명(HMAC Secret 등)은 별도 채널로 관리(PM 승인사항)
- Key Rotation 주기는 Decision Required(DR8-1-17)

## 37. 오류·장애·Timeout 처리

인증 서버(FastAPI) 장애 시: 관리자 요청은 실패(401/503)하며, **Mock 인증으로 자동 전환하지 않는다**(PM 승인사항, §38과 연계). 세션 저장소 장애 시에도 동일 원칙 — 신규 로그인/세션 검증이 실패하면 관리자 작업이 중단되는 쪽을 기본으로 한다("보안 우회보다 작업 중단"). HTTPS 종료 지점, Reverse Proxy 구성은 이 저장소의 코드/설정으로 확인할 수 없다(nginx 설정 등 검색 결과 0건) — **[확인 필요]**, 배포 환경 확인 후 Cookie Secure 속성 적용 가능 여부를 재검토해야 한다.

## 38. 인증 시스템 장애 시 운영원칙

**PM 승인사항 그대로 반영**: 운영 인증 실패 시 Mock 인증으로 우회하지 않는다. 인증 시스템 장애는 보안 우회가 아니라 관리자 작업 중단으로 대응하는 것을 기본 원칙으로 한다. 장애 시 대응 절차는 기존 `docs/CSHSP_Rollback_Guide.md`/`docs/CSHSP_Failure_Response_Manual.md`에 인증 관련 시나리오를 추가하는 것을 향후 과제로 남긴다(이번 Commit에서는 기존 문서 수정 안 함, §56).

## 39. 외부 IdP 확장 가능성

Commit8-0 대안 B(외부 IdP)는 이번에 확정하지 않는다. 설계상 확장 가능성만 남긴다: 인증 처리계층을 `require_user`와 유사하게 교체 가능한 단일 지점(Dependency)으로 유지하면, 향후 IdP 연동 시 이 지점만 교체하고 `has_perm()`/`roles.json` 기반 인가 구조는 그대로 재사용할 수 있다. 병원 측 IdP 존재 여부는 [확인 필요](DR8-1-23).

## 40. 내부망·VPN 보완 통제

**PM 승인사항 준수**: 내부망/VPN은 인증을 대체하지 않으며 §15 아키텍처의 Trust Boundary 1(관리자 단말↔외부 네트워크)에서 보완 통제로만 위치한다. 병원 네트워크 인프라의 VPN/내부망 격리 실제 구성 가능 여부는 이 저장소 범위 밖이며 [확인 필요](DR8-1-22).

## 41. Threat Model

STRIDE 준용, 정성 등급(높음/중간/낮음) 사용.

| ID | 위협 | 유형 | 경로 | 관련자산 | 현재통제 | 통제한계 | 목표통제 | 가능성 | 영향도 | 우선순위 | 잔여위험 | 구현전필수 | 운영차단 | 관련테스트 | 결정주체 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T01 | X-User-Id 위조 | Spoofing | HTTP 헤더 임의 설정 | 전 관리자 API | 없음(§8) | 헤더는 클라이언트 완전 통제 | 서버 세션 인증(§17) | 높음 | 높음 | Critical | 구현 전까지 매우 높음 | 예 | 예 | A그룹 | PM |
| T02 | 인증 없는 관리자 API 접근 | Spoofing/Elevation | 직접 API 호출 | 전 관리자 API | Mock만 | T01과 동일 | 서버 세션 인증 | 높음 | 높음 | Critical | 높음 | 예 | 예 | A그룹 | PM |
| T03 | 권한 없는 상태변경(승인 등) | Elevation | 유효 세션+역할 매칭 실패 | 예약 데이터 | `has_perm()`(부분) | 신규 엔드포인트 누락 시 검증 공백 가능 | 전 엔드포인트 일관 적용 | 중간 | 높음 | High | 중간 | 예 | 아니오 | D그룹 | 개발팀 |
| T04 | 역할·권한 변경 후 기존 세션 유지 | Elevation | 세션 미재검증 | 인가 시스템 | 없음(세션 자체 없음) | §23 설계 필요 | 역할변경 시 세션 폐기 | 중간 | 중간 | High | 중간 | 예 | 아니오 | B그룹 | 개발팀 |
| T05 | Session Fixation | Spoofing | 로그인 전 세션ID 재사용 | 세션 | 없음(세션 자체 없음) | §28 설계 필요 | 로그인 시 재발급 | 낮음(구현 전) | 높음 | High | 낮음(설계 반영 시) | 예 | 아니오 | B그룹 | 개발팀 |
| T06 | Session 탈취(XSS/네트워크) | Info Disclosure | XSS 또는 평문전송 | 세션 | 없음 | §29 설계 필요 | HttpOnly+Secure | 낮음~중간 | 높음 | High | 중간(HTTPS 여부 미확인) | 예 | 아니오 | B그룹 | 개발팀 |
| T07 | CSRF | Spoofing | Cross-Origin 상태변경 요청 | 관리자 상태변경 API | 없음 | §27 설계 필요 | CSRF Token+SameSite | 중간 | 중간 | High | 중간 | 예 | 아니오 | C그룹 | 개발팀 |
| T08 | XSS를 통한 세션 악용 | Info Disclosure | 프론트엔드 XSS 취약점(존재 여부 이번 조사 범위 밖) | 세션 | HttpOnly 설계로 부분 완화 예정 | XSS 자체 방지는 프론트엔드 코드 감사 필요(범위 밖) | HttpOnly + 별도 XSS 점검(향후) | [확인 필요] | 높음 | High | [확인 필요] | 예(HttpOnly는) | 아니오 | — | 개발팀 |
| T09 | Replay(서버 간 호출) | Tampering | GAS 요청 재전송 | Sheets 데이터 | 없음 | §31/35 설계 필요 | Timestamp+Nonce | 낮음 | 중간 | Medium | 낮음(구현 시) | 아니오(Pilot 전 권장) | 아니오 | E그룹 | 개발팀 |
| T10 | Brute Force/Credential Stuffing | Spoofing | 반복 로그인 시도 | 계정 | 없음(로그인 자체 없음) | §32 설계 필요 | 실패횟수 제한+잠금 | 낮음~중간 | 중간 | Medium | 중간 | 권장 | 아니오 | A그룹 | 개발팀 |
| T11 | 계정 공유 | Repudiation | 운영 관행 | 감사 추적성 | 없음(운영 관행 문제, 코드로 방지 불가) | 기술적 통제 한계 | 계정 공유 금지 운영정책 | [확인 필요] | 중간 | Medium | 중간(운영정책 의존) | 아니오 | 아니오 | — | 병원 |
| T12 | 퇴직자 계정 미회수 | Elevation | 운영 프로세스 누락 | 계정 | 없음(수동 관리 추정) | 자동화 없음 | 계정 생성·해지 절차(DR8-1-05) | 중간 | 높음 | High | 중간~높음 | 예(운영전) | 아니오 | — | 병원/PM |
| T13 | 브라우저 GAS 직접호출 | Tampering/Elevation | Legacy/Reservation Portal | GAS/Sheets | URL 비공개만 | Web App URL 유출 시 전면 무방비(§13) | Legacy Stage3 Phase B로 단계적 전환(Sprint8 범위 밖, 별도 Sprint) | 중간 | 높음 | Critical | 높음(Sprint8에서 미해결 예정) | 아니오(별도 Sprint) | 조건부(Legacy 경로 한정) | — | PM |
| T14 | GAS Action 직접호출(임의 action 파라미터) | Tampering | `doGet`/`doPost`의 action 분기 | GAS/Sheets | 없음(§13) | T13과 동일 근본원인 | 서버 간 인증(§35) 도입 후 GAS 자체도 서명 검증 추가 시 완화 | 높음 | 높음 | Critical | 높음(Sprint8 부분 해결) | 아니오(§35 설계만, 구현은 Commit8-3) | 아니오 | — | PM |
| T15 | CORS 우회 | Spoofing | Origin 위조(서버간 호출이나 비브라우저 클라이언트는 CORS 적용 안 됨) | FastAPI | `allow_origin_regex`(localhost 한정, §12 Commit8-0에서 확인) | **CORS는 브라우저에서만 강제되는 정책 — 비브라우저 클라이언트에는 무의미**(PM 승인사항과 일치, CORS≠인증) | 실 인증으로 근본 해결 | 낮음(현재 규모) | 중간 | Medium | 낮음~중간 | 아니오 | 아니오 | — | 개발팀 |
| T16 | 서비스 인증정보 노출(GitHub) | Info Disclosure | 실수로 Secret 커밋 | Secret | 세션 전체의 PII/Secret 정규식 검사 관행(매 Commit) | 사람의 실수는 완전히는 못 막음 | 자동 스캔 도구 도입 검토(향후) | 낮음(현재 관행 준수 중) | 매우 높음 | Critical | 낮음(관행 유지 시) | 예(원칙 유지) | 예(발생 시) | — | 개발팀 |
| T17 | Netlify 번들 Secret 노출 | Info Disclosure | 정적 파일에 Secret 포함 | Secret | 원칙적 금지(PM 승인사항) | 코드 리뷰 의존 | 코드 리뷰 체크리스트화 | 낮음 | 매우 높음 | Critical | 낮음(원칙 준수 시) | 예 | 예(발생 시) | — | 개발팀 |
| T18 | 로그에 인증정보 기록 | Info Disclosure | 감사로그/디버그 로그 | 로그 | `_server_log()` PII-safe 원칙(기존) | 신규 이벤트 추가 시 실수 가능 | §33 원문기록 금지 목록 준수 | 낮음 | 높음 | High | 낮음(원칙 준수 시) | 예 | 아니오 | F그룹 | 개발팀 |
| T19 | 감사로그 삭제·변조 | Repudiation | 파일 직접 편집 | 감사로그 | 파일 권한 통제(OS 수준, [확인 필요]) | 위변조 방지 메커니즘(체크섬 등) 없음 | Decision Required(DR8-1-20) | [확인 필요] | 중간 | Medium | [확인 필요] | 아니오 | 아니오 | F그룹 | PM |
| T20 | FastAPI 우회(Legacy 직접 Sheets 쓰기) | Elevation | Legacy Portal | Sheets | 없음 | T13/T14와 동일 | Phase B 전환(별도 Sprint) | 확인됨(상시) | 높음 | Critical | 높음 | 아니오(별도 Sprint) | 조건부 | — | PM |
| T21 | Legacy 경로 우회 | Elevation | 상동 | 상동 | 없음 | 상동 | 상동 | 확인됨 | 높음 | Critical | 높음 | 아니오 | 조건부 | — | PM |
| T22 | 구버전 API 오용(§12 발견) | Tampering | `/api/reservations/{rid}/cancel` 등 활성화 시 | 로컬 JSON(비-SSOT) | 미사용 상태(§12 확인) | 코드는 여전히 존재, 향후 실수로 활성화 가능성 | DR8-1(Commit8-0 D28)로 처리방향 결정 | 낮음(현재 미사용) | 중간(활성화 시) | Medium | 낮음(현재) | 아니오 | 아니오 | — | PM |
| T23 | JSON 예약경로와 Sheets SSOT 혼선 | Tampering | 개발자 실수로 구버전 API 활성화 또는 참조 | 데이터 정합성 | 문서화(ADR-013, 본 문서 §12) | 기술적 차단 없음 | 코드 주석/Deprecated 표시(Decision Required) | 낮음 | 중간 | Medium | 낮음~중간 | 아니오 | 아니오 | — | 개발팀 |
| T24 | Staging과 운영 계정 혼용 | Repudiation/Elevation | 환경 분리 미흡 시 | 계정 | 환경 분리 여부 [확인 필요] | 미확인 | 환경별 계정 정책(DR8-1-24) | [확인 필요] | 중간 | Medium | [확인 필요] | Staging 구성 시 필요 | 아니오 | — | PM/개발팀 |
| T25 | 운영 데이터의 Staging 사용 | Info Disclosure | Staging에 실 PII 유입 | 개인정보 | 원칙적 금지(Pilot 데이터 기준, Commit8-0 D17) | 기술적 차단 없음(운영정책 의존) | 비식별 데이터만 허용 원칙 강제 | 낮음(원칙상) | 매우 높음 | Critical | 낮음(원칙 준수 시) | 예 | 예(위반 시) | — | PM/개인정보책임자 |
| T26 | 세션 저장소 장애 | DoS | 파일시스템 장애 등 | 세션 | 미구현(설계만) | 구현 후 재평가 | §25 장애 처리 설계 | 낮음 | 중간 | Medium | 미확인(구현 후) | 아니오 | 아니오 | — | 개발팀 |
| T27 | FastAPI 장애 | DoS | 서버 프로세스 중단 | 전체 시스템 | 없음(단일 프로세스 추정) | 이중화 없음 | 별도 과제(Sprint8 범위 밖) | 낮음 | 높음 | High | 미확인 | 아니오 | 아니오 | — | PM |
| T28 | GAS Timeout | DoS | Google 서비스 지연 | 예약 처리 | Admin Portal만 8초 Timeout(Commit5-3.2) | Legacy/Reservation Portal 없음 | 별도 과제 | 낮음 | 중간 | Medium | 낮음(Admin Portal) | 아니오 | 아니오 | — | 개발팀 |
| T29 | 중복 요청(더블클릭 등) | Tampering | 클라이언트 재전송 | 예약 데이터 | [확인 필요](멱등성 처리 여부 미조사) | 미확인 | [확인 필요] | [확인 필요] | 중간 | Medium | [확인 필요] | 아니오 | 아니오 | — | 개발팀 |
| T30 | 관리자 상태변경 중 부분 실패 | Tampering | Slot 점유 성공 후 Sheets 쓰기 실패 등 | 데이터 정합성 | 기존 Commit3A 보상처리 로직(승인 경로 한정, Sprint7 문서 확인) | Legacy 경로는 없음 | 유지(승인 경로), Legacy는 Phase B 대상 | 낮음(승인경로)/중간(Legacy) | 높음 | High | 중간 | 아니오 | 아니오 | — | PM |
| T31 | 운영 인증 실패 시 Mock 우회 | Elevation | 장애 대응 중 임시조치 오남용 | 전체 시스템 | **금지 원칙만**(PM 승인사항, §38) | 기술적 강제는 구현 후 확인 가능 | §34 실패-안전 설계 | 낮음(원칙 준수 시) | 매우 높음 | Critical | 낮음(원칙 준수), 구현 후 재평가 | 예 | 예(위반 시) | A그룹 | PM/개발팀 |
| T32 | 승인 없는 Push·Deploy | Repudiation | 절차 위반 | 전체 시스템 | 세션 전체의 PM 개별승인 관행(Commit마다 재확인) | 사람의 실수 가능성 | Decision Required(DR8-1-28~31 승계) | 낮음(관행 준수 중) | 높음 | High | 낮음 | 아니오 | 예(위반 시) | — | PM |
| T33 | 미Push 로컬 Commit 유실 | DoS(가용성) | 단일 작업환경 장애 | Git 이력 | 없음(원격 42개 뒤처짐, §42) | 로컬 단일 지점 장애 시 이력 손실 가능 | 정기 Push 검토(Decision Required) | 낮음~중간 | 높음(발생 시 이력 손실) | High | 중간 | 아니오 | 아니오 | — | PM |

## 42. 위협별 대응통제

§41 표의 "목표통제" 열이 대응통제다. Critical 등급(T01/T02/T13/T14/T16/T17/T20/T21/T25/T31) 중 T13/T14/T20/T21(Legacy 직접호출 관련)은 **Sprint8 범위에서 완전히 해결되지 않으며 별도 Sprint(Legacy Stage3 Phase B)가 필요**함을 명확히 한다 — 이번 Commit에서 이를 해결된 것처럼 표현하지 않는다.

## 43. 잔여 위험

Commit8-2~8-3 구현이 완료되어도 다음은 잔존한다: T13/T14/T20/T21(Legacy 경로, 별도 Sprint 필요), T08(XSS 자체 방지는 프론트엔드 코드 감사 별도 필요), T19(감사로그 위변조 방지 미설계), T27(FastAPI 이중화 없음), T29(멱등성 미확인). 이들은 Sprint8 Closeout(Commit8-8)에서 재평가한다.

## 44. 기존 기능 영향도

| 구성요소 | 현재 경로 | 인증도입 영향 | 인가도입 영향 | 예상 변경파일 | 회귀위험 | 필수검증 | Rollback 고려사항 | 운영전 필수 |
|---|---|---|---|---|---|---|---|---|
| Admin Portal | `admin_portal_new.html`→FastAPI(Mock) | 로그인 화면 추가, API 호출에 세션 쿠키 필요 | 기존 `has_perm` 유지 | `admin_portal_new.html`, 신규 로그인 UI | 중간(전체 API 호출 방식 변경) | 로그인 후 기존 전 기능 정상 동작 | 인증 장애 시 접근 자체 불가(설계상 의도됨, §38) | 예 |
| Reservation Portal | `reservation_v3_new.html`→GAS 직접 | **없음(관리자 인증과 무관, 수검자용)** | 없음 | 없음 | 낮음 | 없음 | 해당없음 | 아니오 |
| Legacy Portal | `admin_reservations_v2_new.html`→GAS 직접 | 이번 Sprint 범위 밖(§13, T13) — 관리자 인증 도입만으로는 이 경로가 자동으로 보호되지 않음 | 없음(이번엔) | 없음(이번엔) | 없음(변경 안 하므로) | 없음 | 해당없음 | 아니오(단, 위험은 잔존, §43) |
| FastAPI Admin Routes | `routes_admin_portal.py` | `require_user` 교체 | 기존 `need_perm` 재사용 | `api_server.py`, `routes_admin_portal.py`, 신규 인증 모듈 | 높음(모든 관리자 API 영향) | 전체 회귀 스위트 재실행 | Rollback 시 이전 커밋으로 복귀(Mock 재활성화 아님, §38) | 예 |
| 구버전 Reservation API | `/api/reservations/*`(§12 발견, 미사용) | 적용 시 함께 영향받으나 미사용 경로라 우선순위 낮음 | 동일 | 미정(D28 결정 후) | 낮음(미사용) | 미사용 확인 유지 | 해당없음 | 아니오 |
| Reservation Engine | `reservation_engine.py` | 없음(엔진 자체는 인증과 무관, 호출부만 영향) | 없음 | 없음 | 낮음 | 기존 테스트 유지 | 해당없음 | 아니오 |
| GAS v3 | `sheets_api_v3_final.gs` | 서버간 인증 추가 시 영향(Commit8-3) | 없음 | 이번엔 없음 | 없음(이번 Commit) | 없음 | 해당없음 | 아니오(이번엔) |
| GAS v4 | `sheets_api_v4_deploy_new.gs` | 미사용(v3 유지 중) | 없음 | 없음 | 없음 | 없음 | 해당없음 | 아니오 |
| Google Sheets | SSOT | 없음(간접 영향만) | 없음 | 없음 | 낮음 | 없음 | 해당없음 | 아니오 |
| Slot 처리 | 승인경로 성숙 | 인증 도입으로 호출 경로만 바뀜, 로직 불변 | 불변 | 없음(로직 자체는) | 낮음 | 기존 Slot 테스트 재실행 | 해당없음 | 예(회귀검증) |
| 승인·거절 | Admin Portal→FastAPI | 세션 인증 요구로 전환 | 불변 | 위 Admin Portal과 동일 | 높음 | 전체 회귀 | 해당없음 | 예 |
| 예약확정(Legacy) | Legacy Portal, 클라이언트 차단(Commit6-1) | 없음(이번 Sprint 범위 밖) | 없음 | 없음 | 없음 | 없음 | 해당없음 | 아니오 |
| 예약변경 | 라벨만 변경(§13 Commit8-0) | 없음(이번 Sprint 범위 밖, D10 결정 대기) | 없음 | 없음 | 없음 | 없음 | 해당없음 | 아니오 |
| 예약취소 | Legacy 직접 | 없음(이번 Sprint 범위 밖) | 없음 | 없음 | 없음 | 없음 | 해당없음 | 아니오 |
| 검진완료 | Legacy 직접 | 없음(이번 Sprint 범위 밖) | 없음 | 없음 | 없음 | 없음 | 해당없음 | 아니오 |
| 감사로그 | `append_audit()` | 신규 이벤트 추가(§33) | 없음 | `reservation_audit.py`(AUDIT_EVENTS 목록 확장) | 낮음(추가만, 기존 항목 불변) | 신규 이벤트 기록 확인 | 해당없음 | 예 |
| Netlify | 정적 배포 | 로그인 UI 신규 배포 필요 | 없음 | Admin Portal HTML/JS | 낮음(정적 파일 추가) | 배포 후 접근 확인 | 이전 배포로 되돌리기(Rollback Guide §7) | 예 |
| 개발환경 | 로컬 | Mock 유지(§34) | 불변 | 없음 | 없음 | 기존 테스트 유지 | 해당없음 | 아니오 |
| Staging | [확인 필요, 존재 여부 미확인] | 구성 필요 시 신규 영향 | — | — | — | — | — | Commit8-7 대상 |
| 운영환경 | [확인 필요] | 전면 영향(Mock 차단) | 전면 영향 | 배포 설정 | 높음 | E2E 검증(Commit8-7) | Rollback Guide 절차 확장 필요(§56) | 예 |

**예약변경이 실제 일정·시간·프로그램 변경이 아니라 현재 라벨 변경 수준이라는 기존 확인사항을 그대로 유지하며, 이번 인증 설계에서 이 업무요구사항을 임의로 확정하지 않는다.**

## 45. 회귀검증 범위

§44의 "필수검증" 열 종합: 기존 회귀 스위트 전체(FastAPI 252개+, Admin Portal Parser 58/Legacy Guard 24/TD Cleanup 12, 백업 리허설 9/9 — Sprint7 Closeout §17 인용) + 신규 인증·세션·CSRF·감사로그 테스트(§46) 전부 PASS가 Commit8-2~8-3 완료 기준이다.

## 46. 인증·인가 테스트전략

테스트 코드는 작성하지 않으며, 아래는 실행 가능한 테스트 계획이다.

### A. 인증 테스트

| Test ID | 목적 | 선행조건 | 입력 | 절차 | 예상결과 | 실패판정 | 감사로그확인 | 자동화 | 8-2필수 | Staging필수 | Pilot전필수 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AUTH-01 | 정상 로그인 | 유효계정 존재 | 올바른 자격증명 | 로그인 요청 | 세션 발급, 200 | 세션 미발급 | 로그인성공 기록 | 예 | 예 | 예 | 예 |
| AUTH-02 | 잘못된 사용자 | - | 존재하지않는 ID | 로그인 요청 | 401, 계정존재 미노출 | 계정존재 노출 또는 200 | 로그인실패 기록 | 예 | 예 | 예 | 예 |
| AUTH-03 | 잘못된 비밀번호 | 유효계정 | 틀린 비밀번호 | 로그인 요청 | 401 | 200 | 로그인실패 기록 | 예 | 예 | 예 | 예 |
| AUTH-04 | 비활성 계정 | status≠ACTIVE 계정 | 올바른 자격증명 | 로그인 요청 | 401 | 200 | 로그인실패 기록 | 예 | 예 | 예 | 예 |
| AUTH-05 | 반복 로그인 실패 | - | 틀린 자격증명 N회 | 반복 요청 | 임계치 후 잠금(DR8-1-12) | 무제한 허용 | 반복실패 기록 | 예 | 권장(필수아님) | 예 | 예 |
| AUTH-06 | 로그인 성공 후 세션ID 재발급 | - | 로그인 전후 세션ID 비교 | 로그인 전후 세션ID 대조 | 상이해야 함 | 동일 | 세션생성 기록 | 예 | 예 | 예 | 예 |
| AUTH-07 | 인증 없는 API 요청 | - | 쿠키 없이 요청 | 보호 API 직접 호출 | 401 | 200 | 미인증요청 기록 | 예 | 예 | 예 | 예 |
| AUTH-08 | 위조된 X-User-Id | - | 임의 X-User-Id 헤더만 | 보호 API 호출 | 401(운영환경) | 200 | Mock사용시도 기록 | 예 | 예 | 예 | 예 |
| AUTH-09 | 운영환경 Mock 차단 | 운영환경 설정 | X-User-Id만 | 보호 API 호출 | 401 | 200 | Mock사용시도 기록 | 예 | 예 | 예 | 예 |
| AUTH-10 | 로그아웃 후 세션 재사용 | 로그인 상태 | 로그아웃 후 이전 쿠키로 요청 | 로그아웃→재요청 | 401 | 200 | 로그아웃 기록 | 예 | 예 | 예 | 예 |
| AUTH-11 | 세션 만료 후 요청 | 만료된 세션 | 만료 세션 쿠키 | 요청 | 401 | 200 | 세션만료 기록 | 예 | 예 | 예 | 예 |
| AUTH-12 | 강제폐기 세션 재사용 | 강제폐기된 세션 | 폐기된 쿠키 | 요청 | 401 | 200 | 세션강제폐기 기록 | 예 | 권장 | 예 | 예 |

### B. 세션 테스트

HttpOnly/Secure/SameSite 속성 확인(응답 헤더 검사), 유휴시간 만료, 절대 유효시간 만료, 권한변경 후 기존세션 무효화, 계정비활성화 후 기존세션 무효화, 다중 브라우저 세션(정책에 따름, DR8-1-11), Session Fixation(로그인 전후 ID 비교, AUTH-06과 연계), 세션 저장소 재시작 후 동작(파일 기반 채택 시 세션 유지 확인), 세션 저장소 장애 시뮬레이션(락 실패 등) — 각 항목 Test ID SESS-01~11 부여, Commit8-2 필수 대부분.

### C. CSRF 테스트

정상 Token 통과, Token 누락 거부, Token 불일치 거부, 다른 세션 Token 거부, Token 재사용/Replay 거부, GET으로 상태변경 시도 차단(라우팅 설계 확인), Cross-Origin 상태변경 시도 차단 — Test ID CSRF-01~07, Commit8-2 필수(상태변경 API부터).

### D. 인가 테스트

역할별 허용/거부 요청(기존 `roles.json` 역할별 매트릭스 기반), 권한없는 승인/예약변경/예약취소/검진완료 시도(단, 후3개는 Legacy 경로라 이번 Sprint 대상 아님 — Admin Portal 경로만), 존재하지 않는 권한 요청, 역할 변조 시도(세션 저장값과 다른 역할 주장), 클라이언트 권한정보 변조 시도, 기본거부 확인(정의되지 않은 조합은 거부) — Test ID AUTHZ-01~10, Commit8-2 필수(기존 `has_perm` 로직은 변경 없음이므로 회귀 성격).

### E. FastAPI–GAS 테스트

정상 서명/Token 통과, 자격증명 누락 거부, 잘못된 자격증명 거부, 만료된 자격증명 거부, Timestamp 초과 거부, Nonce 재사용 거부, 본문 변조 감지, 권한범위 초과 거부, FastAPI 우회 GAS 직접호출 시나리오 확인(현재는 차단 불가 — T14 잔존 위험 확인용, Pass/Fail이 아니라 현황 기록용 테스트), GAS Timeout 처리, 중복요청 처리, 감사로그 Correlation 확인 — Test ID GASAUTH-01~12, **Commit8-3 대상**(이번 8-2는 관리자 인증만, 서버간 인증은 8-3).

### F. 감사로그 테스트

필수 이벤트 기록 확인(§33 목록 전체), 실패 이벤트 기록, 권한거부 기록, 민감정보 미기록 확인(로그 파일에 비밀번호/세션ID원문/CSRF Token 부재 확인), Request ID 연계 확인, 로그 접근권한 확인([확인 필요] 항목이라 실제 구현 후 재설계 필요), 로그 저장 실패 시 처리(장애 시 요청 자체를 거부할지 로그 없이 통과시킬지 — Decision Required 성격, 원칙상 "로그 실패도 감사 대상" 권장) — Test ID AUDIT-01~07.

### G. 회귀 테스트

Admin Portal 기존 조회, 승인·거절, Legacy Portal(변경 없음 확인), Reservation Portal(변경 없음 확인), Google Sheets SSOT 연동, Slot 처리, GAS v3 운영경로, GAS v4 후보경로(미사용 상태 유지 확인), 구버전 JSON API와 현행 Sheets 경로 분리 유지 확인(§12/§44 T22 관련), 기존 테스트 스위트 전체 재실행 — Test ID REGR-01~10, **전부 Commit8-2/8-3 필수, Staging 필수, Pilot전 필수**.

## 47. 보안 테스트

§46 C(CSRF)/E(FastAPI-GAS)/일부 A(Brute Force 관련 AUTH-05)가 보안 테스트에 해당한다. 추가로 Commit8-7(Staging E2E) 단계에서 다음을 별도 확인: 세션 쿠키 속성이 실제 배포 환경(HTTPS 여부 확인 후)에서 의도대로 설정되는지, Secret이 실제로 클라이언트 번들에 포함되지 않는지(빌드 산출물 grep 검사).

## 48. 운영 준비도 Gate

Sprint7 Closeout(§22)의 보안 준비도 NOT READY 판정이 이 문서(Commit8-1)만으로는 해소되지 않는다 — 설계일 뿐이다. Commit8-2 구현 및 §45/46 검증 통과 후 재평가 대상이다.

## 49. Commit8-2 구현 범위 제안

§34(Mock 격리, 환경분기+운영차단), §17~19(로그인/로그아웃/세션 흐름), §25(파일기반 세션 저장소), §26~28(Cookie/CSRF/Fixation 방어), §33(감사로그 신규 이벤트) — 관리자 브라우저 인증에 한정. GAS 서버간 인증(§35)은 **Commit8-3으로 분리**.

## 50. Commit8-2 제외 범위

외부 IdP 연동(§39), FastAPI-GAS 서버간 인증(§35, Commit8-3), Legacy/Reservation Portal 변경(§44, 별도 Sprint), 예약변경 기능 자체(D10 미결정), 비정상 세션 자동탐지, 감사로그 위변조 방지 메커니즘.

## 51. Commit8-2 진입조건

DR8-1-01(계정저장소), DR8-1-07(세션저장소), DR8-1-08/09(유휴/절대시간), DR8-1-14(CSRF방식), DR8-1-21(Mock격리방식) 최소 결정 + 본 문서 PM 승인.

## 52. 구현 전 Decision Required

§53 참조(통합표).

## 53. Decision Required

(요구사항 명명 규칙 DR8-1-NN 준수)

| ID | 결정사항 | 현재상태 | 이유 | 미결정시영향 | 권장안 | 대안 | 보안영향 | 운영영향 | 결정주체 | 결정시점 | 임시통제 | 관련코드 | 관련문서 | 8-2차단 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DR8-1-01 | 사용자 계정 저장소 | `users.json`(비밀번호 필드 없음) | 실 인증에 비밀번호 저장 필요 | 구현 불가 | 기존 `users.json` 확장(해시 필드 추가) | 신규 별도 저장소 | 중간 | 낮음(기존 구조 재사용) | PM/개발팀 | 8-2 착수전 | 없음 | `data/users.json` | 본 문서 §24 | **예** |
| DR8-1-02 | 비밀번호 검증 주체 | 없음 | 검증 로직 위치 필요 | 설계 불가 | FastAPI 자체 검증 | 외부 IdP(대안B) | 중간 | 낮음 | PM | 8-2 착수전 | 없음 | 신규 | §20 | 예 |
| DR8-1-03 | 비밀번호 Hash 방식 | 없음 | 저장 방식 필요 | 구현 불가 | 표준 강력 해시(구체 알고리즘은 구현팀 기술결정, 예: bcrypt/argon2 계열 — 라이브러리 신규 도입 필요, 현재 코드에 0건 확인) | 없음(필수) | 높음 | 낮음 | 개발팀 | 8-2 착수전 | 없음 | 신규 | §24 | 예 |
| DR8-1-04 | 계정 생성·승인 주체 | 없음(수동 추정) | 절차 필요 | 운영 혼선 | 전산담당 수동 생성 | 자동 신청·승인 플로우(향후) | 낮음 | 중간 | 병원/PM | 운영착수전 | 수동 관리 유지 | — | §24 | 아니오 |
| DR8-1-05 | 계정 비활성화 주체 | 없음 | 퇴직 등 처리 필요 | T12 위험 지속 | 전산담당 | 자동화(향후) | 높음 | 중간 | 병원/PM | 운영착수전 | 수동 관리 | — | §24, T12 | 아니오 |
| DR8-1-06 | 역할·권한 승인 주체 | 없음(수동) | 권한 부여 절차 필요 | 최소권한 훼손 위험 | PM | 전산담당 | 중간 | 낮음 | PM | 운영착수전 | 수동 관리 | `data/roles.json` | §24 | 아니오 |
| DR8-1-07 | 세션 저장소 | 없음 | §25 대안 필요 | 구현 불가 | 파일 기반(권장) | Redis(과설계) | 낮음(권장안 기준) | 낮음 | PM/개발팀 | 8-2 착수전 | 없음 | 신규 | §25 | **예** |
| DR8-1-08 | 유휴시간 | 없음 | §25 대안 필요 | 구현 불가 | 30분(대안2) | 15분/60분 | 중간 | 중간 | PM/병원 | 8-2 착수전 | 없음 | 신규 | §25 | **예** |
| DR8-1-09 | 절대 유효시간 | 없음 | 상동 | 상동 | 8시간(대안2) | 4시간/24시간 | 중간 | 중간 | PM/병원 | 8-2 착수전 | 없음 | 신규 | §25 | **예** |
| DR8-1-10 | 재인증 조건 | 없음 | 상동 | 상동 | 절대만료+역할변경 시 | 절대만료만 | 중간 | 낮음 | PM | 8-2 착수전 | 없음 | 신규 | §25 | 아니오 |
| DR8-1-11 | 동시 로그인 정책 | 없음 | 다중세션 허용여부 | UX/보안 상충 | 다중 허용(업무 편의 우선, 소규모 인원) | 단일 세션 강제 | 낮음~중간 | 중간 | PM | 8-2 착수전 | 없음 | 신규 | §25 | 아니오 |
| DR8-1-12 | 로그인 실패 제한 | 없음 | Brute Force 방어 필요 | T10 위험 지속 | 5회/15분(예시, 최종값은 결정필요) | 다른 임계치 | 중간 | 낮음 | 개발팀 | 8-2 착수전 | 없음 | 신규 | §32 | 권장 |
| DR8-1-13 | 계정 잠금·해제정책 | 없음 | 상동 | 상동 | 자동 잠금+수동 해제(전산담당) | 자동 해제(시간경과) | 중간 | 중간 | PM | 8-2 착수전 | 없음 | 신규 | §32 | 권장 |
| DR8-1-14 | CSRF 구현방식 | 없음 | §27 필요 | T07 위험 지속 | 세션연계 Token+SameSite=Lax 병행 | Double Submit Cookie | 중간 | 낮음 | 개발팀 | 8-2 착수전 | 없음 | 신규 | §27 | **예** |
| DR8-1-15 | FastAPI–GAS 서비스 인증방식 | 없음 | §35 필요 | T14 위험 지속 | HMAC(대안1) | Token/JWT | 높음 | 중간 | PM/개발팀 | 8-3 착수전 | URL비공개 유지 | `sheets_write_service.py` | §35 | 아니오(8-3 대상) |
| DR8-1-16 | 서비스 인증정보 저장위치 | 없음 | 상동 | 상동 | 서버환경변수+GAS Script Properties | 없음 | 높음 | 낮음 | 개발팀 | 8-3 착수전 | 없음 | §35/36 | §35 | 아니오 |
| DR8-1-17 | Key Rotation 주기 | 없음 | 상동 | 상동 | [확인 필요, 병원 정책에 따름] | 없음 | 중간 | 중간 | PM | 8-3 착수전 | 없음 | §36 | §35 | 아니오 |
| DR8-1-18 | 감사로그 저장소 | 기존 `audit_logs.json` | 신규 이벤트도 여기에 저장할지 | 설계 확정 필요 | 기존 파일 재사용(권장, 신규 인프라 회피) | 별도 저장소 | 낮음 | 낮음 | PM | 8-2 착수전 | 없음 | `reservation_audit.py` | §33 | 권장 |
| DR8-1-19 | 감사로그 보존기간 | backup_policy.md 로컬JSON 1년(Sprint7) | 인증 이벤트도 동일 적용할지 | 정책 불일치 위험 | 동일 1년 적용 | 별도 기간 | 낮음 | 낮음 | PM | 운영착수전 | 현행(무기한) | `backup_policy.md` | §33 | 아니오 |
| DR8-1-20 | 감사로그 접근권한 | 없음(Sprint7 D13 승계) | 오남용 방지 | 위험 지속 | 개발팀+PM 한정 | 전체 운영팀 | 중간 | 낮음 | PM | 운영착수전 | 없음 | — | §33 | 아니오 |
| DR8-1-21 | X-User-Id Mock 제거 시점 | Mock 유지 중 | §34 절차 필요 | T01/T31 위험 지속 | Commit8-2에서 환경분기 도입, 운영환경만 우선 차단, 개발/테스트는 유지 | 즉시 전체 제거(테스트 인프라 영향 큼) | 높음 | 중간(테스트 전환 부담) | PM/개발팀 | 8-2 착수전 | 없음 | `api_server.py` | §34 | **예** |
| DR8-1-22 | 내부망·VPN 적용범위 | 없음 | 대안C 적용여부 | 보완통제 부재 | Pilot 기간 한정 적용 검토 | 전체 상시 적용 | 낮음(보완통제) | 높음(인프라 의존) | 병원 | Pilot 착수전 | 없음 | — | §40 | 아니오 |
| DR8-1-23 | 외부 IdP 검토시점 | 미확정 | 대안B 재검토 시점 필요 | 장기 로드맵 불명 | 별도 Sprint(중장기) | Sprint8 내 검토 | 낮음 | 낮음 | PM | 비긴급 | 없음 | §39 | §39 | 아니오 |
| DR8-1-24 | Staging 계정정책 | 없음, Staging 자체 존재 [확인 필요] | 환경 분리 필요 | T24 위험 | Staging 전용 계정 별도 발급 | 운영계정 재사용(비권장) | 중간 | 중간 | PM/개발팀 | 8-7 착수전 | 없음 | — | §44, T24 | 아니오 |
| DR8-1-25 | 운영계정 전환절차 | 없음 | Mock→실계정 전환 방법 필요 | 전환 혼선 | 병원 전산담당이 초기 계정 일괄 생성 | 개별 신청 | 낮음 | 중간 | 병원/PM | 8-2 완료후 | 없음 | — | §24 | 아니오 |
| DR8-1-26 | 인증 장애 시 관리자 업무절차 | 없음(원칙만, §38) | 수기 대체 절차 필요 | 장애 시 업무 완전 중단 | 장애 시 임시 수기 처리 후 사후 입력(원칙만 제안) | 없음 | 낮음 | 높음 | 병원/PM | Pilot 착수전 | 없음 | `CSHSP_Failure_Response_Manual.md`(향후 반영) | §38 | 아니오 |
| DR8-1-27 | Rollback 결정권자 | 미확정(Sprint7 D2/Commit8-0 D21 승계) | 인증 관련 Rollback 판단 주체 | 대응 지연 | PM | — | 낮음 | 중간 | PM | Pilot 착수전 | PM 임시 겸임 | — | Rollback Guide | 아니오 |
| DR8-1-28 | Push 승인권자 | 미확정(Commit8-0 D25 승계) | 매Push 승인 필요 | 절차 혼선 | PM | — | 낮음 | 낮음 | PM | 매Push시점 | PM 개별승인 | — | §55 | 아니오 |
| DR8-1-29 | Netlify Deploy 승인권자 | 미확정(Commit8-0 D26 승계) | 상동 | 상동 | PM | — | 낮음 | 낮음 | PM | 매Deploy시점 | PM 개별승인 | — | §55 | 아니오 |
| DR8-1-30 | FastAPI Deploy 승인권자 | 미확정(신규) | 서버 배포 절차 자체가 이 저장소에 문서화 안 됨 [확인 필요] | 배포 절차 불명 | PM | — | 중간 | 중간 | PM | 8-2 완료후 | PM 개별승인 | `src/deploy/production_checklist.md`(향후 보강 검토) | §55 | 아니오 |
| DR8-1-31 | GAS Deploy 승인권자 | 미확정(Commit8-0 D27 승계) | 과거 미반영 배포 사고 이력 | 사고 재발 위험 | PM | — | 중간 | 중간 | PM | 8-3 착수전 | PM 개별승인+"새버전" 배포 원칙 | Rollback Guide §8 | 아니오 |
| DR8-1-32 | 미Push 로컬 Commit 백업·Push 시점 | 42개 앞섬(§54) | 유실 위험(T33) | 이력 손실 가능 | Sprint8 주요 마일스톤(예: Commit8-8 Closeout) 시점에 PM 승인 하 일괄 Push 검토 | 매Commit마다 Push | 낮음 | 중간(대량 Push 시 검토부담) | PM | Sprint8 완료 시점 검토 | 로컬 보관 유지(현재도 문제 없음, 단일 세션 연속 작업 중) | — | §54 | 아니오 |

**D1/D4 기본방향(대안A+C, 서버관리형 세션)은 재확정하지 않고 그대로 유지하며, 세부값만 위 표로 관리한다.**

## 54. Sprint8 위험등록부 (본 Commit 관련분만 갱신 확인)

Commit8-0 SR1~SR20(§32, Sprint8 Security Plan)을 그대로 승계하며 이번 Commit에서 신규 위험을 추가하지 않는다(설계 문서 작성만 수행했으므로). T01~T33(§41)은 SR1~SR20보다 세분화된 Threat Model이며 상호 매핑 관계다(예: T01/T02→SR1, T13/T14→SR3, T31→SR14/SR18 관련).

## 55. Git 백업·Push 위험

**확인됨**: 로컬 브랜치가 원격보다 **42개** 커밋 앞선 상태(`git status -sb` 재확인, PM이 언급한 "약 42개 이상"과 일치). 위험으로 기록: 미Push Commit 유실 위험(단일 로컬 작업환경 장애 시 전체 손실 가능, T33), 원격 백업 부재, Push 지연에 따른 이력 공유 부족, 대량 Push 시 검토 난이도 증가, 운영 배포와 Git Push 혼동 위험.

**Git Push ≠ 운영 배포 확인**: 이 저장소에 Netlify/GAS/FastAPI 자동배포 트리거(예: GitHub Actions, Netlify 자동빌드 후크) 설정 파일이 존재하는지 확인한 결과, `netlify.toml`은 빌드 설정(`publish = "."`)과 보안 헤더만 포함하고 있으며 Git Push에 반응하는 자동배포 파이프라인 정의는 이 저장소 파일만으로는 확인되지 않았다 — **다만 Netlify 서비스 자체의 대시보드 설정(저장소 연결 시 자동배포 여부)은 이 저장소 코드로 확인할 수 없으므로, 자동배포가 연결되어 있을 가능성을 임의로 배제하지 않는다.** [확인 필요]로 표시하며, Push 실행 전 매번 이 가능성을 재확인하는 것을 권장한다.

## 56. Push·Deploy 통제

DR8-1-28~31(§53)로 통합 관리. Git Push, Netlify Deploy, GAS Deploy, FastAPI Deploy는 각각 독립적으로 PM 개별 승인을 받으며, 하나의 승인이 나머지를 포함하지 않는다(Commit8-0 §35 원칙 재확인).

## 57. Rollback 고려사항

인증 도입 후 Rollback 시나리오: (1) Commit8-2 코드를 이전 커밋으로 되돌리는 경우 — 이 경우에도 §34 원칙에 따라 **Mock 인증으로 재활성화하지 않는다**(PM 승인사항), 대신 서비스 일시 중단을 택한다. (2) 세션 저장소 장애 — §25/§37 참조, 신규 로그인 실패로 자연스럽게 서비스 제한. `docs/CSHSP_Rollback_Guide.md`에 인증 관련 장애 시나리오를 추가하는 것은 이번 Commit의 대상 외(§56, 향후 별도 Commit 제안)로 남긴다.

## 58. 완료 기준

이 문서(Commit8-1)의 완료 기준은 PM이 §20(대안 A/C 상세설계)과 §35(FastAPI-GAS 대안)의 세부 방향, §53 Decision Required 중 Commit8-2 차단 항목(DR8-1-01/07/08/09/14/21)을 검토·결정 방향을 확정하는 것이다. 이 문서 자체가 Commit8-2를 자동 승인하지 않는다(PM 승인사항 명시 준수).

## 59. 미확정 사항

배포 환경의 HTTPS 여부(§37), 검진센터 관리자 공용 PC 사용 여부(§25), 병원 측 IdP 존재 여부(§39), VPN/내부망 실제 구성 가능 여부(§40), Staging 환경 존재 여부(§44), XSS 취약점 존재 여부(프론트엔드 코드 감사 필요, T08), 멱등성 처리 여부(T29), 감사로그 접근권한 통제 방식(T19), FastAPI 이중화 여부(T27), Netlify 자동배포 트리거 존재 여부(§55). 전부 [확인 필요] 또는 Decision Required로 표시했으며 임의로 확정하지 않았다.

## 60. PM 승인 요청사항

1. §25 세션 저장소 권장안(파일 기반, 기존 `session_store.py`/`file_lock.py` 패턴 재사용) 승인 여부
2. §25 유휴시간/절대 유효시간 권장안(30분/8시간, 대안2) 승인 또는 병원 운영 특성 반영한 조정
3. §35 FastAPI-GAS 서비스 인증 권장안(HMAC, GAS Script Properties) — Commit8-3에서 다룰 예정이나 기본 방향 사전 확인 필요 여부
4. §53 DR8-1-01/07/08/09/14/21(Commit8-2 차단 항목) 결정 일정
5. §55 Git 미Push 42개 커밋에 대한 Push 시점 계획(DR8-1-32) — 이번 Commit에서는 Push하지 않음을 전제로, 향후 계획만 확인 요청
6. Commit8-2(관리자 인증·인가 최소 구현) 착수 승인 여부

---

## 완료 조건 준수 확인

이 문서 작성 중 애플리케이션 코드·인증 코드·인가 코드·테스트 코드·설정 파일·환경변수·API 경로·API 동작·Business Rule·Google Sheets 구조·Apps Script·Netlify 설정·FastAPI 배포설정·운영 계정·사용자 계정·역할 데이터·권한 데이터·운영 데이터·Legacy 기능·기존 Portal 기능·백업 데이터를 변경하지 않았다(전부 Read/Grep으로만 조사). 보호 대상 파일(`ADR-015_Slot_Status_Policy_Draft.md`, `tests/sprint3_rbac_test_result.csv`)은 읽지 않았다. 실제 Secret, GAS URL, Spreadsheet ID, 개인정보를 기록하지 않았다. Cookie/Session/Token의 실제 값은 존재하지 않으며(설계 문서이므로) 기록될 수 없다. 미확정 정책을 임의로 승인하지 않았다. git reset, git checkout을 이용한 사용자 변경사항 복원, git clean, force push, rebase, amend를 사용하지 않았다. Commit8-2 구현 착수, Push, Netlify/GAS/FastAPI Deploy, 외부 시스템 변경, Pilot 시작, 실제 개인정보를 사용한 테스트를 하지 않았다.
