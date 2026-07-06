# 구조 재편 분석 보고서 — 현재 구조 vs 목표 구조(CSHSP)

**작성일**: 2026-07-04 (결론 갱신: 2026-07-04)
**성격**: 분석 전용 문서. **이 보고서 작성 과정에서 어떤 파일도 이동·삭제·이름변경하지 않았다.**
**대상**: `CMC_Platform_new`(현재 프로젝트 루트) → `CSHSP/`(목표 구조)

---

## 결론 (2026-07-04 확정)

- **Pilot 전 구조 재편은 보류한다.**
- **현재 구조는 v0.9.0-pilot 기준으로 유지한다.**
- **`src/` 및 `app/` 내부 재편은 v1.0 이후 별도 작업으로 검토한다.**
- **Pilot 전에는 STEP1.5 DateFix 해결을 최우선으로 한다.**

본 보고서에서 식별한 "저위험 이동 후보 15개 파일"(§4 그룹 A+B)은 실제로 이동하지 않으며, §9 "Pilot 이후 정리 대상"으로만 명시해 추적한다. 구조 재편은 Pilot 운영 이후, STEP1.5 DateFix 등 Known Issues(PROJECT_STATUS.md §2, ROADMAP.md "Sprint J 이전 필수 해결 과제") 해결이 우선된 다음에 재논의한다.

---

## 0. 목표 구조 (사용자 제공)

```
CSHSP/
├── CLAUDE.md  ├── START_HERE.md  ├── PROJECT_STATUS.md  ├── ARCHITECTURE.md
├── ROADMAP.md ├── DECISIONS.md   ├── README.md  ├── CHANGELOG.md
├── LICENSE    ├── .gitignore     ├── requirements.txt   ├── .env.example
├── app/  ├── admin/  ├── chat/  ├── src/  ├── data/  ├── docs/
├── prompts/ ├── skills/ ├── tests/ ├── scripts/ ├── config/
├── deployment/ ├── backups/ ├── logs/ ├── archive/ └── tools/
```

---

## 1. 현재 프로젝트 구조 분석

### 1-1. 루트 파일 (26개)

| 파일 | 목표 구조 항목 | 판정 |
|---|---|---|
| CLAUDE.md / ARCHITECTURE.md / ROADMAP.md / DECISIONS.md / PROJECT_STATUS.md | 동일명 | ✅ 일치 |
| README.md / CHANGELOG.md / LICENSE / .gitignore / requirements.txt / .env.example | 동일명 | ✅ 일치 |
| index.html | — | ⚠️ 목표 구조에 없는 항목(현재 앱 진입점) |
| RELEASE_NOTES_v0.9.0-pilot.md | — | ⚠️ 목표 구조에 없는 항목 |
| PILOT_READINESS_REVIEW.md | — | ⚠️ 목표 구조에 없는 항목 |
| DEV-003_..._Design_new.md / _v2_new.md / _Design_Final_new.md (3개) | — | ⚠️ 목표 구조에 없는 항목 |
| README_platform_new.md ~ _v5_new.md (5개, 구버전 README) | — | ⚠️ 목표 구조에 없는 항목 |
| STEP0-1_..._new.md / STEP1.5_..._new.md / STEP1.5.1_..._new.md (3개) | — | ⚠️ 목표 구조에 없는 항목 |

→ **루트에 있는 12개 md 파일이 목표 구조에 정의된 루트 파일 목록에 없다.** (README 5종, DEV-003 3종, STEP 3종, RELEASE_NOTES 1, PILOT_READINESS_REVIEW 1)

### 1-2. 루트 폴더 (9개) 대응 현황

| 현재 폴더 | 목표 구조 대응 | 판정 |
|---|---|---|
| app/, admin/, chat/, src/, data/, docs/, tests/ | 동일명 항목 존재 | ✅ 일치 (7개) |
| **(없음)** | prompts/, skills/, scripts/, config/, deployment/, backups/, logs/, archive/, tools/ | ❌ 미존재 (9개) |
| src/deploy/ (하위폴더) | deployment/ 후보 | ⚠️ 위치 다름 — 목표구조의 deployment/는 루트 최상위, 현재는 src/ 하위 |

**요약**: 목표 구조 27개 항목(파일 12 + 폴더 15) 중 **현재 정확히 일치하는 것은 18개(파일 12 + 폴더 6 — app/admin/chat/src/data/docs/tests, 정확히는 7개)**, **불일치/부재 9개 폴더**, **목표 구조에 없는 루트 파일 12개**가 남아있다.

---

## 2. 목표 구조 대비 차이점 분석

### 2-1. 완전 일치 (변경 불필요)

- 12개 표준 루트 문서 (CLAUDE.md ~ .env.example)
- app/, admin/, chat/, src/, data/, docs/, tests/ — 7개 폴더

### 2-2. 목표 구조에는 있으나 현재 없는 폴더 (9개) — 신설 여부 검토 필요

| 목표 폴더 | 현재 대응 콘텐츠 위치 | 이동/신설 판단 근거 |
|---|---|---|
| **deployment/** | `src/deploy/` (backup_policy.md, process_manager.md, production_checklist.md 3개 파일) | 실질적으로 이미 존재, 위치만 다름 → **이동 후보** |
| **backups/** | `tests/rehearsal_sandbox/backup/20260704/` (스냅샷 21개 JSON) | 테스트 리허설용 산출물이며 정기 백업 체계는 미구축 → **신설 필요, 내용물 이관 여부는 별도 판단** |
| **archive/** | 루트에 산재한 구버전 문서(README 5종·DEV-003 3종·STEP 3종) | 목표 구조상 명확한 수납처 → **이동 후보 1순위** |
| **logs/** | 없음 (테스트 결과 CSV가 tests/에 산재, 런타임 로그는 미확인) | 로그 파일 자체가 현재 생성되지 않음(또는 확인 불가) → **신설은 가능하나 이관할 기존 파일이 불명확** |
| **config/** | `.env.example`(루트), `app/config_v2_new.js`, `app/config_new.js` | 설정이 이미 두 성격(서버 환경변수 vs 프론트 JS 설정)으로 나뉘어 있어 단순 통합 시 참조 방식 자체를 바꿔야 함 → **신설 시 영향도 높음** |
| **scripts/** | 없음 (배포 자동화 스크립트 자체가 존재하지 않음, 문서만 존재) | 이동 대상 파일이 없음 → **신설(빈 폴더)만 가능, 내용은 신규 작성 필요** |
| **tools/** | 없음 | 이동 대상 파일이 없음 → **신설(빈 폴더)만 가능** |
| **prompts/** | 없음 (AI 프롬프트는 `src/agents/` 내부에 코드로 하드코딩되어 있고 별도 파일로 분리되어 있지 않음) | 이동 대상 파일이 없음 → **신설 시 기존 코드에서 문자열을 추출하는 별도 작업 필요(단순 이동 아님)** |
| **skills/** | 없음 | 이동 대상 파일이 없음 → **신설(빈 폴더)만 가능** |

**핵심 판단**: 9개 미존재 폴더 중 실제로 "파일 이동"으로 채울 수 있는 것은 **deployment/(3개 파일), archive/(12개 파일), backups/(선택적)** 뿐이다. 나머지 6개(prompts/skills/scripts/config/logs/tools)는 이동이 아니라 **신규 콘텐츠 작성이 필요한 빈 폴더**이며, 이번 요청 범위인 "파일 이동 분석"의 대상이 아니다.

### 2-3. 목표 구조에 없는 현재 항목

- 루트의 `index.html` — 목표 구조 명세에 없으나 현재 앱의 실제 진입점. 목표 구조가 이 파일의 존치를 전제하는지 불명확 (별도 확인 필요, 이번 분석에서는 판단 보류)
- `src/deploy/` 자체 폴더 (내용은 deployment/로 이동 후보, 빈 폴더는 삭제 대상이 될 수 있음)

---

## 3. 참조 경로 분석 (import / 경로 / 링크 / API / Apps Script / 테스트)

### 3-1. Python import 및 sys.path (위험도 최상)

- `src/` 전체에서 **약 177개 import 구문**, **23개 파일에서 sys.path.insert() 호출** 확인
- 각 파일이 프로젝트 루트를 계산하는 방식이 **파일마다 다름** (`parents[1]`, `parents[2]`, `Path(__file__).resolve().parent` 등 불일치)
- 대표 예시:
  - `src/core/core_data_loader.py:18` — `PROJECT_ROOT = Path(__file__).resolve().parents[2]`
  - `src/api/api_server.py:22-27` — `_ROOT` 계산 후 `src/core`, `src/reservation` 등 4개 경로를 sys.path에 개별 추가
  - `src/reservation/reservation_engine.py:21-23`, `src/agents/function_tools.py:18-20`, `src/dashboard/ai_metrics.py:16-19` 등 다수 파일에서 유사 패턴 반복
- **의미**: `src/` 내부 폴더(`core/`, `reservation/`, `api/`, `agents/` 등)의 **상대적 depth가 바뀌면 이 23곳의 sys.path 계산이 전부 깨진다.** 반면 `src/` 자체가 통째로 이동하고 내부 구조가 그대로 유지된다면(예: `CMC_Platform_new/src/` → `CSHSP/src/`) 영향은 없다.

### 3-2. 데이터 파일 접근 (위험도 낮음)

- `data/` JSON 파일 접근은 대부분 `json_store.py`의 `read_doc`/`write_doc` 추상화를 경유(약 258회 호출 지점)
- `CSHSP_DATA_DIR` 환경변수로 데이터 경로 오버라이드 가능
- **의미**: `data/` 폴더 위치가 바뀌어도 환경변수만 재설정하면 대응 가능 — 구조 변경에 상대적으로 안전

### 3-3. HTML 링크/스크립트 참조 (위험도 낮음)

- `app/`, `admin/`, `chat/` 전체에서 **약 63개**의 `href=`/`src=` 참조 확인, 전부 `../` 상대경로 사용
- `app/pages/*.html` → `../styles/`, `../services/`, `../config*.js`, `../components/`, `../data/` 패턴
- **의미**: `app/` 폴더 자체가 통째로 이동하지 않는 한(내부 상대 위치 유지) 안전. `app/` 내부 하위구조(pages/services/styles 등)의 상대 depth가 바뀌면 전부 깨짐.

### 3-4. JS fetch/API 경로 (위험도 낮음)

- `app/services/*.js`에서 **fetch() 약 11건** 확인 — 전부 Google Calendar/Sheets/Gmail 외부 API 호출이며 로컬 파일 경로 의존 없음
- **의미**: 프로젝트 내부 구조 변경과 무관

### 3-5. Apps Script (위험도 없음)

- `app/apps_script/sheets_api_v3_final.gs`는 Google 클라우드에서 독립 실행되며 로컬 파일시스템 경로에 의존하지 않음
- `app/config_v2_new.js`가 배포 URL(문자열)만 참조 — 프로젝트 구조 변경과 무관

### 3-6. 테스트 코드 참조 (위험도 중간)

- `tests/run_sprint_*.py` 각각이 `src/` 하위 모듈을 import하기 위해 자체 sys.path 설정을 가짐(§3-1과 동일 패턴 공유)
- 테스트용 데이터는 `tests/sandbox_sprint_*/data/`, `tests/rehearsal_sandbox/`로 분리되어 있고 `CSHSP_DATA_DIR` 오버라이드로 운영 데이터와 분리됨
- **의미**: `src/` 재구조화 시 테스트 스크립트도 §3-1과 동일하게 전부 영향받음. `tests/` 폴더 자체 위치 이동은 상대적으로 안전.

### 3-7. 문서 간 마크다운 링크 (위험도 높음, 국지적)

- SSOT 문서 5종 + README.md + RELEASE_NOTES + PILOT_READINESS_REVIEW + CHANGELOG 사이에 **약 38개**의 `[텍스트](파일명.md)` 상대링크 존재 (전부 같은 폴더 내 파일명만 사용, 경로 접두어 없음)
- 예: `README.md`가 8개 문서를, `PROJECT_STATUS.md`가 6개 문서를 링크
- **의미**: 이 9개 문서가 전부 같은 폴더(루트)에 있는 한 안전. 이 중 일부만 다른 폴더(예: archive/, docs/)로 옮기면 **링크가 전부 깨진다.**

---

## 4. 실제 이동이 필요한 파일 목록 (분석 결과, 미실행)

아래는 목표 구조 준수를 위해 "이동이 필요하다고 판단되는" 파일 목록이다. **실행하지 않았다.**

### 그룹 A — `deployment/` 신설 후 이동 (3개 파일)

| 현재 경로 | 이동 후보 경로 |
|---|---|
| `src/deploy/backup_policy.md` | `deployment/backup_policy.md` |
| `src/deploy/process_manager.md` | `deployment/process_manager.md` |
| `src/deploy/production_checklist.md` | `deployment/production_checklist.md` |

### 그룹 B — `archive/` 신설 후 이동 (12개 파일)

| 현재 경로 | 이동 후보 경로 |
|---|---|
| `README_platform_new.md` | `archive/README_platform_new.md` |
| `README_platform_v2_new.md` | `archive/README_platform_v2_new.md` |
| `README_platform_v3_new.md` | `archive/README_platform_v3_new.md` |
| `README_platform_v4_new.md` | `archive/README_platform_v4_new.md` |
| `README_platform_v5_new.md` | `archive/README_platform_v5_new.md` |
| `DEV-003_관리자예약관리_Sheets연동_Design_new.md` | `archive/DEV-003_..._Design_new.md` |
| `DEV-003_관리자예약관리_Sheets연동_Design_v2_new.md` | `archive/DEV-003_..._Design_v2_new.md` |
| `DEV-003_관리자예약관리_Sheets연동_Design_Final_new.md` | `archive/DEV-003_..._Design_Final_new.md` |
| `STEP0-1_예약쓰기검증_배포절차_new.md` | `archive/STEP0-1_..._new.md` |
| `STEP1.5_create_QA결과_new.md` | `archive/STEP1.5_..._new.md` |
| `STEP1.5.1_DateFix_QA_new.md` | `archive/STEP1.5.1_..._new.md` |
| (테스트 결과 CSV 9개, 선택적) | `archive/test_results/` 또는 `logs/` — 판단 보류 |

### 그룹 C — 위치 판단 보류 (이동 여부 자체가 불확실)

| 파일 | 사유 |
|---|---|
| `RELEASE_NOTES_v0.9.0-pilot.md` | 목표 구조에 명시된 위치 없음. 루트 유지 vs `docs/` 이동 여부는 사용자 판단 필요 |
| `PILOT_READINESS_REVIEW.md` | 위와 동일 |
| `index.html` | 목표 구조에 명시 없음. 앱 진입점이므로 삭제/이동 시 서비스 접근 경로 자체가 바뀜 — 신중한 판단 필요 |
| `tests/rehearsal_sandbox/`, `tests/sandbox_*/` | `backups/` 이동 vs `tests/` 잔류 vs `archive/` 이동, 세 후보 모두 가능 — 용도(현재 진행 중 테스트 자산인지 과거 산출물인지)에 대한 정책 결정 필요 |

**⚠️ 그룹 B의 이동은 §3-7에서 확인된 문서 간 링크와 직접 충돌하지 않는다** — README_platform_*, DEV-003_*, STEP*는 SSOT 5종/README.md/CHANGELOG 등 9개 핵심 문서의 상호링크 대상에 포함되어 있지 않기 때문(별도 조사 결과, 이 12개 파일을 가리키는 마크다운 링크는 발견되지 않음). 단, docs/ 내 Sprint 문서들이 이 파일들을 텍스트로 언급하는지는 이번 조사에서 전수 확인하지 못했으므로 실제 실행 전 재확인이 필요하다.

---

## 5. 이동 시 영향받는 파일 수 계산

| 이동 그룹 | 이동 대상 파일 수 | 직접 참조하는 파일 수(영향 범위) | 근거 |
|---|---|---|---|
| 그룹 A (deployment/) | 3개 | **0개 확인됨** (production_checklist.md 등은 다른 코드/문서에서 파일 경로로 직접 참조되지 않고, PROJECT_STATUS.md 등에서 `src/deploy/production_checklist.md` 텍스트로만 1회 언급됨) | §3-7 조사 기준 — SSOT 문서 내 텍스트 언급 1곳(PILOT_READINESS_REVIEW.md)은 경로 문자열 수정 필요 |
| 그룹 B (archive/) | 12개 | **0개 확인됨** (다른 파일에서 이 12개를 코드/링크로 참조하는 사례 미발견) | §3-7 마크다운 링크 38개 목록에 그룹 B 파일이 포함되지 않음 |
| 그룹 C (판단 보류) | 3개 + 폴더 다수 | RELEASE_NOTES/PILOT_READINESS_REVIEW는 SSOT 5종 중 **PROJECT_STATUS.md 1개 파일에서 3회 링크**됨 | §3-7 |
| `src/` 내부 재구조화(미요청, 참고용) | 해당 시 전체 | **약 200개 지점** (import 177 + sys.path 23) | §3-1 — 이번 이동 대상에는 포함되지 않았으나, 향후 `src/` 내부까지 재편할 경우 가장 큰 영향 |

**결론**: 이번에 식별된 이동 후보(그룹 A+B, 15개 파일)는 **직접 코드 참조가 없어 영향 파일 수가 0~1개로 매우 제한적**이다. 반면 판단 보류 항목(그룹 C) 중 RELEASE_NOTES/PILOT_READINESS_REVIEW를 옮기면 PROJECT_STATUS.md의 링크 3곳을 함께 수정해야 한다.

---

## 6. 위험도 평가

| 이동 후보 | 위험도 | 사유 |
|---|---|---|
| 그룹 A (deployment/ 3개) | 🟢 낮음 | 코드 참조 없음, 문서 내 텍스트 언급 1곳만 수정하면 됨 |
| 그룹 B (archive/ 12개) | 🟢 낮음 | 코드/문서 참조 미발견. 단, 사람이 과거 이력을 찾을 때 참조하던 "익숙한 루트 위치"가 바뀌는 운영상 불편은 있음 |
| 그룹 C (RELEASE_NOTES, PILOT_READINESS_REVIEW) | 🟡 중간 | PROJECT_STATUS.md 링크 수정 필요, 파일 수는 적지만 SSOT 문서 수정이 수반됨 |
| `index.html` 이동/삭제 | 🟡 중간 | 실제 서비스 진입점일 가능성 — 이동 시 북마크/배포 설정 등 외부 참조 파악이 우선되어야 함 |
| `tests/rehearsal_sandbox/`, `sandbox_*` 이동 | 🟡 중간 | 테스트 스크립트가 이 폴더들을 상대경로로 참조할 가능성이 있어(§3-6) 개별 확인 필요 |
| `src/deploy/` 폴더 자체 삭제(내용 이동 후) | 🟢 낮음 | 그룹 A 이동 후 빈 폴더만 남으면 삭제해도 무해 |
| `src/` 내부 하위폴더 재편(요청 범위 아님) | 🔴 높음 | sys.path 계산 로직 23곳, import 177곳 전부 재검증 필요 |
| `app/` 내부 하위폴더(pages/services/styles) 재편(요청 범위 아님) | 🔴 높음 | HTML 상대경로 63곳 전부 재검증 필요 |

**전체 위험도 종합**: 이번에 명확히 식별된 이동 후보(그룹 A, B)는 **낮음**. 목표 구조 전체를 완성하려면 결국 6개 빈 폴더(prompts/skills/scripts/config/logs/tools) 신설과 그룹 C 판단이 필요하며, 이 부분은 "이동"이 아니라 "신규 설계"에 가까워 위험도 평가 자체가 별도 검토 대상이다.

---

## 7. 자동 재구성 가능 여부 판단

| 구분 | 자동화 가능 여부 | 판단 근거 |
|---|---|---|
| 그룹 A 이동(3개) + 참조 1곳 수정 | ✅ **자동화 가능** | 대상 파일 수 적음, 참조 지점 명확히 특정됨(PILOT_READINESS_REVIEW.md 내 경로 문자열 1곳) |
| 그룹 B 이동(12개) | ✅ **자동화 가능** | 참조 없음이 확인되어 단순 파일 이동으로 충분 |
| 그룹 C(RELEASE_NOTES, PILOT_READINESS_REVIEW) 이동 | ⚠️ **조건부 자동화 가능** | 이동은 가능하나, 이동 전 "루트 유지 vs docs/ 이동" 정책을 사용자가 먼저 결정해야 함 — 기술적 문제가 아니라 정책 결정 문제 |
| index.html 처리 | ❌ **자동화 부적합** | 목표 구조에 명시가 없어 "어떻게 할지"가 기술이 아니라 요구사항 문제. 자동 판단 시 서비스 진입점을 잘못 건드릴 위험 |
| backups/, logs/, config/, scripts/, tools/, prompts/, skills/ 신설 | ❌ **자동화 부적합(콘텐츠 없음)** | 폴더 생성 자체는 자동화 가능하지만, 채워 넣을 내용이 이번 조사에서 식별되지 않음(신규 작성 필요) — 빈 폴더만 만드는 것은 목표 구조 달성에 실질적 의미가 적음 |
| `src/` 내부 재구조화 | ❌ **자동화 부적합** | 요청 범위 밖이며, 실행 시 23개 sys.path 지점 + 177개 import 지점의 수동 검증이 필요해 리스크가 큼 |

**종합 판단**: 목표 구조 27개 항목 중 **"파일 이동"만으로 안전하게 자동화할 수 있는 범위는 그룹 A(3개)+그룹 B(12개), 총 15개 파일**이다. 나머지는 (1) 사용자의 정책 결정이 선행되어야 하거나(그룹 C, index.html), (2) 이동이 아니라 신규 콘텐츠 작성이 필요하거나(prompts/skills/scripts/config/logs/tools), (3) 이번 요청 범위를 벗어난 대규모 내부 재구조화(src/, app/ 하위구조)에 해당한다.

---

## 8. 결론 요약

1. 목표 구조의 표준 루트 문서 12개는 이미 100% 일치한다.
2. 목표 구조의 폴더 15개 중 7개는 이미 존재, 8개는 미존재.
3. 미존재 8개 중 실질적으로 "이동"으로 채울 수 있는 것은 `deployment/`(3개 파일), `archive/`(12개 파일)뿐이며 나머지 6개는 콘텐츠 자체가 없어 신설해도 빈 폴더에 그친다.
4. 이동 후보 15개 파일의 참조 위험도는 낮음(직접 코드 참조 0건, 문서 참조 1건)으로 확인되어, **기술적으로는 자동 재구성이 가능**하다고 판단한다.
5. `src/`, `app/` 내부 하위구조까지 건드리는 재편은 각각 200개, 63개 참조 지점의 재검증이 필요해 고위험이며, 이번 목표 구조 비교에서는 해당 사항이 없다(목표 구조가 `src/`, `app/`을 통째로 하나의 폴더로만 명시하고 있어 내부 재편을 요구하지 않음).
6. **본 보고서 작성 중 실제 파일 이동·삭제·이름변경은 수행하지 않았다.**
7. **단, 상단 "결론"에 따라 기술적 가능 여부와 무관하게 Pilot 전 구조 재편은 수행하지 않기로 결정했다.** 이동 후보 15개 파일은 §9 "Pilot 이후 정리 대상"으로 이관하여 추적만 한다.

---

## 9. Pilot 이후 정리 대상 (실제 이동은 Pilot 이후로 보류)

아래 15개 파일은 §4~§6에서 저위험으로 평가된 이동 후보이나, **Pilot 이전에는 이동을 수행하지 않는다.** Pilot 운영 개시 이후, STEP1.5 DateFix 등 Known Issues 해결이 완료된 뒤 별도 작업으로 재검토한다.

### 9-1. `deployment/` 이관 대상 (3개)

| 현재 경로 | 이동 후보 경로 | 상태 |
|---|---|---|
| `src/deploy/backup_policy.md` | `deployment/backup_policy.md` | 🕓 Pilot 이후 정리 대상 |
| `src/deploy/process_manager.md` | `deployment/process_manager.md` | 🕓 Pilot 이후 정리 대상 |
| `src/deploy/production_checklist.md` | `deployment/production_checklist.md` | 🕓 Pilot 이후 정리 대상 |

### 9-2. `archive/` 이관 대상 (12개)

| 현재 경로 | 이동 후보 경로 | 상태 |
|---|---|---|
| `README_platform_new.md` | `archive/README_platform_new.md` | 🕓 Pilot 이후 정리 대상 |
| `README_platform_v2_new.md` | `archive/README_platform_v2_new.md` | 🕓 Pilot 이후 정리 대상 |
| `README_platform_v3_new.md` | `archive/README_platform_v3_new.md` | 🕓 Pilot 이후 정리 대상 |
| `README_platform_v4_new.md` | `archive/README_platform_v4_new.md` | 🕓 Pilot 이후 정리 대상 |
| `README_platform_v5_new.md` | `archive/README_platform_v5_new.md` | 🕓 Pilot 이후 정리 대상 |
| `DEV-003_관리자예약관리_Sheets연동_Design_new.md` | `archive/DEV-003_..._Design_new.md` | 🕓 Pilot 이후 정리 대상 |
| `DEV-003_관리자예약관리_Sheets연동_Design_v2_new.md` | `archive/DEV-003_..._Design_v2_new.md` | 🕓 Pilot 이후 정리 대상 |
| `DEV-003_관리자예약관리_Sheets연동_Design_Final_new.md` | `archive/DEV-003_..._Design_Final_new.md` | 🕓 Pilot 이후 정리 대상 |
| `STEP0-1_예약쓰기검증_배포절차_new.md` | `archive/STEP0-1_..._new.md` | 🕓 Pilot 이후 정리 대상 |
| `STEP1.5_create_QA결과_new.md` | `archive/STEP1.5_..._new.md` | 🕓 Pilot 이후 정리 대상 (단, DateFix 해결 확정 전까지는 원본 위치 보존 권장 — 참조 빈도가 높은 진행 중 이슈 문서이므로 §9-3 참조) |
| `STEP1.5.1_DateFix_QA_new.md` | `archive/STEP1.5.1_..._new.md` | 🕓 Pilot 이후 정리 대상 (위와 동일) |

### 9-3. 주의사항

- `STEP1.5_create_QA결과_new.md`, `STEP1.5.1_DateFix_QA_new.md`는 archive/ 이관 후보로 분류되어 있으나, STEP1.5 DateFix는 현재 미해결 Critical 이슈이므로(PROJECT_STATUS.md §2) **DateFix가 실제로 해결·재QA 통과되기 전까지는 이 2개 파일을 다른 문서보다 먼저 옮기지 않는다.** 작업 중인 이슈 문서를 아카이브로 옮기면 추적성이 떨어질 수 있다.
- 이 15개 파일에 대한 참조 위험도 평가(§5, §6)는 **현재 시점 기준**이며, Pilot 운영 기간 중 새로운 참조가 추가될 수 있으므로 실제 이동 시점에 재확인이 필요하다.
- 실제 이동은 Pilot 이후 사용자 승인을 받아 별도 작업으로 진행한다. 이 표는 추적용 목록이며 실행 지시가 아니다.
