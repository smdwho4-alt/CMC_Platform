# CSHSP 운영 FAQ

> 작성: Sprint7 Commit7-5(2026-07-29) — 신규 독립 문서.
> 대상: 신규 직원을 포함한 검진센터·전산 담당자. 질문·답변(Q&A) 형식.
> 확정되지 않은 내용은 **[확인 필요]** 또는 **[Decision Required]**로 표시한다 — 추측으로 답하지 않는다.

---

## A. 시스템 기본 구조

**Q1. "Google Sheets가 SSOT(Single Source of Truth)"라는 게 무슨 뜻인가요?**
A. 예약(Reservation) 데이터의 **공식 원장이 Google Sheets라는 뜻**입니다(ADR-013). `data/reservations.json`(로컬 파일)도 여전히 존재하지만, 신규 예약의 진짜 원본은 아니고 기존 기능 호환·테스트용 사본으로만 남아 있습니다. 예약이 실제로 어떻게 됐는지 확인하려면 Google Sheets를 봐야 합니다.

**Q2. Admin Portal, Reservation Portal, Legacy Portal은 각각 무엇인가요?**
A.
- **Admin Portal**(`admin_portal_new.html`): 현재 서비스 중인 관리자 화면. **예약 승인/거절**을 담당하며, 승인 시 정원(Slot)·정책(휴진일/의료진 등) 검증을 거칩니다.
- **Reservation Portal**(`reservation_v3_new.html`): 수검자가 예약을 신청하는 화면. Google Sheets에 직접 기록되며 Admin Portal의 승인 로직과는 별개 경로입니다.
- **Legacy Portal**(`admin_reservations_v2_new.html`): 예약 **변경·취소·검진완료** 처리를 담당하는 이전 세대 화면. "예약확정" 처리만 화면에서 막혀 있고, 나머지 3개 전이는 검증 없이 바로 처리됩니다.

**Q3. FastAPI와 GAS(Apps Script)는 각각 무슨 역할인가요?**
A. **FastAPI**(Backend)는 Admin Portal의 승인/거절 요청을 받아 정원·정책을 검증하고 결과를 Google Sheets에 반영합니다. **GAS(Apps Script)**는 Google Sheets에 실제로 접근하는 다리 역할입니다 — FastAPI도, Legacy Portal도, Reservation Portal도 결국 이 GAS를 통해 Sheets에 접근합니다.

**Q4. GAS 파일이 v3, v4 두 개 있다고 들었는데 어떤 걸 쓰나요?**
A. **현재 실제로 운영 배포된 파일은 `sheets_api_v3_final.gs`(v3)**입니다(`ARCHITECTURE.md`에서 "현재 배포본"으로 명시). `sheets_api_v4_deploy_new.gs`(v4)도 저장소에 있지만, 파일 자체 설명에 "핵심 로직은 v3와 동일"이라고 적혀 있고 실제로 배포에 쓰였는지는 **[확인 필요]**입니다. 확인 없이 임의로 v4로 바꾸지 않습니다.

---

## B. 예약 운영

**Q5. 예약신청이 들어왔는지 어떻게 확인하나요?**
A. Admin Portal의 "예약조회" 탭에서 상태가 "예약접수"인 건을 확인합니다. Legacy Portal에서도 같은 목록을 볼 수 있습니다.

**Q6. 승인·거절은 어느 화면에서 해야 하나요?**
A. **반드시 Admin Portal에서** 처리합니다. Admin Portal의 승인은 정원(Slot)과 운영 정책(휴진일/의료진/검사실/장비/프로그램 제한)을 자동으로 검증하지만, Legacy Portal에서 상태를 "예약확정"으로 직접 바꾸려 하면 화면에서 차단되고 Admin Portal 이용 안내가 표시됩니다.

**Q7. 승인 시 "정책 검증에 의해 확정할 수 없습니다"라는 메시지가 뜨면 어떻게 하나요?**
A. 오류가 아니라 **정상적인 차단**일 가능성이 높습니다. 휴진일, 담당 의료진 근무 여부, 검사실/장비 상태, 프로그램 제한 중 하나에 걸린 것입니다. 구체적인 사유는 현재 화면에 자세히 나오지 않으므로, 담당자가 해당 날짜의 근무표·휴진일을 직접 확인해야 합니다(상세: `docs/CSHSP_Failure_Response_Manual.md` §N).

**Q8. 정원이 꽉 찼거나(SLOT_FULL) Slot 충돌 메시지가 뜨면요?**
A. `docs/CSHSP_Failure_Response_Manual.md` §O를 참조합니다. 특히 "동일 예약번호가 이미 다른 곳에 점유돼 있다"는 메시지(`SLOT_RESERVATION_CONFLICT`)는 **자동으로 정정되지 않으므로** 전산 담당에게 데이터 확인을 요청해야 합니다.

**Q9. 예약을 취소했는데 정원이 그대로예요. 오류인가요?**
A. **오류가 아니라 현재 시스템의 알려진 제한사항입니다.** 예약취소는 Legacy Portal에서 처리되는데, 이 처리는 Slot(정원) 데이터를 자동으로 되돌리지 않습니다. 취소 건이 발생하면 전산 담당에게 알려 수동으로 정원 데이터를 확인·수정해야 합니다(상세: `docs/CSHSP_Rollback_Guide.md` §15).

**Q10. "예약변경(일정변경)"으로 처리하면 실제로 날짜가 바뀌나요?**
A. **아니요, 현재는 바뀌지 않습니다.** "일정변경"을 선택해 저장해도 상태 라벨만 바뀔 뿐, 희망 검진일시 자체는 그대로입니다. 실제 날짜를 바꾸려면 별도 방법(현재 Legacy Portal 화면에는 날짜 수정 입력란이 없음)이 필요하며, 이는 향후 개선 대상으로 등록되어 있습니다(`Legacy_Stage3_PhaseB_Design_v1.0.md`).

---

## C. 장애 대응

이 항목들은 요약이며, 상세 절차는 `docs/CSHSP_Failure_Response_Manual.md`와 `docs/CSHSP_Rollback_Guide.md`를 참조합니다.

**Q11. Admin Portal에 접속이 안 돼요.**
A. 정적 서버 상태 확인이 우선입니다(`CSHSP_Failure_Response_Manual.md` §H, `CSHSP_Rollback_Guide.md` §11).

**Q12. Admin Portal은 뜨는데 승인 버튼을 누르면 응답이 없거나 "시간 초과" 메시지가 떠요.**
A. FastAPI 서버 상태 문제일 가능성이 높습니다(§I, Rollback Guide §9). 8초가 지나면 자동으로 "요청 시간이 초과되었습니다" 메시지가 뜨도록 되어 있습니다 — 이는 정상적인 Timeout 동작입니다.

**Q13. Google Sheets 조회나 저장이 안 돼요.**
A. §J(조회)/§K(저장) 참조. FastAPI Health Check로 Sheets 연동 상태를 먼저 확인합니다.

**Q14. GAS(Apps Script) 자체에 문제가 있는 것 같아요.**
A. §L 참조. Google 계정 인증이 필요한 작업이라 아무나 GAS를 재배포할 수 없습니다 — 담당자를 확인합니다.

**Q15. Legacy Portal에서 상태 변경이 이상하게 처리됐어요.**
A. §P 참조. Legacy Portal의 변경/취소/완료는 **감사 로그가 남지 않으므로** Sheets를 직접 열어 확인해야 합니다.

**Q16. 정원(Slot) 숫자와 실제 예약 건수가 안 맞는 것 같아요.**
A. §U(데이터 정합성 이상) 및 `CSHSP_Rollback_Guide.md` §16 참조. 전산 담당에게 즉시 알립니다 — 정원 초과가 실제로 확인되면 P1(즉시 보고) 대상입니다.

**Q17. Netlify에 배포한 사이트가 안 열려요.**
A. §T 참조. Netlify 대시보드에서 이전 배포로 되돌리는 방법이 가장 빠릅니다(`CSHSP_Rollback_Guide.md` §7).

---

## D. 배포 및 Rollback

**Q18. 배포하기 전에 무엇을 확인해야 하나요?**
A. `src/deploy/production_checklist.md`의 ①~⑨ 전체를 확인합니다. 특히 **PM의 명시적 승인 없이는 Push/Deploy를 하지 않습니다.**

**Q19. 배포했는데 문제가 생기면 가장 먼저 뭘 해야 하나요?**
A. `docs/CSHSP_Failure_Response_Manual.md`에서 증상에 맞는 항목을 찾아 1차 대응을 시도합니다. 그래도 해결되지 않으면 `docs/CSHSP_Rollback_Guide.md`의 해당 절차로 이동합니다.

**Q20. 언제 이전 Netlify 배포로 되돌려야 하나요?**
A. 배포 직후 사이트 접속 자체가 안 되거나 화면이 깨지는 등 **정적 파일 자체의 문제**로 판단될 때입니다(`CSHSP_Rollback_Guide.md` §7). Backend(FastAPI)나 Sheets 문제는 Netlify Rollback으로 해결되지 않습니다.

**Q21. GAS 이전 버전으로 되돌릴 때 주의할 점은요?**
A. Google 계정 인증이 필요하고, 되돌린 뒤에도 반드시 **"새 버전"으로 재배포**해야 합니다(기존 버전 재사용 시 과거 실제로 배포 미반영 사고가 있었습니다). 정확한 화면 조작 절차는 **[확인 필요]** — Apps Script UI를 직접 보고 진행해야 합니다(`CSHSP_Rollback_Guide.md` §8).

**Q22. Rollback이 끝났는지 어떻게 확인하나요?**
A. `CSHSP_Rollback_Guide.md` §17에 나열된 회귀 테스트가 전부 통과해야 합니다. 통과하지 않으면 아직 완료된 것이 아닙니다.

**Q23. 운영을 다시 시작해도 된다는 결정은 누가 하나요?**
A. **[Decision Required]** — 이 문서 작성 시점에는 실제 승인권자가 지정되어 있지 않습니다. 제안 기준은 `CSHSP_Rollback_Guide.md` §18을 참조하되, 최종적으로는 **PM 확인 후 운영 재개를 공지**하는 것을 원칙으로 합니다.

---

## E. 보안 및 개인정보

**Q24. GitHub(저장소)에 절대 올리면 안 되는 것은 무엇인가요?**
A. 실제 예약자 정보(이름/연락처/생년월일/검진결과/사업장), 운영 계정 정보, 비밀번호, Token, API Key, **실제 GAS Web App URL**, **실제 Google Sheets ID**, 운영 Secret 전부입니다. 환경변수 **이름**(예: `CSHSP_GAS_WEBAPP_URL`)은 문서에 적어도 되지만 **실제 값**은 절대 적지 않습니다.

**Q25. Sheet ID, GAS URL 등은 어디에 보관하나요?**
A. 서버 환경변수로만 관리합니다(`src/deploy/process_manager.md` 참조). 문서·커밋 메시지·채팅 어디에도 원문을 남기지 않습니다.

**Q26. 개인정보가 포함된 파일을 백업할 때 주의할 점은요?**
A. 백업 드라이브는 암호화하고 접근 권한을 검진센터 담당자로 제한합니다. 외부 반출·클라우드 업로드는 금지되며, **어떤 경우에도 Git 저장소에는 커밋하지 않습니다**(`src/deploy/backup_policy.md` §2).

**Q27. 관리자 로그인은 실제 인증인가요?**
A. **아니요, 현재는 Mock(가짜) 인증입니다.** `X-User-Id`라는 값만 입력하면 되고, 비밀번호 등 실제 인증 절차가 없습니다. 이 때문에 내부망 안에서만 사용해야 하며, 외부에 노출되면 안 됩니다. 실제 로그인 구현은 아직 **[Not Implemented]** 상태입니다.

**Q28. Legacy Portal을 직접 호출하면 위험하다는 게 무슨 뜻인가요?**
A. Legacy Portal이 사용하는 GAS(Google Apps Script)는 **호출자가 누구인지 확인하지 않습니다.** 즉 Web App 주소만 알면 화면을 거치지 않고도 누구나 예약 데이터를 조회·수정할 수 있습니다. "예약확정 차단"도 화면(브라우저)에만 있는 장치이지, GAS 자체를 막는 것이 아니라서 이 방식으로 우회될 수 있습니다. 이 때문에 GAS Web App URL을 외부에 노출하지 않는 것이 매우 중요합니다.

---

## F. 백업 및 기록

**Q29. Google Sheets 백업 시 무엇을 확인해야 하나요?**
A. Google Sheets 자체의 "버전 기록" 기능이 최소한의 안전망입니다. 다만 보존 기간, 복구 성공 기준, 담당자는 아직 **[Decision Required]**로 남아 있습니다(`src/deploy/backup_policy.md` §5-2). 대규모 변경 전에는 시트를 수동으로 "사본 만들기" 해두는 것을 권장합니다.

**Q30. 장애가 발생하면 무엇을 기록해야 하나요?**
A. 발생 시각, 발견자, 증상, 영향 범위, 조치 내용, 복구 시각을 기록합니다. 양식은 `docs/CSHSP_Rollback_Guide.md` §20을 사용합니다.

**Q31. 운영일지나 완료보고는 어떤 기준으로 쓰나요?**
A. 배포 완료 보고는 `docs/DEPLOY_GUIDE_new.md` §9 양식을, Rollback 완료 보고는 `docs/CSHSP_Rollback_Guide.md` §21 양식을 사용합니다.

**Q32. 아직 정해지지 않은 것들은 무엇인가요?**
A. 대표적으로: 백업/복구 책임자, Sheets 백업 보존 기간, 복구 성공 판정 기준, 운영 연락망(담당자 이름·연락처), Rollback 운영 재개 승인 최종 절차 — 전부 **[Decision Required]**입니다. 확정되기 전까지는 PM에게 확인 후 진행합니다.

---

## G. 지원 요청 및 보고

**Q33. 직원이 스스로 처리해도 되는 범위는 어디까지인가요?**
A. Admin Portal에서의 정상적인 승인/거절, Legacy Portal에서의 정상적인 예약변경/취소/검진완료 처리(단, §B의 제한사항 인지 필요), 조회·CSV 다운로드, `CSHSP_Failure_Response_Manual.md`에 명시된 1차 대응(서비스 재시작 등)까지입니다.

**Q34. 언제 즉시 상급자나 PM에게 보고해야 하나요?**
A. `CSHSP_Failure_Response_Manual.md` §2의 **P1(즉시)** 기준 — 개인정보 노출 의심, AI 임의 확정, 데이터 복구 실패, **정원 초과 예약이 실제로 확인된 경우**(§16 데이터 정합성)입니다.

**Q35. 언제 개발자(전산) 확인이 필요한가요?**
A. GAS 재배포가 필요한 경우, Rollback 절차 수행이 필요한 경우, Sheets-Slot 데이터 정합성이 맞지 않는 경우, 원인을 알 수 없는 반복 오류가 발생하는 경우입니다.

**Q36. 서비스를 중단하거나 제한해야 하는 상황은 언제인가요?**
A. 정원 초과 예약처럼 데이터 신뢰도에 문제가 생겼을 때(§16), 또는 AI 이상 응답·개인정보 노출처럼 즉시 채팅을 차단해야 하는 상황입니다(`CSHSP_Failure_Response_Manual.md` §D). **[Not Implemented]** 원격으로 특정 기능만 끄는 도구는 현재 없어, 제한이 필요하면 운영적 조치(담당자가 사용 중단을 안내)로 대응합니다.

---

## 완료 조건 준수 확인

이 문서 작성 중 어떤 코드·설정·운영 데이터도 변경하지 않았다. 모든 답변은 실제 코드/문서로 확인된 사실에 근거했으며, 확정되지 않은 내용은 [확인 필요] 또는 [Decision Required]로 표시했다.
