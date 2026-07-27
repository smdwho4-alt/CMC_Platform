# SSOT Update Checklist

> **성격**: `SSOT_Document_Alignment_Plan_v1.0.md`(Sprint 4 Architecture Gate 단계 산출물)에서 식별한 정정 대상을 **실행 가능한 체크리스트**로 전환한 문서. Sprint 4 Commit 1(SSOT 문서 정렬)에서 이 체크리스트를 그대로 따라 실제 수정을 수행한다.
> **작성일**: 2026-07-28
> **이번 Commit(Commit 0)에서는 아래 항목을 실행하지 않았다** — `ARCHITECTURE.md`/`ROADMAP.md`/`PROJECT_STATUS.md`/`DECISIONS.md` 원본은 이 문서 작성으로 전혀 수정되지 않았다.

---

## 수정 순서

문서 간 의존관계(더 최신인 문서를 기준점으로 낡은 문서를 정정)를 고려해 아래 순서로 진행한다.

1. **`PROJECT_STATUS.md`** — 가장 최신 사실을 담고 있으나 v1.1.0-beta1(DEV-004) 태그를 반영하지 못했으므로 먼저 기준점을 맞춘다.
2. **`ROADMAP.md`** — 갱신된 `PROJECT_STATUS.md`를 근거로 STEP1.5/DEV-003 관련 낡은 서술을 정정한다.
3. **`ARCHITECTURE.md`** — 버전 관리 서술(§3 기술스택 표)을 정정한다.
4. **`DECISIONS.md`** — ADR-012를 정식 등재하고 ADR-008을 Superseded로 표기한다(마지막에 수행 — 앞 3개 문서 정정이 끝난 뒤 ADR 상태를 확정하는 것이 논리적 순서).

## 체크리스트

### 1. `PROJECT_STATUS.md`

| 항목 | 내용 |
|---|---|
| 대상 | 문서 최상단 "최종 갱신: 2026-07-12 (v1.0.0-pilot 릴리스 반영)" |
| 정정 내용 | "v1.1.0-beta1" 태그 반영(DEV-004, 종합검진 선택검사 Rule 기반 UI 전면 개편, 커밋 `ce6cce2`) + §1 표에 DEV-004 완료 행 추가 |
| 근거 | `git log -1 v1.1.0-beta1` = `ce6cce2 2026-07-12 feat(DEV-004): 종합검진 선택검사 Rule 기반 UI 전면 개편`. `SSOT_Document_Alignment_Plan_v1.0.md` §1-D |
| 영향도 | **낮음** — 표기 갱신 및 표 행 추가만, 다른 문서와의 링크 구조 변경 없음 |
| 검증 방법 | 갱신 후 `git tag`와 `PROJECT_STATUS.md` 최상단 버전 표기가 일치하는지 확인. 문서 내 다른 절(§1~§5)과 신규 추가 행이 모순되지 않는지 재독 |
| Rollback | git이 SSOT이므로(ADR-012) 이전 커밋으로 `git revert` 또는 `git checkout <이전커밋> -- PROJECT_STATUS.md`로 즉시 원복 가능 |

### 2. `ROADMAP.md`

| 항목 | 내용 |
|---|---|
| 대상 1 | "완료된 작업" 표 — STEP1.5 행 "⚠️ 코드 완료, 배포 미반영" |
| 정정 내용 1 | "✅ 완료(2026-07-12, GAS Version 5 재배포)"로 변경 |
| 대상 2 | "Sprint J 이전 필수 해결 과제" 표 — STEP1.5 실배포 행("🔴 미해결, 최우선"), DEV-003 구현 행("⚠️ 설계만 확정, 후순위") |
| 정정 내용 2 | 두 행 모두 "✅ 완료"로 변경, 해당 표 하단 "이 표의 항목이 모두 해소되기 전에는 Sprint J 착수하지 않는다" 문구와의 정합성 재확인(Sprint 4가 이미 착수됐으므로 이 표의 잔여 항목이 실제로 모두 해소됐는지 재검토 필요 — 더미 데이터/계정 정리, 프로젝트 구조 재편 두 항목은 여전히 미해소 상태임을 명시 유지) |
| 대상 3 | "구조 Freeze 및 최우선 작업 순서" 1)/3) 항목의 "🔴 실배포 대기"/"⏳ 대기" 표기 |
| 정정 내용 3 | 완료 반영 |
| 대상 4 | "다음 단계" 1~4번(STEP1.5/DEV-003을 미착수인 것처럼 서술) |
| 정정 내용 4 | 완료 이력으로 이동하거나 목록에서 제거 |
| 대상 5 | "보류/미착수" — "git 버전관리 도입 여부 (현재 파일명 접미사로 대체, DECISIONS.md ADR-008)" |
| 정정 내용 5 | 항목 자체를 "보류/미착수"에서 제거하고, "완료된 작업" 또는 별도 각주로 "git 커밋 기반 운영 확정(ADR-012, 2026-07-06부터 실제 운영 중)"으로 이동 |
| 근거 | `PROJECT_STATUS.md` §1/§2/§2-1(정정 후), `git log --reverse`, `SSOT_Document_Alignment_Plan_v1.0.md` §1-B/§1-C/§1-A |
| 영향도 | **보통** — 여러 절에 걸쳐 표기가 흩어져 있어 수정 지점이 5곳으로 많음. 다만 모두 상태 표기 변경(완료로 갱신)이라 구조 변경은 아님 |
| 검증 방법 | 정정 후 `ROADMAP.md`와 `PROJECT_STATUS.md`를 나란히 대조해 STEP1.5/DEV-003 상태 서술이 일치하는지 확인 |
| Rollback | `PROJECT_STATUS.md`와 동일(git revert/checkout) |

### 3. `ARCHITECTURE.md`

| 항목 | 내용 |
|---|---|
| 대상 | §3 기술 스택 표 — "버전 관리 \| 없음 (git 미사용, 파일명에 `_v2/_v3/_final/_new` 등 버전 접미사로 이력 관리)" |
| 정정 내용 | "버전 관리 \| Git 커밋 기반(ADR-012) + 파일명 접미사(`_new` 등, 상위 폴더 규칙 계승, 보조 수단) 병행" |
| 근거 | `git log`(32개 커밋, 최초 커밋 2026-07-06), `ADR-012_Git_Based_Version_Control.md` |
| 영향도 | **낮음** — 표 한 행만 수정, 문서의 다른 절(§1/§2/§7 등)에는 영향 없음 |
| 검증 방법 | §7(알려진 아키텍처 부채) 2번 항목 "버전 관리 부재: git 미사용..."도 함께 재검토 — 이 항목 역시 같은 오류를 담고 있으므로 동일 Commit에서 함께 정정하는 것을 권장(체크리스트 확장 항목으로 별도 표기) |
| Rollback | 동일(git revert/checkout) |

### 3-1. `ARCHITECTURE.md` §7 추가 확인 항목(정정 시 함께 처리 권장)

`ARCHITECTURE.md` §7 "알려진 아키텍처 부채" 2번 "버전 관리 부재: git 미사용, 파일명 접미사로 이력 관리 — 롤백/diff 추적 어려움"도 §3과 동일한 사실 오류를 포함한다. 이 항목은 §3 정정과 함께 "파일명 접미사와 git 병행 관리 — 두 체계가 공존해 어느 쪽이 최신 이력인지 확인하려면 양쪽을 모두 봐야 하는 부채는 남아있음"으로 정정하는 것을 제안한다(완전히 삭제하지 않는 이유: `기술부채 분석`에서 이미 이 병행 자체가 부채로 재확인됐기 때문 — `Platform_Integration_Architecture_Review_v1.0.md` §11-2).

### 4. `DECISIONS.md` (ADR 등재)

| 항목 | 내용 |
|---|---|
| 대상 | ADR-008 "상태: ✅ 확정" |
| 정정 내용 | "상태: ⚠️ Superseded by ADR-012 (2026-07-28)" + 배경 절에 "Sprint 4 Architecture Gate에서 실제 git 운영과의 불일치가 확인되어 대체됨" 각주 추가 |
| 대상 2 | ADR-012 정식 등재 — `ADR-012_Git_Based_Version_Control.md`(Commit 0에서 이미 초안 작성됨)의 내용을 `DECISIONS.md`에 신규 ADR 절로 추가 |
| 근거 | `ADR-012_Git_Based_Version_Control.md`(본 세션 Commit 0 산출물) |
| 영향도 | **낮음** — ADR-008을 삭제하지 않고 상태만 변경, ADR-012는 신규 절 추가이므로 기존 ADR 번호 체계에 영향 없음 |
| 검증 방법 | ADR 번호 중복 여부 확인(ADR-009~ADR-011이 이미 존재하므로 ADR-012가 다음 번호로 정확한지 재확인), Superseded 표기가 ADR-008 원문을 삭제하지 않고 보존하는지 확인 |
| Rollback | 동일(git revert/checkout). ADR-008 원문 자체는 삭제되지 않으므로 정보 손실 위험 없음 |

## 이 체크리스트의 실행 범위 밖

- 위 4개 문서 외의 다른 문서(`CLAUDE.md`, `README.md` 등)는 이번 체크리스트 대상이 아니다 — `SSOT_Document_Alignment_Plan_v1.0.md`에서 상충이 식별된 4개 문서로 범위를 한정한다.
- 이 체크리스트를 실제로 실행하는 것(파일 수정)은 **Sprint 4 Commit 1**에서 수행하며, 이번 Commit 0(문서 Baseline)에서는 실행하지 않았다.
