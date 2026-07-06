# CSHSP API Layer — Sprint D 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** D — REST API Layer 구현 (FastAPI)
> **작성일:** 2026-07-03
> **위치:** `99_임시보관_정리대기/CMC_Platform_new/src/api/`

---

## 1. Sprint D 목적

Sprint A(Core Data Layer) · B(Reservation Engine) · C(Admin Console)를 REST API로 연결한다.

- Reservation Engine을 HTTP로 노출 — 화면/AI Agent가 엔진을 직접 조작하지 않고 API 경유
- Header 기반 Mock 인증·권한 (Sprint E에서 실제 인증으로 교체할 의존성 주입 구조)
- JSON 쓰기 동시성 보호 (스레드 + 프로세스 파일 잠금)
- Admin Console `?mode=live` 전환 — 화면 코드 재사용, 데이터 소스만 교체

## 2. 실행 방법

```bash
pip install fastapi "uvicorn[standard]" httpx     # 최초 1회 (fastapi 0.139 확인됨)

cd CMC_Platform_new
python -m uvicorn src.api.api_server:app --port 8600
# 데이터 폴더 변경: 환경변수 CSHSP_DATA_DIR (기본: CMC_Platform_new/data)

# Admin Console live 모드:
#   정적 서버(포트 4000)로 /admin/?mode=live 접속  (api 주소 변경: ?mode=live&api=http://host:port)
# API 문서(자동 생성): http://localhost:8600/docs
```

## 3. 구조

```
src/api/
├── api_server.py   ★ FastAPI 앱 (create_app(data_dir) 팩토리 + 전 Endpoint)
└── file_lock.py    DataLock — threading.RLock + msvcrt/fcntl 파일 잠금

호출 경로:  admin(?mode=live) / AI Agent
              → REST API (인증·권한·마스킹·HTTP 매핑)
              → DataLock (쓰기 직렬화)
              → reservation_engine (Sprint B, 무수정 재사용*)
              → core_data_loader / json_store → data/*.json
* 엔진에는 release_hold() 함수 1개만 추가 (기존 코드 변경 없음)
```

예외 → HTTP 매핑: `EnginePermissionError→403`, `NotFoundError→404`, `InvalidTransitionError→409`,
`EngineError→400`, 검증 실패(중복/FULL/BLOCKED)→`422 + {verdict, reasons, alternatives}`.

## 4. 주요 Endpoint

| 분류 | Method / Path | 설명 | 권한 |
|------|--------------|------|------|
| 기본 | GET /api/health | 상태 + Entity 건수 | 없음 |
| 기본 | GET /api/entities/bundle | admin live 모드용 일괄 조회 (역할 기반 마스킹) | 인증 |
| 예약 | GET /api/reservations?status=&query= | 목록 (마스킹 필드 포함) | reservation:view |
| 예약 | GET /api/reservations/pending | 승인 대기함 | reservation:view |
| 예약 | GET /api/reservations/{id} | 상세 + auditTrail + allowedNext | reservation:view |
| 예약 | POST /api/reservations | 신청 (엔진 → PENDING_APPROVAL + Slot HOLD) | 엔진 검사 |
| 예약 | POST /api/reservations/{id}/approve | 승인 → CONFIRMED | reservation:approve |
| 예약 | POST /api/reservations/{id}/reject·cancel·change | 거절/취소/변경 | 엔진 검사 |
| 예약 | POST /api/reservations/{id}/no-show·complete | 노쇼/완료 | reservation:change |
| Slot | GET /api/slots?status=&from=&to= | 목록 (비개인정보) | 인증 |
| Slot | GET /api/slots/recommend | 대체 Slot ≤5 | 인증 |
| Slot | POST /api/slots/generate | 기간 Slot 생성 (주말·휴진 차단) | slot:manage |
| Slot | POST /api/slots/{id}/release-hold | HOLD 해제 | slot:manage |
| Admin | GET /api/admin/schedules?tab= | 일정 (holiday 등) | 인증 |
| Admin | GET /api/admin/users · roles | 사용자(민감필드 제외)/역할 | 인증 |
| Admin | GET /api/admin/validate | Sprint A Validator 실행 | 인증 |
| Dashboard | GET /api/dashboard/kpi | KPI 8종 (가동률·온라인비율 포함) | 인증 |
| 감사 | GET /api/audit-logs?action=&query=&date= | 감사로그 필터 | audit:view 또는 reservation:view |

## 5. 인증·권한 구조 (Mock)

- 모든 보호 Endpoint는 **`X-User-Id` 헤더 필수** → users.json의 ACTIVE 사용자만 통과 (아니면 401)
- 권한은 roles.json 기준 (엔진과 동일 규칙, `*` 와일드카드 지원)
- **AI 예약비서(ROLE-AI-AGENT)**: 신청(POST /reservations)·Slot 조회·추천만 가능. 승인/거절/HOLD해제/Slot생성/예약조회 전부 403 — "AI는 확정 불가" 원칙이 API 레벨에서 강제됨
- **개인정보 서버측 마스킹**: FULL 표시 역할(ADMIN/STAFF/DIRECTOR) 외에는 생년월일 `YYYY****`, 전화 `010-****-1234`, email 제외 (Sprint C의 클라이언트 Privacy를 서버로 이관)
- 교체 지점: `require_user` 의존성만 JWT/세션 구현으로 바꾸면 전 Endpoint에 적용

## 6. 동시성 보호

`file_lock.DataLock(data_dir)` — 쓰기 계열 엔드포인트는 전부 잠금 내에서 엔진 호출:
- 프로세스 내: `threading.RLock` (uvicorn 다중 스레드 직렬화)
- 프로세스 간: `data_dir/.cshsp.lock` 배타 잠금 (Windows `msvcrt.locking` / POSIX `fcntl.flock`)
- 검증: 스레드 8개 동시 예약 신청 → 예약번호 채번 충돌 0건, JSON 파싱 무결성 유지

## 7. admin_api.js live 모드

- `?mode=live` 접속 시: 데이터는 `GET /api/entities/bundle`, 조작(승인/거절/취소/HOLD해제)은 REST POST + 응답 후 번들 재수신으로 화면 동기화. 사이드바에 "Live 모드" 배너 표시
- 화면 코드(admin.js)는 `handleAction`의 async 승격 + `setActor`(X-User-Id 동기화) 2곳만 보완 — 나머지 무수정
- mock 모드는 기존 그대로 동작 (기본값)

## 8. 테스트 결과

**API 자동 테스트 36/36 PASS** (`tests/run_sprint_d_tests.py`, 결과 `tests/sprint_d_test_result.csv`)
— TestClient + 샌드박스 사본, 원본 data/ 불변 검증 포함.

- 인증(401/403) · 목록/상세/필터/검색 · 역할별 마스킹 · 신청→승인→취소 파이프라인 · 409(잘못된 전이) · 422(중복/FULL+대체슬롯) · Slot 생성/추천/HOLD해제 · KPI · 감사로그 필터 · **동시 신청 8건 채번 무충돌** · Validator 무결성 0오류

**브라우저 live 모드 실증** (uvicorn :8600 + 정적 :4000, 샌드박스 데이터):
- `/admin/?mode=live` 로드 → Live 배너 + KPI 카드 + 승인 대기 표시 ✅
- 승인 버튼 클릭 → REST → 엔진 → **서버 JSON 파일에 CONFIRMED + RESERVATION_APPROVED 영속 기록** ✅ (원본 data/는 PENDING_APPROVAL 그대로 = 불변 확인)

기존 회귀: Sprint B 38/38 PASS 유지.

## 9. 발견된 문제

1. HTTP 헤더는 ASCII 전용 — X-User-Id에 한글 불가 (Mock 인증 한계, 실제 인증 토큰으로 해소)
2. AI 역할은 reservation:view가 없어 자기 신청 건도 조회 불가 — Sprint E에서 "본인 신청 건 한정 조회" 권한 설계 필요
3. starlette TestClient의 httpx 사용 deprecation 경고 (동작 무관, 향후 httpx2 전환)
4. bundle 방식은 데이터 증가 시 비효율 — 운영 단계에서 화면별 개별 API 호출로 전환 필요

## 10. 보완 필요사항

- 실제 인증(JWT/세션) + 감사로그에 인증 이벤트(LOGIN 등) 추가
- JSON → SQLite/DB 이관 (파일 잠금은 과도기 조치)
- 예약 변경/노쇼/완료 화면 버튼의 live 연동 (API는 준비됨, admin.js 액션 미배선)
- Rate limit, 요청 로깅, OpenAPI 스키마 응답 모델 정식화

## 11. Sprint E 제안 (AI Agent 연계)

| 우선순위 | 작업 |
|:---:|------|
| 1 | AI 예약비서 Function Calling 스펙 — POST /api/reservations, GET /api/slots/recommend를 Claude tool로 정의 |
| 2 | 예약 대화 흐름 (프로그램 안내 → 슬롯 추천 → 신청 → "직원 확인 후 확정" 안내) |
| 3 | RAG Knowledge Base 연동 (health-checkup-knowledge의 프로그램/선택검사 데이터) |
| 4 | 알림 발송 워커 (notifications.json PENDING → 카카오/SMS) |
| 5 | 실인증 + 본인확인 정책 (전화번호 검증 등) |

---

*CSHSP Sprint D | 2026-07-03 | 천안의료원 건강검진센터*
