# Commit8-3b 격리 GAS 교차검증 — 실행 로그

## 계정 확인
- `clasp show-authorized-user` 결과: `smdwho4@gmail.com`으로 로그인됨(사용자 지정 계정과 일치, 토큰 원문 미출력, 기존 로그인 캐시 삭제하지 않음).
- clasp 미설치 상태였으므로 `npm install -g @google/clasp`(v3.4.1)로 설치함.

## 프로젝트 생성
- 명령: `clasp create --type standalone --title "CMC_HMAC_V2_ISOLATED_TEST"`
- 시각: 2026-10-03 (한국시간, 터미널 로컬시간 기준)
- 결과: 신규 생성됨
  - 프로젝트명: `CMC_HMAC_V2_ISOLATED_TEST`
  - Script ID: `1f8e3qCgMfd7vR5cq81Bqir_6RNf8Ux8pjTrD5-EhalIibO2OUCKXMXeD`
  - 편집기 URL: https://script.google.com/d/1f8e3qCgMfd7vR5cq81Bqir_6RNf8Ux8pjTrD5-EhalIibO2OUCKXMXeD/edit
  - `clasp clone`을 사용하지 않았고(`clasp create`만 사용), 기존 프로젝트를 연결·수정하지 않음(신규 scriptId 발급 확인).
- `clasp create`가 로컬 `appsscript.json`을 Google 기본 매니페스트(timeZone America/New_York, oauthScopes 미선언)로 덮어썼음 — 계획했던 매니페스트(Asia/Seoul, V8, `oauthScopes: []`)로 즉시 복원한 뒤 push함.

## 업로드
- 명령: `clasp push --force`(기존 push가 "매니페스트가 변경됨" 확인 프롬프트를 띄우는데, 비대화형 셸이라 `--force`로 그 확인만 생략함 — 업로드 대상 파일 자체는 변경하지 않음)
- 결과: 5개 파일 업로드 성공 — `appsscript.json`, `Code.gs`, `Expected.gs`, `Fixtures.gs`, `Main.gs`(README.md는 clasp가 인식하는 확장자(.gs/.js/.json/.html)가 아니라 자동 제외됨, 의도된 동작).

## runAllVectors 실행 시도
- 명령: `clasp run runAllVectors`
- 시각: 2026-10-03 13:19:08 KST
- **결과: 실패**
  ```
  Exception: We're sorry, a server error occurred while reading from storage. Error code NOT_FOUND. []
  ```
- OAuth 동의 화면이나 추가 scope 요청 프롬프트는 **나타나지 않았다** — 이 오류는 scope/권한 문제가 아니라 Google Apps Script 실행 API(`clasp run`이 내부적으로 쓰는 `scripts.run`)가 신규 생성 직후의 standalone 프로젝트를 아직 찾지 못하는 것으로 보인다(흔히 보고되는 원인: 사용자 Google 계정 설정의 "Google Apps Script API" 토글이 꺼져 있거나, 신규 프로젝트의 실행 API 연동 전파 지연).
- **지시에 따라 자동으로 설정을 변경하거나 재시도하지 않고 여기서 중단**했다.

## runAllVectors 수동 실행(사용자 직접, 편집기)
- 사용자가 Apps Script 편집기에서 `runAllVectors`를 직접 실행.
- 실행 시각(사용자 보고): 2026-10-03 13:31:28 KST
- 결과(사용자 요약 전달): 서명·해시 비교 12/12 PASS, 입력 거절 9/9 PASS, 필드 거절 V07 1/1 PASS, 전체 22/22 PASS, FAIL 0.
- Sheets/Drive 등 계획 밖 권한 요청이 있었다는 보고 없음.
- 전체 원문 로그(시작 줄·벡터별 22줄·완료 줄)는 이 시점까지 미확보 — 요약만 전달받음.

## Expected.gs V02 라벨 오류 발견 및 실행본 복구(이번 갱신)
- 실행(13:31:28 KST) 이후, `Expected.gs`의 `EXPECTED_REJECT.V02_korean_unicode_payload.verificationBasis`가
  `"INDEPENDENT_OPENSSL"`로 **잘못 표기**되어 있었음을 발견(거절
  판정은 openssl로 독립 검증할 수 없는 제어흐름이므로
  `"PYTHON_COMPARISON_ONLY"`가 맞음).
- **실행 당시 코드는 아직 재push하지 않았으므로**, 별도 디렉터리에서
  `clasp pull`(읽기 전용 다운로드, GAS 재실행 아님)로 실행 당시
  그대로의 5개 파일을 복구함:
  ```
  clasp pull (별도 작업 디렉터리, scriptId만 지정)
  → appsscript.json, Code.js, Fixtures.js, Expected.js, Main.js 복구
  ```
- 복구본 SHA-256을 로컬 현재본과 비교한 결과, `appsscript.json`/
  `Code.gs`/`Fixtures.gs`/`Main.gs` 4개는 **해시 완전 일치**(수정한
  적 없으므로 당연한 결과, 교차 확인됨). `Expected.gs`만 해시가
  다름(실행본 `bcb4b11d...` vs 정정본 `f7bb2baa...`) — 이것이 바로
  라벨 수정의 증거.
- 복구된 실행본을 `Expected_AS_EXECUTED_20261003.gs`로 저장(바이트
  단위로 수정하지 않고 그대로 보존), 임시 작업 디렉터리는 삭제.
- `diff`로 변경 범위 확인: 상단 주석 보강 + `verificationBasis` 값
  1개뿐, 그 외 모든 해시값·reason 코드·로직은 동일 — **라벨·근거
  메타데이터뿐임을 확인**, GAS 재실행 없이 정적 수정만 수행.

## 다음 결정이 필요한 사항
1. 전체 실행 로그(원문 22줄 포함)를 사용자에게 재요청 중 — 받는 즉시 보존 파일 추가·보고서 정정.
2. 이 패키지·보고서를 실제로 저장소에 commit할지, 어느 경로에 둘지 승인 필요(결과보고서 §8 제안 참조).
3. (참고, 해결되지 않음) `clasp run` 원격 실행이 `Error code NOT_FOUND`로 실패했던 원인 — 편집기 수동 실행으로 우회해 결과를 얻었으므로 더 조사하지 않았음.
