# Sprint8 RBAC Permission Matrix

> **상태**: 설계 계약 초안(Draft). 신규 권한(`reservation:complete`/`reservation:note`) 저장소 미존재, 담당부서·승인권자 DEFERRED, HMAC-RBAC 책임경계 원칙만 정의. Commit 없음.
> **작성일**: 2026-08-02(Sprint8 Commit8-3a STEP 3-D-A)
> **기준선**: `main`/`origin/main` = `650c899f662730a5578a8d1dd6d8897709b5fda0`

---

## 1. 문서 목적과 범위

Admin Operations API Contract §10(인가 및 RBAC 계약)에서 후속 확정으로 위임한 역할×Operation 권한 매트릭스를 정의한다. 저장소에 실제 존재하는 역할·권한 문자열만 "확인된 사실"로 다루며, 신규 권한은 제안(PROPOSED) 또는 미발견(NOT FOUND)으로 명확히 구분한다.

## 2. 기준선 Commit

`650c899f662730a5578a8d1dd6d8897709b5fda0`.

## 3. 선행 문서 및 코드 근거

| 문서/코드 | 경로 |
|---|---|
| ADR-016/017 | `ADR-016_...Draft.md`, `ADR-017_...Operations.md` |
| Security Architecture Design | `docs/Sprint8_Security_Architecture_Design.md` §8 |
| Admin Operations API Contract | `docs/Sprint8_Admin_Operations_API_Contract.md` §10 |
| 역할·권한 정의 | `data/roles.json` |
| Sheets 도메인 권한검사 | `src/api/routes_admin_portal.py` L67(`_build_require_permission`) |
| 로컬 JSON 도메인 권한검사 | `src/api/api_server.py`(`need_perm`), `src/reservation/reservation_engine.py` L64-70(`_has_permission`) |
| GAS 소스 | `app/apps_script/sheets_api_v3_final.gs`(인증·인가 코드 없음) |

## 4. 용어와 판정 라벨

§4 State Transition Matrix와 동일: `CURRENTLY CONFIRMED`/`PROPOSED`/`NOT IMPLEMENTED`/`DEFERRED`/`NOT FOUND`.

## 5. AS-IS 인증 구조

FastAPI 세션(Sprint8 Commit8-2, HttpOnly/Secure/SameSite=Lax, **CURRENTLY CONFIRMED**). GAS는 인증 없음(**CURRENTLY CONFIRMED as 부재**, `doPost` 코드 재확인).

## 6. AS-IS 인가 구조

**두 개의 독립된 데이터플레인에 각각 다른 인가 구현이 존재**(CLAUDE.md "이중 백엔드" 원칙과 일치):

| 데이터플레인 | 인가 구현 위치 | 방식 |
|---|---|---|
| Sheets 도메인(`routes_admin_portal.py`) | `_build_require_permission(data_dir, *perms)`(L67) | FastAPI `Depends` 데코레이터 |
| 로컬 JSON 도메인(`api_server.py`/`reservation_engine.py`) | `need_perm()`, `_has_permission()`(engine.py L64-70) | 함수 호출 내부 검사 |
| GAS(Sheets 직접호출) | **없음** | 해당없음 |

## 7. 역할 정의의 실제 저장 위치

`data/roles.json`(**CURRENTLY CONFIRMED**, PII 없음 `meta.containsPII:false` 확인). 5개 역할: `ROLE-DIRECTOR`/`ROLE-ADMIN`/`ROLE-STAFF`/`ROLE-CRM`/`ROLE-AI-AGENT`.

## 8. Permission 정의의 실제 저장 위치

동일 파일(`data/roles.json`) 내 각 역할의 `permissions` 배열. **18개 Permission 문자열 확인**(재확인, `grep -oE '"[a-z]+:[a-z*]+"'`): `audit:view`/`crm:log`/`crm:manage`/`dashboard:view`/`notification:draft`/`notification:send`/`patient:edit`/`patient:view`/`program:view`/`reservation:approve`/`reservation:cancel`/`reservation:change`/`reservation:request`/`reservation:view`/`schedule:manage`/`slot:manage`/`slot:view`/`statistics:view`, 그리고 ROLE-ADMIN 전용 `"*"` 와일드카드.

## 9. 역할과 Permission 연결 방식

역할별 `permissions` 배열에 직접 나열(**CURRENTLY CONFIRMED**), `_has_permission()`이 `"*" in perms or perm in perms`로 검사(L70).

## 10. 서버측 권한검사 위치

§6 표 참조. **중요 정정**: 이전 STEP들(ADR-017 §20, Admin Operations API Contract §16)에서 "`reservation:cancel`은 정의만 있고 어떤 라우트도 검사하지 않는다"고 기술했으나, **이번 재조사로 정정한다** — `reservation:cancel`은 **로컬 JSON 도메인**(`reservation_engine.py` L449, `_has_permission(actor_user_id, "reservation:cancel", data_dir)`)에서 **실제로 시행되고 있음(CURRENTLY CONFIRMED)**. 단, 이는 `api_server.py`의 `/api/reservations/{rid}/cancel`(RSV- 접두, 로컬 JSON)이 대상이며, **이 문서와 API Contract가 다루는 Sheets 도메인의 CANCEL Operation(예약번호 YYYYMMDD-NNNN 형식)에는 여전히 대응 시행코드가 없다(NOT IMPLEMENTED, Sheets 도메인 한정)**. 두 도메인을 구분하지 않으면 오판할 수 있는 지점이라 명시적으로 정정·기록한다.

## 11. 클라이언트측 표시제어와 서버측 인가 구분

Legacy Portal의 `approvalBlocked` 클라이언트 가드(Sprint6 Commit6-1, "예약확정" 전이만 화면에서 차단)는 **서버측 인가가 아님**(**CURRENTLY CONFIRMED as UI 레벨 우회 가능**, ADR-016 companion §5-1 항목2 재확인 — Web App URL 직접 호출 시 완전히 우회됨). 이 문서는 UI 숨김을 보안 통제로 간주하지 않는다(작성 원칙 준수).

## 12. GAS 인증·인가 현재 상태

`doPost`/`doGet`은 action 문자열만으로 분기하며 호출자 인증·인가 코드가 전혀 없다(**CURRENTLY CONFIRMED as 부재**, 전체 파일 재확인). **이는 현재 보안 Gap으로 명시한다**(작성 원칙 준수).

## 13. 관리자 Operation 8개

State Transition Matrix §11-19와 동일 8개: LIST/DETAIL/APPROVE/REJECT/RESCHEDULE/CANCEL/COMPLETE/NOTE.

## 14. Operation별 Permission 후보

| Operation | Permission string | Exists in repository | Enforcement location | Current status | Approval owner | Evidence |
|---|---|---|---|---|---|---|
| LIST | `reservation:view` | 예(**CURRENTLY CONFIRMED**) | `routes_admin_portal.py` L189(Sheets 도메인) | 시행중 | 해당없음(기존확정) | L189 |
| DETAIL | `reservation:view` | 예 | 상동 | 시행중 | 해당없음 | 상동 |
| APPROVE | `reservation:approve` | 예 | `routes_admin_portal.py` L689(Sheets 도메인) | 시행중 | 해당없음 | 코드 |
| REJECT | `reservation:approve` | 예 | 상동 | 시행중 | 해당없음 | 코드 |
| RESCHEDULE | `reservation:change`(제안, 기존문자열 재사용) | 예(단 **로컬 JSON 도메인에서만 시행중**, `api_server.py::need_perm`) | **Sheets 도메인 미시행(NOT IMPLEMENTED)** | PROPOSED(Sheets 도메인 신규 연결 필요) | **DEFERRED**(STEP1§24-3 유사 성격) | `api_server.py` need_perm 호출부 |
| CANCEL | `reservation:cancel`(제안, 기존문자열 재사용) | 예(단 **로컬 JSON 도메인에서만 시행중**, §10 정정사항) | **Sheets 도메인 미시행(NOT IMPLEMENTED)** | PROPOSED | **DEFERRED** | `reservation_engine.py` L449 |
| COMPLETE | `reservation:complete`(신규) | **NOT FOUND**(저장소 전체 검색 0건, 재확인) | 없음 | **PROPOSED, 미구현** | **DEFERRED**(STEP1§24-3) | 없음(부재 확인) |
| NOTE | `reservation:note`(신규) | **NOT FOUND**(상동) | 없음 | **PROPOSED, 미구현** | **DEFERRED** | 없음(부재 확인) |

## 15. 역할별 Permission Matrix

| Role | LIST | DETAIL | APPROVE | REJECT | RESCHEDULE | CANCEL | COMPLETE | NOTE | Evidence | Decision status |
|---|---|---|---|---|---|---|---|---|---|---|
| ROLE-DIRECTOR | O(조회만, `reservation:view`) | O | X | X | X | X | X | X | `data/roles.json` | 확정(조회권한만 보유) |
| ROLE-ADMIN | O(`*`) | O | O | O | O(권한상 가능, 문자열 보유) | O(권한상 가능) | **DEFERRED**(권한자체 NOT FOUND) | **DEFERRED**(상동) | `data/roles.json` `"*"` | 부분확정 |
| ROLE-STAFF | O(`reservation:view`) | O | O(`reservation:approve`) | O | O(`reservation:change`, 단 로컬JSON도메인만 시행중) | O(`reservation:cancel`, 상동) | **DEFERRED**(권한 NOT FOUND) | **DEFERRED**(상동) | `data/roles.json` | 부분확정 |
| ROLE-CRM | X(reservation:view 있음, 상세는 별개) | O(`reservation:view`) | X | X | X | X | X | O(`crm:manage`로 메모유사기능 보유, NOTE Operation 자체와는 별개 판단 필요 — **DEFERRED**) | `data/roles.json` | 부분확정 |
| ROLE-AI-AGENT | X | X | X | X | X | X | X | X | `data/roles.json`(`reservation:request`만 보유) | 확정(권한 없음) |

**주의**: 위 표의 "O"는 "해당 권한 문자열을 역할이 보유"를 의미할 뿐, RESCHEDULE/CANCEL 항목의 "O"는 **로컬 JSON 도메인 한정**이며 Sheets 도메인(이 문서의 실제 대상)에는 시행 코드가 없다(§10). COMPLETE/NOTE의 "DEFERRED"는 권한 문자열 자체가 저장소에 없어(§14 NOT FOUND) 어떤 역할도 실제로 보유할 수 없는 상태임을 의미한다.

## 16-23. Operation별 권한 상세

§14 표에 통합 기재.

## 24. 신규 후보 Permission 존재 여부

`reservation:complete`, `reservation:note` **모두 저장소에 존재하지 않음(NOT FOUND, 재확인 완료)**. 두 문자열 모두 이전 STEP(ADR-017 §20)에서 이미 "미구현"으로 명시되었으며, 이번 재조사로 "구현 완료로 오인되지 않도록" 재확인한다(작성 원칙 준수).

## 25. 승인권자·담당부서 결정 상태

**전부 DEFERRED**(STEP1§24-3, "실제 운영 담당부서 확인 필요, 코드로 확인 불가"). 이 문서는 어떤 부서·직책도 임의 지정하지 않는다.

## 26. 최소권한 원칙

기존 `ROLE-AI-AGENT`는 `reservation:request`만 보유하고 승인·조회 관련 권한이 전혀 없음이 확인됨(**CURRENTLY CONFIRMED**, `data/roles.json`) — 최소권한 원칙이 이미 부분 적용된 사례로 확인.

## 27. 명시적 거부 원칙

`_has_permission()`은 권한 부재 시 `False` 반환(기본 거부, **CURRENTLY CONFIRMED**). FastAPI `_build_require_permission()`도 동일 원칙으로 추정되나 이 STEP에서 전체 구현을 재확인하지 않았으므로 **NOT FOUND(이번 조사 범위 밖)로 표시**하지 않고 이전 STEP(Commit8-2)에서 이미 CURRENTLY CONFIRMED로 확인된 사실을 재인용한다.

## 28. 권한 없는 요청의 오류계약

`PERMISSION_DENIED`(ADR-017 §12, Admin Operations API Contract §14 재인용) — 새로운 오류코드를 이 문서에서 만들지 않는다(작성 원칙 준수).

## 29. 감사로그 필수항목

State Transition Matrix §31과 동일(`append_audit()` 재사용).

## 30. 역할·권한 변경 감사

**NOT FOUND**(저장소에 역할/권한 변경 자체를 감사로그로 남기는 코드는 이번 조사에서 발견되지 않음) — Open Question(§35)으로 유지.

## 31. HMAC와 사용자 인가의 책임 경계

**명확히 구분**: HMAC(ADR-017)은 FastAPI-GAS **서버간** 요청 무결성·인증 수단이며, 특정 사용자가 어떤 권한을 가졌는지와는 무관하다. 사용자별 RBAC(이 문서)는 FastAPI 세션 계층에서만 판단되며 GAS는 이를 알지 못한다(**CURRENTLY CONFIRMED**, GAS에 사용자 개념 자체가 없음). 즉 **HMAC 서명이 유효해도 그 서명을 만든 FastAPI 요청이 적절한 RBAC 검사를 거쳤는지는 HMAC이 보장하지 않는다** — RBAC는 FastAPI 계층의 책임이며 이는 이번 설계에서도 변경되지 않는다(작성 원칙 준수, 책임 경계 유지).

## 32. 직접 GAS 호출 위험

§12 재확인 — GAS는 호출자를 구분하지 못하므로, HMAC 미적용 상태에서 Web App URL을 아는 누구나 임의 권한으로 상태변경 가능(**CURRENTLY CONFIRMED as Critical 위험**, Security Gate STEP1과 동일 결론 재확인).

## 33. UI 숨김과 보안통제의 차이

§11 재확인 — Legacy Portal의 `approvalBlocked` 클라이언트 가드는 서버측 인가가 아니며 우회 가능함을 재확인.

## 34. 코드와 문서 불일치

1. **`reservation:cancel`/`reservation:change` 시행 여부의 도메인 구분 누락**(§10) — 이전 ADR-017 §20/API Contract §16이 "미사용 정의"라고 단순화했던 것을, 이번 조사에서 "로컬 JSON 도메인에서는 시행 중, Sheets 도메인에서는 미시행"으로 **정정**했다. 이는 오류 정정이며 새로운 정책 결정이 아니다.
2. 역할·권한 변경 자체의 감사로그 부재(§30) — 문서화된 요구사항은 없었으나(Gap이라기보다 미조사 영역), Open Question으로 신규 등록.

## 35. 미결정 사항

승인권자·담당부서(§25), `reservation:complete`/`reservation:note` 신설 최종 확정(권한명·구현 여부), 역할·권한 변경 감사(§30), ROLE-CRM의 NOTE Operation 관련 권한(§15 "DEFERRED" 표시) — 전부 이 문서에서 확정하지 않는다.

## 36. 후속 구현 및 테스트 Gate 입력사항

Commit8-3d 착수 전 확정 필요: STEP1§24-3(담당부서), `reservation:complete`/`reservation:note` 신설 최종 승인. Security Test and Deployment Gate Plan(STEP3-E)은 §32(직접 GAS 호출 위험)를 필수 회귀 테스트 항목 후보로 참조 가능(채택 여부는 확정하지 않음).

## 37. 추적성 표

| ID | 출처 | 이 문서 반영 위치 | 최종상태 |
|---|---|---|---|
| companion#6 | companion §16 | §14/§24(신설 여부) | PROPOSED(미구현 유지) |
| STEP1§24-2 | 세션(STEP1) | §14(권한명칭 후보) | PROPOSED |
| STEP1§24-3 | 세션(STEP1) | §25(담당부서) | DEFERRED |
| ADR-017 §20 | ADR-017 | §10(정정 대상) | 정정 반영(이 문서에서) |

## 38. 결론

역할 5종·권한 18종은 저장소에서 명확히 확인되었으나, 신규 권한 2종(`reservation:complete`/`reservation:note`)은 저장소에 전혀 존재하지 않는다(NOT FOUND). 이번 조사에서 `reservation:cancel`/`reservation:change`의 시행 여부가 데이터플레인(Sheets vs 로컬 JSON)에 따라 다르다는 점을 새로 확인·정정했다(§10, §34). RBAC 완전 확정은 STEP1§24-3(담당부서)의 PM 결정 없이는 불가능하다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 어떤 기존 파일도 수정하지 않았다. 역할·권한을 새로 발명하지 않았다(저장소에서 확인된 문자열만 사용). 신규 권한을 구현 완료로 표현하지 않았다. 승인권자·담당부서를 임의 지정하지 않았다. UI 숨김을 서버측 인가로 표현하지 않았다. 실제 Secret·PII·운영 URL 미포함. Git add/commit/push 없음.
