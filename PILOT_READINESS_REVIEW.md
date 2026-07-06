# PILOT_READINESS_REVIEW.md — Pilot 운영 시작 전 최종 검토 보고서

**대상 릴리스**: v0.9.0-pilot
**작성일**: 2026-07-04
**목적**: Architecture Freeze 완료 이후, Pilot 운영 개시 가능 여부를 판단하기 위한 최종 검토

---

## 1. 결론 (3단계 판정)

이 프로젝트는 **Architecture / Pilot / Production 3단계를 서로 다른 기준으로 판정**한다. 하나의 Go/No-Go로 뭉뚱그리지 않고, 각 단계별 준비도를 독립적으로 관리한다.

| 단계 | 판정 | 의미 |
|---|---|---|
| **Architecture** | 🟢 **PASS** | 설계·구조·표준 문서(SSOT) 확정 완료. Freeze 선언 가능 상태 |
| **Pilot** | 🟡 **Conditional Go** | 제한된 조건 하에 파일럿 운영 착수 가능. 단, 아래 §3 Known Issues를 인지하고 그 영향 범위 내에서만 운영 |
| **Production** | 🔴 **No-Go** | 정식 운영(Go-Live) 개시는 불가. §3 Known Issues 전부 해결 및 Production Checklist 완료 전까지 유지 |

**요약**: Architecture Freeze는 완료되었고, 그 기반 위에서 조건부로 Pilot을 시작할 수 있는 상태다. 다만 Pilot 기간 중에도 §3의 미해결 이슈들이 실제 운영 데이터 정합성·본인확인·알림 발송에 영향을 준다는 점을 인지하고 범위를 제한해야 하며, 이 이슈들이 모두 해소되기 전에는 정식 Production(Go-Live)으로 전환할 수 없다.

---

## 2. Architecture — 🟢 PASS 근거

| 항목 | 확인 결과 |
|---|---|
| SSOT 문서 5종(CLAUDE/ARCHITECTURE/ROADMAP/DECISIONS/PROJECT_STATUS) 존재 | ✅ 확인 |
| Sprint A~I, Sprint 2 기능 개발 완료 | ✅ 확인 (ROADMAP.md) |
| Quality Gate 통과 (Sprint I) | ✅ PASS (FAIL 0, WARN 2, SKIPPED 1), 회귀 148/148 PASS |
| AI Safety 통과 | ✅ 금지응답 35/35 차단, 3중 방어(Safety Guard/Tool 화이트리스트/RBAC) 확인 |
| Release 문서 완료 | ✅ README/CHANGELOG/LICENSE/.gitignore/requirements.txt/.env.example/RELEASE_NOTES 작성 완료 |
| 운영 문서 완료 | ✅ backup_policy.md, process_manager.md, production_checklist.md, Failure_Response_Manual 등 존재 |
| Architecture Freeze는 미해결 버그와 독립적으로 완료 가능 | ✅ DECISIONS.md ADR-010으로 명문화됨 |

**Architecture는 PASS로 확정한다.**

---

## 3. Known Issues — Pilot 운영 전 해결 권고 사항

아래 4개 항목은 Pilot의 **Conditional Go 판정을 뒤집는 차단 조건은 아니지만**, Production(Go-Live) 전환을 막는 필수 해결 과제다. Pilot 기간 중에는 각 이슈의 영향 범위를 인지한 상태로 운영해야 한다.

| # | 항목 | 상태 | 영향 범위 | 근거 |
|---|---|---|---|---|
| 1 | **STEP1.5 DateFix** 미배포 | 🔴 미해결 | 예약 데이터의 birth/wishDate/wishTime 표시·통계 정합성 오류 | PROJECT_STATUS.md §2 — 재QA 1차 실패 확인됨 |
| 2 | **DEV-003 Sheets 연동** 미구현 | ⚠️ 설계만 확정 | 관리자 예약관리 화면에서 Sheets 데이터 조작 불가(기존 localStorage 화면으로만 대체 운영) | 코드 미작성, DECISIONS.md ADR-007 |
| 3 | **실인증** 미구현 | 🔴 미해결 | 현재 Mock 인증(X-User-Id)/Mock 본인확인 코드로 대체 운영 중 — 실제 신원확인 보증 없음 | production_checklist.md B, CLAUDE.md·CSHSP_Operation_Transition_Sprint_H.md 실연동 교체 지점 |
| 4 | **실발송** 미구현 | ⚠️ 미해결 | 알림톡/SMS가 Mock 발송(PENDING 큐 적재)까지만 동작, 실제 문자 발송 없음 | notification_worker.py `default_mock_sender`, production_checklist.md E |

이 4개 항목은 **Pilot 운영 전 해결 권고 사항**으로 분리 관리하며, Sprint J 착수 여부와 별개로 추적한다(ROADMAP.md).

> 참고: 더미 데이터/계정 정리(QA 더미 예약, USR-0001~0003)는 위 4개 항목과 별개로 Production Checklist §4 B/C 섹션에서 계속 추적한다(운영 데이터 정합성에는 영향이 크지 않아 Known Issues 목록에서는 제외).

---

## 4. Pilot Conditional Go의 조건

Pilot을 "조건부로" 시작할 수 있다고 판단하는 근거와 그 조건은 다음과 같다.

- **조건부 승인 근거**: Architecture PASS, Quality Gate 통과, AI Safety 통과, 운영 문서 완비 — 파일럿 규모의 제한된 운영을 지탱할 최소 요건은 충족됨.
- **조건 1**: 파일럿 기간 중 예약일자/생년월일 등 날짜 데이터는 Sheets 조회 시 육안 재확인을 병행한다(§3-1 DateFix 미해결 보완).
- **조건 2**: 관리자의 Sheets 기반 예약관리 기능은 사용하지 않고 기존 localStorage 기반 화면으로 운영을 대체한다(§3-2 DEV-003 미구현 보완).
- **조건 3**: 본인확인은 Mock 방식의 한계를 내부망 한정 운영으로 상쇄하며, 실제 환자 대면 확인 등 보완 절차를 병행한다(§3-3 실인증 미해결 보완).
- **조건 4**: 알림은 Mock 발송(대기 큐)까지만 동작하므로, 파일럿 기간 중 실제 알림이 필요한 경우 직원이 수동으로 대체 발송한다(§3-4 실발송 미해결 보완).

이 조건들을 충족하지 못하는 규모나 방식으로는 Pilot을 확장하지 않는다.

---

## 5. Production Checklist 현황 (`src/deploy/production_checklist.md`)

Sprint H에서 작성된 A~F 6개 섹션, 총 24개 항목을 재확인한 결과, **현재까지 체크 완료된 항목은 없다(전 항목 미체크 상태)**. 이는 이 체크리스트가 "정식 운영 서버 배치 시점"에 수행하는 절차이며, 아직 그 단계(Production)에 도달하지 않았기 때문이다.

- **B. 환경변수·보안** — "직원 계정 실계정 교체", "Mock 인증 한계 공지·실인증 필요" 항목은 §3-3(실인증)과 직결
- **D. 기능 검증** — DateFix가 반영되지 않은 상태에서는 "시나리오 리허설(신청→승인→알림→문진→검토)"을 통과해도 날짜 데이터 정합성 문제가 재현될 수 있음 → §3-1 해결이 선행되어야 이 섹션의 검증이 의미를 가짐
- **E. 운영 준비** — "알림 발송 정책 확정(Mock→실발송 연동 시점 결정)" 항목은 §3-4(실발송)와 직결

**Production Checklist는 §3 Known Issues가 모두 해소된 이후 A~F 순서로 실제 점검에 착수하는 것을 권장한다. 이 체크리스트 완료 전까지 Production 판정은 No-Go로 유지한다.**

---

## 6. 보안/설정 추가 확인 사항

- `app/apps_script/sheets_api_v3_final.gs`에 운영 `SPREADSHEET_ID`가 하드코딩되어 있음을 확인. 현재는 git 저장소가 아니라 즉각적 노출 위험은 낮으나, 향후 버전관리 도입 시 반드시 `.gitignore` 또는 설정 분리로 보호해야 함(RELEASE_NOTES_v0.9.0-pilot.md §5, §6 참조).
- `ANTHROPIC_API_KEY` 등 민감 환경변수는 `.env.example`에 값 없이 템플릿만 제공됨을 확인 — 적절.
- HTTPS 미구현 상태를 재확인 — Production Checklist A 섹션에서 다룰 항목이며 정식 Go-Live 전 필수.

---

## 7. 이번 릴리스에서 변경하지 않은 것 (범위 확인)

사용자 지시에 따라 이번 작업은 **문서·릴리스 준비에 한정**했으며, 다음은 수행하지 않았다.

- 기능 코드 수정 (STEP1.5 DateFix 실제 배포 포함)
- DEV-003 구현, 실인증/실발송 구현
- 더미 데이터/계정 삭제
- git 저장소 초기화(`git init`) 및 실제 커밋/태그 생성

---

## 8. 다음 조치 제안 (우선순위 순)

1. Pilot Conditional Go 조건(§4)을 관계자와 공유하고 파일럿 범위를 그 조건 내로 제한
2. STEP1.5 DateFix를 Apps Script에 실제 배포하고 재QA 통과 확인 (PROJECT_STATUS.md §2 절차 그대로 수행)
3. DEV-003(`admin_reservations_v2_new.html`) 구현
4. 실인증(SMS/알림톡 인증코드 등) 연동
5. 실발송(SMS/알림톡) 연동
6. 위 §3 Known Issues 4건이 모두 해소되면 본 보고서를 갱신하여 Production 판정을 재평가하고, `production_checklist.md` A~F 순차 점검에 착수

---

## 9. 관련 문서

- [PROJECT_STATUS.md](PROJECT_STATUS.md) — 현재 상태, Known Issues
- [ROADMAP.md](ROADMAP.md) — Sprint J 이전 필수 해결 과제
- [DECISIONS.md](DECISIONS.md) — ADR-010 (Architecture Freeze와 Pilot Ready 분리 원칙)
- [RELEASE_NOTES_v0.9.0-pilot.md](RELEASE_NOTES_v0.9.0-pilot.md) — 이번 릴리스 상세
- `src/deploy/production_checklist.md` — 운영 전 점검표 원본
