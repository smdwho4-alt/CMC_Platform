# Sprint 4 Commit 2 Implementation Plan v1.0 — Reservation Approval Foundation

> **성격**: PM 승인 대기 중인 구현 계획. 이 문서 자체는 설계이며, **PM 승인 전까지 코드를 작성하지 않는다**(Sprint 1~3 전 Commit에서 확립된 관행 유지).
> **작성일**: 2026-07-28
> **선행 근거**: `Reservation_Core_Architecture_v1.0.md` §3(승인 흐름), `Reservation_Data_Mapping_and_Migration_Plan_v1.0.md` §5/§6(상태값·승인 갭), `ADR-013`(예약 SSOT=Sheets), `Sprint4_Architecture_Gate_Report_v1.0.md` §9-1(승인 게이트 PM 결정 필요 — 본 문서로 구체화)

---

## 0. 이번 Commit이 결정하는 것

PM 지시(Commit 2 = "Reservation Approval Foundation")를 다음 5개 구성요소로 분해해 하나의 Commit으로 통합 구현한다: ① 예약 상태 모델(State Machine, Sheets 도메인 한정) ② 승인/거절 API(FastAPI) ③ Google Sheets 상태 매핑 ④ Audit Hook ⑤ Portal 승인 UI. **Slot/정원 제어는 Commit 3으로 명시 제외**한다. 기존 기능(엔드포인트/화면/GAS action/Sheets 데이터) 삭제·수정 없이 **추가만** 한다.

## 1. 예약 상태 모델 (State Machine, Sheets 도메인)

기존 로컬 JSON의 9-상태 머신(`state_machine.py`)을 그대로 재사용하지 않는다 — Sheets `예약상태` 컬럼은 값 집합이 다르고(§ 매핑 문서 §5), Sheets에는 애초에 `PENDING_APPROVAL`/`WAITING`/`NO_SHOW` 개념이 없다. 대신 **Commit 2 범위에 필요한 최소 상태 전이만** 신규로 정의한다.

```python
# 신규: src/api/reservation_approval_states.py (신규 파일, 기존 파일 무수정)
SHEETS_APPROVAL_TRANSITIONS = {
    "예약접수": {"예약확정", "거절"},   # 승인 → CONFIRMED, 거절 → REJECTED(신규 값)
}
```

- **"예약접수"가 곧 승인 대기 상태다** — 별도의 "승인대기" 상태값을 신규로 만들지 않는다. `core_data_loader.LEGACY_STATUS_MAP`이 이미 `예약접수 → REQUESTED`로 매핑해 두었고, 수검자 웹 폼이 예약 생성 시 기본값으로 `예약접수`를 쓰므로(GAS `_actionCreate`) 이 상태 자체가 "직원 검토 전" 상태를 정확히 표현한다. `Reservation_Core_Architecture_v1.0.md` §3에서 예시로 그렸던 "승인대기(신규 상태값 후보)"는 **불필요한 것으로 판단해 이번 계획에서 제외**한다(상태값 1개 추가로 범위를 최소화).
- **"거절"은 Sheets에 없던 신규 값**이다(§ 매핑 문서 §5에서 확인한 갭). GAS `_actionUpdateStatus`는 `status` 파라미터에 대해 어떤 Enum 검증도 하지 않고 `.setValue(status)`로 그대로 저장하므로(코드 확인, `VALID_PAYMENT_STATUS` 등 3개 Enum 상수는 애초에 `예약상태`가 아닌 다른 컬럼용), **GAS 코드를 전혀 수정하지 않고도 "거절"이라는 새 문자열 값을 안전하게 쓸 수 있다.** 이는 Sheets 구조 변경(컬럼 추가 등)이 아니라 기존에 자유 텍스트나 다름없던 필드에 새 값 하나를 쓰기 시작하는 것뿐이다.
- 이 상태 모델은 **`예약접수` 상태의 예약에만 적용된다.** `예약확정/검진중/검진완료/일정변경/예약취소`는 기존 `admin_reservations_v2_new.html`이 이미 다루고 있으므로 이번 Commit에서 건드리지 않는다(중복 구현 금지 원칙).

## 2. 승인/거절 API (FastAPI)

`routes_admin_portal.py`(Sprint 1~3에서 이미 `/api/admin/*` 네임스페이스를 다루고 있는 파일)에 엔드포인트 2개를 **추가**한다. 기존 `_build_require_permission()`(Sprint 3 RBAC)을 그대로 재사용한다 — 새 권한검사 로직을 만들지 않는다.

| 엔드포인트 | 권한 | 동작 |
|---|---|---|
| `POST /api/admin/reservations/{reservationNo}/approve` | `reservation:approve`(기존 문자열 재사용, ROLE-STAFF/ROLE-ADMIN만 보유 — `roles.json` 재확인 완료) | Sheets에서 현재 상태 조회 → `예약접수`가 아니면 409 → GAS `updateStatus(status='예약확정')` 호출 → Audit Hook 기록 → 결과 반환 |
| `POST /api/admin/reservations/{reservationNo}/reject` | `reservation:approve`(로컬 JSON `reject_reservation()`도 동일 권한을 쓰는 기존 관행 재사용 — 신규 권한 문자열 만들지 않음) | 동일 흐름, `status='거절'` | 

- **기존 `/api/reservations/{rid}/approve`\|`/reject`(로컬 JSON 대상, `api_server.py`)는 전혀 수정하지 않는다** — 새 엔드포인트는 URL이 다르므로(`/api/admin/reservations/...` vs `/api/reservations/...`) 충돌 없음.
- 거절 사유(reason)는 요청 바디로 받되 Sheets에는 쓰지 않고(§1에서 결정한 범위 최소화 원칙 — Sheets `특이사항` 컬럼에 병행 기록하는 것은 GAS 호출 1회 추가를 의미해 이번 Commit 범위 밖으로 결정) Audit 로그의 `note` 필드에만 남긴다.
- Sheets 쓰기 서비스: 현재 `src/services/sheets_readonly_service.py`는 이름 그대로 읽기 전용(ping/list/get/summary)만 구현되어 있다(Sprint 1 설계). 쓰기(`updateStatus`)를 이 파일에 추가하면 "readonly"라는 이름과 모순되므로, **신규 파일 `src/services/sheets_write_service.py`를 추가**해 `update_status(reservation_no, status)` 함수 하나만 구현한다(기존 `sheets_readonly_service.py`의 GAS 호출 패턴을 그대로 재사용, 신규 action을 만들지 않고 기존 `updateStatus` action만 사용).

## 3. Google Sheets 상태 매핑

| Sheets 상태 문자열 | 의미 | 매핑(LEGACY_STATUS_MAP 확장 여부) |
|---|---|---|
| `예약접수` | 승인 대기(기존값, 변경 없음) | 기존 `REQUESTED` 매핑 유지 |
| `예약확정` | 승인됨(기존값, 변경 없음) | 기존 `CONFIRMED` 매핑 유지 |
| `거절`(신규) | 거절됨 | **`core_data_loader.LEGACY_STATUS_MAP`에 `'거절': 'REJECTED'` 1행 추가** — 기존 5개 매핑은 그대로 두고 항목만 추가(삭제 없음), JSON 쪽 `REJECTED` 상태와 의미가 일치하므로 기존 Enum을 재사용) |

**Google Sheets 컬럼/구조 변경 없음** — §1에서 확인했듯 `예약상태` 컬럼은 이미 자유 텍스트로 저장되며 새 값 추가에 스키마 변경이 필요하지 않다. `LEGACY_STATUS_MAP`(Python 코드, `core_data_loader.py`)에 항목 1개를 추가하는 것은 Sheets 자체의 변경이 아니라 Python 쪽 매핑 테이블 확장이다.

## 4. Audit Hook

기존 `src/reservation/reservation_audit.py::append_audit()`를 **그대로, 수정 없이** 재사용한다. 함수 시그니처가 이미 범용적이라(`entity_id: str | None`은 임의 문자열 허용) Sheets `reservationNo`(`YYYYMMDD-NNNN`, `RSV-` 접두어 없음)를 그대로 넘길 수 있다. 사용할 기존 이벤트 타입도 이미 `AUDIT_EVENTS`에 등록되어 있다 — 신규 이벤트 추가 불필요.

- 승인 성공 시: `append_audit(data_dir, "RESERVATION_APPROVED", "Reservation", reservationNo, actor_user_id, before={"status": "예약접수"}, after={"status": "예약확정"}, channel="ADMIN_PORTAL")`
- 거절 성공 시: `append_audit(data_dir, "RESERVATION_REJECTED", "Reservation", reservationNo, actor_user_id, before={"status": "예약접수"}, after={"status": "거절"}, channel="ADMIN_PORTAL", note=reason)`
- 이 로그는 Single Admin Portal의 기존 감사로그 탭(Sprint 3 Commit 3, `GET /api/audit-logs` 재사용)에서 **별도 개발 없이 즉시 조회 가능**하다 — Sprint 3에서 이미 구축한 재사용 원칙이 여기서도 그대로 이어진다.

## 5. Portal 승인 UI

`admin_portal_new.html`의 **기존 예약조회 탭**(Sprint 1~2, `renderTable()`)에 승인/거절 버튼을 추가한다 — 신규 탭을 만들지 않는다(이미 예약 목록이 있는 화면에 쓰기 액션만 얹는 것이 Sprint 3 CRM 상담관리 탭의 상태전이 버튼 패턴과 동일).

- `status === '예약접수'`이고 현재 사용자가 `reservation:approve` 권한을 가진 경우에만 행에 [승인]/[거절] 버튼 노출(권한 없는 사용자에게는 버튼 자체를 숨기지 않고 — 기존 Sprint 3 RBAC 패턴처럼 — 클릭 시 403을 그대로 노출할지, 아니면 프론트에서 먼저 숨길지는 구현 시 Sprint 3 CRM 버튼 패턴(서버 응답 기반 403 처리)을 따른다).
- 성공/실패 피드백은 Sprint 3 Commit 5에서 구축한 `showToast()`를 그대로 재사용(신규 알림 시스템 불필요).
- 거절 시 사유 입력은 간단한 `prompt()` 또는 인라인 입력창 — 구현 단계에서 확정(신규 모달을 만들 만큼 복잡하지 않다고 판단).

## 6. 명시적 제외 범위 (Commit 3으로 이관)

- Slot 조회/점유/정원 검사 — Sheets에는 애초에 Slot 개념이 없음(`Reservation_Data_Mapping_and_Migration_Plan_v1.0.md` §7). 승인 시 정원을 확인하지 않는다 — 이번 Commit은 순수하게 "상태를 예약접수→예약확정/거절로 바꾸는" 기능만 다룬다.
- 검진중/검진완료/일정변경/예약취소 — 기존 `admin_reservations_v2_new.html`이 계속 담당.
- 로컬 JSON 예약(`admin/index.html`)의 승인/거절 — 이미 존재하는 기능이며 이번 Commit이 손대지 않음.

## 7. 기존 기능 삭제 금지 확인

| 대상 | 처리 |
|---|---|
| `api_server.py`의 `/api/reservations/{rid}/approve`\|`/reject`(로컬 JSON) | 무수정 |
| `admin_reservations_v2_new.html`(Sheets 조회/상태변경/메모) | 무수정 |
| `admin/index.html`(로컬 JSON 승인/거절/Slot/일정) | 무수정 |
| `sheets_readonly_service.py`(읽기 전용 서비스) | 무수정(신규 파일 `sheets_write_service.py`로 분리) |
| `core_data_loader.LEGACY_STATUS_MAP` | 기존 5개 항목 유지, `'거절': 'REJECTED'` 1개 항목만 **추가** |
| `sheets_api_v3_final.gs`(GAS) | **무수정**(§1/§3에서 확인한 대로 기존 `updateStatus` action이 이미 임의 문자열을 받아들이므로 코드 변경 불필요) |

## 8. 영향도 분석

| 영향 대상 | 분석 |
|---|---|
| 신규 FastAPI 엔드포인트 2개 | 기존 엔드포인트와 URL 겹치지 않음, 신규 추가이므로 회귀 위험 낮음 |
| `LEGACY_STATUS_MAP` 확장 | `core_data_loader.legacy_status_to_standard()`(139행, `LEGACY_STATUS_MAP.get(status, status)`)를 사용하는 모든 호출부에 영향 — grep으로 전수 확인 필요(구현 단계에서 수행), 기존 5개 키는 그대로이므로 기존 동작에는 영향 없고 새 키 조회만 추가됨 |
| `admin_reservations_v2_new.html`(기존 Sheets 관리 화면) | **간접 영향 발견**: 이 화면의 상태 필터 드롭다운(`<option>예약접수</option><option>예약확정</option><option>검진완료</option><option>일정변경</option><option>예약취소</option>`)에 **"거절"이 없다.** Commit 2 이후 Portal에서 거절 처리된 예약은 이 화면에서 "전체" 필터로는 보이지만 개별 상태 필터로는 걸러지지 않는다. **이번 Commit에서는 이 파일을 수정하지 않기로 결정**(기존 화면 무수정 원칙 우선) — 이 갭은 알려진 제약으로 문서화하고 Commit 5(Legacy Admin 흡수) 또는 별도 PM 결정 시점까지 남겨둔다. |
| 감사로그 탭(Sprint 3) | 신규 이벤트 타입 없이 기존 `RESERVATION_APPROVED`/`RESERVATION_REJECTED`만 사용하므로 무영향(그대로 조회 가능) |
| PII | 승인/거절은 상태값만 변경하므로 PII 노출 범위 변화 없음 |
| Sheets 실 데이터 | 이번 Commit 개발·테스트는 전 세션과 동일하게 `CSHSP_GAS_WEBAPP_URL` 미설정 샌드박스에서만 수행 — 실 Sheets 접근 없음 |

## 9. 회귀 테스트 계획

### 9-1. 신규 자동화 테스트(`tests/run_sprint4_commit2_approval_qa.py`, Sprint 3 패턴 준용)

- 권한 매트릭스: STAFF(reservation:approve 보유)→200, DIRECTOR/CRM/AI-AGENT(미보유)→403, 헤더 없음→401(Authentication→RoleCheck 순서 재확인)
- 상태 전이 검증: `예약접수`→승인 200, `예약접수`→거절 200, 이미 `예약확정`인 건에 승인 재시도→409, `거절`된 건에 승인 시도→409(종결 상태)
- Audit 로그 기록 검증: 승인/거절 후 `GET /api/audit-logs`에서 해당 `RESERVATION_APPROVED`/`RESERVATION_REJECTED` 레코드 조회 확인
- GAS 코드 무변경 확인: `git diff --name-only HEAD`에 `sheets_api_v3_final.gs`가 없는지 자동 검사(Sprint 3에서 확립한 패턴 재사용)
- `LEGACY_STATUS_MAP` 회귀: 기존 5개 키가 여전히 정확히 매핑되는지 재검증

### 9-2. 기존 전체 회귀 스위트 재실행

Sprint A~I + Single Admin Portal Sprint 1~3 + Sprint 4 Commit 0/1(문서뿐이라 코드 테스트 대상 아님) 전체 재실행, 신규 회귀 없음 확인(`run_sprint3_full_regression_summary.py` 패턴을 Sprint 4용으로 확장할지, Commit 2 전용으로 별도 실행할지는 구현 단계에서 결정 — Commit 6에서 최종 통합).

### 9-3. 실브라우저 QA(임시 서버 + 샌드박스, 종료 후 삭제)

- STAFF로 예약조회 탭에서 `예약접수` 건 승인 → 토스트 확인 → 목록에서 `예약확정`으로 갱신 확인
- STAFF로 다른 건 거절 → 토스트 확인 → `거절`로 갱신 확인
- DIRECTOR로 승인 시도 → 403 토스트(alert 아님, Sprint 3 Commit 5 패턴) 확인
- 감사로그 탭에서 방금 승인/거절 이벤트 조회 확인

## 10. Rollback 방법

- 코드: 신규 파일(`reservation_approval_states.py`, `sheets_write_service.py`) 삭제 + `routes_admin_portal.py`/`admin_portal_new.html`/`core_data_loader.py`의 추가분만 `git revert`로 되돌림(기존 파일을 부분 수정하므로 diff 단위 revert).
- 데이터: 이번 Commit은 Sheets 실데이터를 건드리지 않는 개발 단계이므로(샌드박스만 사용) 데이터 Rollback 대상 없음. 실제 배포 이후 문제 발견 시 GAS는 무수정이므로 GAS 롤백 불필요, FastAPI만 이전 커밋으로 되돌리면 승인/거절 엔드포인트가 사라지고 Sheets에 이미 기록된 `거절` 값은 텍스트로 남아있으나(무해, 스키마 손상 아님) `LEGACY_STATUS_MAP` 역시 함께 되돌아가 `거절`이 매핑되지 않은 원문 그대로 조회됨(치명적이지 않음, 기존 5개 키 동작에는 영향 없음).

## 11. PM 승인 필요 사항 (이번 계획에서 제가 내린 판단, 확인 요청) — ✅ PM 조건부 승인으로 아래 §12에서 확정

1. §1: "승인대기" 신규 상태값을 만들지 않고 기존 "예약접수"를 승인 대기 상태로 그대로 쓰는 것 — **PM 결정 1로 확정(동의)**.
2. §2: 거절 사유를 Sheets `특이사항`에는 기록하지 않고 Audit 로그에만 남기는 것 — **PM 결정 2로 확정(동의, 단 사유 입력을 필수·검증 대상으로 강화)**.
3. §8: `admin_reservations_v2_new.html`의 상태 필터 갭을 그대로 둘지 — **PM 결정 3으로 방향이 바뀜: 무수정이 아니라 "거절" 옵션을 추가(필수 호환성 보완)로 확정**.

---

## 12. PM 조건부 승인 반영 (2026-07-28, 코드 작성 전 최종 확정본)

### 12-1. 상태 전이 — PM 결정 1 그대로 채택(변경 없음)

이번 Commit이 허용하는 전이는 **`예약접수 → 예약확정`, `예약접수 → 거절` 두 가지뿐**이다. §1의 원안과 동일 — `SHEETS_APPROVAL_TRANSITIONS = {"예약접수": {"예약확정", "거절"}}`. 그 외 모든 전이(예: `예약확정`에서 거절, `거절`에서 재승인 등)는 409로 차단한다.

### 12-2. 거절 사유 — PM 결정 2 반영(원안 대비 강화)

원안(§2, §5)의 "간단한 사유 입력"을 아래 명시 규칙으로 구체화한다.

| 규칙 | 구현 방식 |
|---|---|
| 필수 입력 | Pydantic `RejectBody.reason: str` 필드, 누락 시 자동 422(FastAPI 기본 동작) |
| 앞뒤 공백 제거 | `field_validator`에서 `.strip()` |
| 빈 문자열 금지 | trim 후 길이 0이면 422 |
| 최소·최대 길이 | 최소 2자, 최대 200자(운영 메모 성격의 다른 필드 관행을 참고한 보수적 기본값 — 근거 문서 없음, 실사용 피드백에 따라 추후 조정 가능함을 §14 알려진 제약에 기록) |
| 개인정보·민감정보 입력 금지 | 연속 숫자 6자리 이상(`\d{6,}`, 전화번호·주민등록번호 패턴 방어) 발견 시 422로 거부 — 완전한 PII 탐지는 아닌 휴리스틱임을 명시. UI에도 "개인정보를 입력하지 마세요" 안내 문구를 함께 노출(이중 방어: UI 안내 + 서버 검증) |
| Sheets 저장 범위 | `예약상태` 값(`거절`)만 Sheets에 기록, 사유는 Sheets에 전송하지 않음(원안 §2 유지) |
| Audit 기록 | 거절 사유는 `append_audit()`의 `note` 파라미터에 저장(전용 필드 재사용, 신규 필드 추가 없음) |

### 12-3. Legacy UI 필터 — PM 결정 3 반영(원안 방향 전환)

원안 §8에서 "무수정 우선"으로 판단했던 것을 PM이 뒤집었다 — `admin_reservations_v2_new.html`의 상태 드롭다운 2곳(상단 필터 `#fStatus`, 상세 모달의 상태변경 `#statusSel`)에 `<option>거절</option>`을 **추가만** 한다(기존 5개 옵션 순서·값 변경 없음). 두 곳 모두 동일한 옵션 목록을 공유하므로, 필터(`#fStatus`)뿐 아니라 상태변경 드롭다운(`#statusSel`)에도 함께 추가한다 — 후자에 추가하지 않으면 Portal에서 거절 처리된 예약을 이 화면의 상세 모달로 열었을 때 상태 드롭다운이 "거절"을 표시할 방법이 없어(일치하는 `<option>` 부재) 오히려 새로운 표시 오류를 만들기 때문이다. PM 지시("상태 필터에 거절 옵션 추가")를 실무적으로 안전하게 만족시키기 위한 해석 확장이며, 두 곳 모두 **추가만** 하므로 "기존 기능 삭제·변경 금지" 원칙과 상충하지 않는다.

### 12-4. 에러 코드 확정(원안 §9 대비 세분화)

| 코드 | 상황 |
|---|---|
| 401 | 인증 실패(기존 패턴) |
| 403 | `reservation:approve` 권한 없음 |
| 404 | Sheets에 해당 예약번호 없음 |
| 409 | 현재 상태가 `예약접수`가 아님(이미 처리됨/승인·거절 대상 아님) |
| 422 | 거절 사유 누락·유효성 오류(Pydantic 자동 처리) |
| 502 | GAS 호출 실패/오류 응답(`SheetsIntegrationError`, 기존 패턴 재사용) |
| 503 | GAS 미설정(`SheetsIntegrationNotConfigured`, 기존 패턴 재사용) |

### 12-5. 동시성(read → validate → write) — 한계 명시

PM 지시대로 "상태 변경 직전에 Sheets 최신 상태 재확인"을 구현한다: `GET`(현재 상태 조회) → 검증(`예약접수`인지) → `POST updateStatus`(쓰기) 순서를 명시적으로 코드에 나타낸다. 단, **GAS `_actionUpdateStatus`는 compare-and-swap을 지원하지 않고(현재 상태와 무관하게 무조건 덮어씀, 코드 확인됨) 이번 Commit에서 GAS를 수정하지 않기로 했으므로**, Python 쪽의 read→validate→write는 경쟁 조건(두 관리자가 거의 동시에 같은 건을 처리하는 경우)을 **줄이지만 완전히 제거하지는 못한다.** 이 한계는 "가능한 범위에서" 구현하라는 PM 지시와 일치하며, §14(알려진 제약)에 명확히 기록한다.

### 12-6. Audit 실패 정책 — 기존 시스템 규칙 조사 결과

`src/reservation/reservation_engine.py::approve_reservation()`을 확인한 결과, 기존 시스템은 **"상태 변경(write) 성공 → 그 다음 Audit 기록"** 순서를 쓰며, Audit 기록이 예외적으로 실패하는 경우(파일 I/O 오류 등)에 대한 별도의 보상 트랜잭션(상태 롤백)은 구현되어 있지 않다 — 즉 이미 "best-effort, non-transactional" 정책이 기존 시스템 전반에 일관되게 적용되어 있다. 이번 Commit도 **동일한 정책을 그대로 따른다**: Sheets 상태 변경 성공 후 Audit을 기록하고, Audit 기록 자체가 실패하면(현재 등록된 이벤트 타입만 쓰므로 실무적으로는 거의 발생하지 않음) 예외가 그대로 전파되어 500 응답이 되지만 Sheets 상태는 이미 변경된 채로 남는다 — 기존 로컬 JSON 승인 흐름과 동일한 리스크 수준이며 이번 Commit이 새로 만든 리스크가 아니다.

이 계획으로 코드 작성을 시작한다.
