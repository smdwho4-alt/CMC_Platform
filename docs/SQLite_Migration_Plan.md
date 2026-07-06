# CSHSP JSON → SQLite 이관 검토 (Sprint H)

## 1. 결론 (권고)

**파일럿(동시 사용자 ~10명, 일 예약 ~100건)은 현행 JSON + DataLock으로 충분하다.**
이관 트리거: ① 다중 프로세스/서버 확장 ② 예약 누적 1만건 이상(파일 로드 지연)
③ 동시 쓰기 충돌 관찰 ④ 통계 질의 복잡화. 트리거 발생 시 SQLite로 이관하고,
그 다음 단계(다지점·고동시성)에서 PostgreSQL을 검토한다.

## 2. 현행 구조가 이관에 유리한 이유

- 모든 읽기가 `core_data_loader.load_entity(entity)` 한 곳, 모든 쓰기가
  `json_store.read_doc/write_doc` + `DataLock` 경유 → **교체 지점이 2개 모듈로 수렴**
- Entity 스키마·필수 필드가 `data_validator.REQUIRED_FIELDS`에 이미 정의됨
- id 체계(PT-/RSV-/SLOT- 접두어)가 그대로 PK로 사용 가능

## 3. 매핑 설계

| JSON | SQLite |
|------|--------|
| 파일 1개(엔벨로프+records) | 테이블 1개 (20개 Entity → 20 테이블) |
| 레코드 공통 id/status/createdAt/updatedAt | 컬럼 + PK(id) + 인덱스(status, 날짜) |
| 중첩 필드(changeHistory, items, kpi 등) | TEXT 컬럼에 JSON 직렬화 (SQLite JSON1 함수로 질의 가능) |
| meta(containsPII 등) | `entity_meta` 테이블 1개 |
| DataLock 파일 잠금 | SQLite 자체 잠금 (WAL 모드) — DataLock 제거 가능 |

## 4. 이관 단계 (예상 1~2일)

1. `src/database/sqlite_store.py` 작성 — json_store와 동일 시그니처
   (`read_doc(entity)`/`write_doc(entity, doc)`)의 어댑터 → 엔진·API 코드 무수정 목표
2. 마이그레이션 스크립트: data/*.json → cshsp.db 적재 + 건수 대조 + validator 통과 확인
3. `core_data_loader`에 백엔드 스위치 (env `CSHSP_STORAGE=json|sqlite`)
4. 테스트 스위트 전체를 sqlite 모드로 재실행 (B/D/E/F/G/H)
5. 병행 운전 1주 (일일 JSON 스냅샷과 대조) 후 전환

## 5. 리스크

| 리스크 | 대응 |
|--------|------|
| 중첩 JSON 질의 성능 | 자주 조회하는 필드(상태·날짜·patientId)만 컬럼 승격 |
| 파일 직접 열람 편의성 상실 (직원이 JSON을 열어보던 습관) | admin 콘솔/CSV 내보내기로 대체 |
| 백업 방식 변경 | 파일 1개(cshsp.db) 복사 + `VACUUM INTO` — 오히려 단순해짐 |
| Windows 파일 잠금과 WAL 충돌 | WAL 모드 + 단일 서버 전제 유지 |

## 6. 판단 기준 요약

파일럿 중 아래 중 하나라도 관측되면 이관 착수:
- reservations.json > 5MB 또는 API 응답 > 500ms
- `.cshsp.lock` 대기로 인한 타임아웃 로그
- 월간 통계 산출에 수동 스크립트가 반복적으로 필요
