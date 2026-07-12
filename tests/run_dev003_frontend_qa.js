/**
 * DEV-003 — 프런트엔드(admin_reservations_v2_new.html) AA 컨트롤러 단위 테스트 (Node, vm 모의 실행)
 *
 * HTML 파일의 마지막 인라인 <script> 블록(AA 컨트롤러)을 실제로 로드해 실행한다.
 * DOM은 getElementById 기반 최소 스텁으로 대체하고, CMC_SheetsServiceV2는
 * 시나리오별로 제어 가능한 목(mock)으로 주입한다.
 *
 * 실행: node tests/run_dev003_frontend_qa.js
 * 종료 코드: 0(전체 통과) / 1(실패 있음)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML_FILE = path.join(__dirname, '..', 'app', 'pages', 'admin_reservations_v2_new.html');
const CMC_CORE_FILE = path.join(__dirname, '..', 'app', 'data', 'programs_data_new.js');
const RESULT_CSV = path.join(__dirname, 'dev003_frontend_qa_result.csv');

function extractInlineScript(html) {
  const matches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  if (!matches.length) throw new Error('인라인 <script> 블록을 찾지 못함 (AA 컨트롤러)');
  return matches[matches.length - 1][1];
}

/* ── 최소 DOM 스텁 ─────────────────────────────────────────── */
function makeFakeDom() {
  const ids = [
    'clock','searchInput','fStatus','fProg','fDateFrom','fDateTo','mainTable','pagination',
    'mNo','mStatus','dName','dBirth','dPhone','dGender','dProg','dDate','dSleep','dCompany',
    'dTests','dNote','dCreated','dUpdated','statusSel','detailModal','cmc-toast','modeBadge',
    'st-total','st-접수','st-확정','st-완료','st-취소변경',
  ];
  const store = {};
  ids.forEach(id => { store[id] = { value: '', textContent: '', className: '', innerHTML: '', style: {}, addEventListener() {}, _t: null }; });
  const document = {
    getElementById: (id) => store[id],
    addEventListener: () => {},
  };
  return { document, store };
}

function loadAaSandbox({ isGoogle = false } = {}) {
  const html = fs.readFileSync(HTML_FILE, 'utf8');
  const script = extractInlineScript(html);
  const cmcCoreSrc = fs.readFileSync(CMC_CORE_FILE, 'utf8');

  const { document, store } = makeFakeDom();
  const calls = { updateStatus: [], update: [], getOne: [] };
  const order = [];

  let sandboxRef; // set below, after `sandbox` exists — closed over by getAllImpl
  const sheetsServiceMock = {
    getAllImpl: async () => {
      const cache = (sandboxRef && sandboxRef.AA) ? sandboxRef.AA.cache : [];
      return { ok: true, data: cache, source: 'mock', count: cache.length };
    },
    getOneImpl: async (no) => ({ ok: false, error: 'not found' }),
    updateStatusImpl: async (no, status) => ({ ok: true, data: { reservationNo: no, status } }),
    updateImpl: async (no, patch) => ({ ok: true, data: { reservationNo: no } }),
    async getAll(params) { return this.getAllImpl(params); },
    async getOne(no) { calls.getOne.push(no); return this.getOneImpl(no); },
    async updateStatus(no, status, confirmedAt) { order.push('updateStatus'); calls.updateStatus.push([no, status, confirmedAt]); return this.updateStatusImpl(no, status, confirmedAt); },
    async update(no, patch) { order.push('update'); calls.update.push([no, patch]); return this.updateImpl(no, patch); },
  };

  const sandbox = {
    console,
    document,
    setInterval: () => 0,
    clearTimeout: () => {},
    setTimeout: (fn) => fn(), // toast 타이머 즉시 실행(테스트 단순화)
    CMC_CONFIG: { isGoogle: () => isGoogle, isLocal: () => !isGoogle },
    CMC_SheetsServiceV2: sheetsServiceMock,
    CMC_DB: { getAll: () => [], initSampleIfEmpty() {} },
    CMC_Stats: { statusCounts: () => ({}) },
    CMC_Nav: { render() {} },
  };
  sandbox.sheetsServiceMock = sheetsServiceMock; // 테스트 편의용 참조(vm 실행 스크립트는 참조하지 않음)
  vm.createContext(sandbox);
  vm.runInContext(cmcCoreSrc, sandbox, { filename: CMC_CORE_FILE }); // 실제 CMC 네임스페이스 로드
  vm.runInContext(script, sandbox, { filename: HTML_FILE });
  sandbox.AA = vm.runInContext('AA', sandbox);
  sandboxRef = sandbox;
  return { sandbox, store, calls, order, sheetsServiceMock };
}

const results = [];
function check(name, condition, detail) {
  results.push({ name, pass: !!condition, detail: detail || '' });
  console.log(`${condition ? '✅ PASS' : '❌ FAIL'} — ${name}${detail ? ' — ' + detail : ''}`);
}

async function run() {
  /* ── 0) renderModeBadge: Google/Local 모드에 따라 배지 텍스트가 정확히 표시됨 ── */
  {
    const { sandbox, store } = loadAaSandbox({ isGoogle: true });
    sandbox.AA.renderModeBadge();
    check('renderModeBadge: GOOGLE 모드일 때 "Sheets Live" 표시', store.modeBadge.textContent.includes('Sheets Live'), store.modeBadge.textContent);
  }
  {
    const { sandbox, store } = loadAaSandbox({ isGoogle: false });
    sandbox.AA.renderModeBadge();
    check('renderModeBadge: LOCAL 모드일 때 "Local Mode" 표시', store.modeBadge.textContent.includes('Local Mode'), store.modeBadge.textContent);
  }

  /* ── 1) optionalTests 정규화: 배열/문자열 모두 처리 ── */
  {
    const { sandbox } = loadAaSandbox();
    check('_optionalTestsArray: 배열 입력 → 그대로', JSON.stringify(sandbox.AA._optionalTestsArray(['위내시경','대장내시경'])) === JSON.stringify(['위내시경','대장내시경']));
    check('_optionalTestsArray: 콤마 문자열 입력(Sheets) → 배열로 분해', JSON.stringify(sandbox.AA._optionalTestsArray('위내시경, 대장내시경')) === JSON.stringify(['위내시경','대장내시경']));
    check('_optionalTestsArray: 빈 값 → 빈 배열', JSON.stringify(sandbox.AA._optionalTestsArray('')) === '[]');
    check('_optionalTestsArray: undefined → 빈 배열', JSON.stringify(sandbox.AA._optionalTestsArray(undefined)) === '[]');
  }

  /* ── 2) _buildNotePayload: note 단일 필드만 포함(Risk#2 방어) ── */
  {
    const { sandbox } = loadAaSandbox();
    const payload = sandbox.AA._buildNotePayload('메모내용');
    check('_buildNotePayload: note 필드만 존재', JSON.stringify(Object.keys(payload)) === JSON.stringify(['note']), JSON.stringify(payload));
    check('_buildNotePayload: 값 정확', payload.note === '메모내용');
  }

  /* ── 3) saveStatus: 상태+메모 동시 변경 → 순차 호출, note payload는 {note}만 ── */
  {
    const { sandbox, calls, order } = loadAaSandbox();
    sandbox.AA.cache = [{ reservationNo: '20260810-0001', status: '예약접수', note: '기존메모' }];
    sandbox.AA.selectedNo = '20260810-0001';
    sandbox.document.getElementById('statusSel').value = '예약확정';
    sandbox.document.getElementById('dNote').value = '새메모';
    await sandbox.AA.saveStatus();

    check('saveStatus: updateStatus가 정확한 인자로 호출됨', calls.updateStatus.length === 1 && calls.updateStatus[0][0] === '20260810-0001' && calls.updateStatus[0][1] === '예약확정', JSON.stringify(calls.updateStatus));
    check('saveStatus: update(note)가 {note} 단일 필드로만 호출됨', calls.update.length === 1 && JSON.stringify(Object.keys(calls.update[0][1])) === JSON.stringify(['note']) && calls.update[0][1].note === '새메모', JSON.stringify(calls.update));
    check('saveStatus: updateStatus가 update보다 먼저 호출됨(순차)', order[0] === 'updateStatus' && order[1] === 'update', JSON.stringify(order));
    check('saveStatus: 성공 시 모달 닫힘(selectedNo 초기화)', sandbox.AA.selectedNo === null);
  }

  /* ── 4) saveStatus: 상태변경 실패 → 롤백, 메모는 독립적으로 계속 시도됨 ── */
  {
    const { sandbox, calls } = loadAaSandbox();
    sandbox.sheetsServiceMock.updateStatusImpl = async () => ({ ok: false, error: '서버 오류' });
    sandbox.AA.cache = [{ reservationNo: '20260810-0002', status: '예약접수', note: '기존메모' }];
    sandbox.AA.selectedNo = '20260810-0002';
    sandbox.document.getElementById('statusSel').value = '예약확정';
    sandbox.document.getElementById('dNote').value = '새메모2';
    await sandbox.AA.saveStatus();

    const cached = sandbox.AA.cache.find(r => r.reservationNo === '20260810-0002');
    check('saveStatus: 상태변경 실패 시 상태 롤백됨', cached.status === '예약접수', cached.status);
    check('saveStatus: 상태변경 실패해도 메모 저장은 시도됨(독립적)', calls.update.length === 1, JSON.stringify(calls.update));
    check('saveStatus: 메모는 성공했으므로 반영됨', cached.note === '새메모2', cached.note);
    check('saveStatus: 부분 실패 시 모달 유지(selectedNo 비초기화)', sandbox.AA.selectedNo === '20260810-0002');
  }

  /* ── 5) saveStatus: 메모저장 실패 → 메모만 롤백, 상태는 반영 유지 ── */
  {
    const { sandbox, calls } = loadAaSandbox();
    sandbox.sheetsServiceMock.updateImpl = async () => ({ ok: false, error: '메모 저장 오류' });
    sandbox.AA.cache = [{ reservationNo: '20260810-0003', status: '예약접수', note: '기존메모' }];
    sandbox.AA.selectedNo = '20260810-0003';
    sandbox.document.getElementById('statusSel').value = '예약확정';
    sandbox.document.getElementById('dNote').value = '실패할메모';
    await sandbox.AA.saveStatus();

    const cached = sandbox.AA.cache.find(r => r.reservationNo === '20260810-0003');
    check('saveStatus: 메모저장 실패 시 메모 롤백됨', cached.note === '기존메모', cached.note);
    check('saveStatus: 메모저장 실패해도 상태변경은 반영 유지', cached.status === '예약확정', cached.status);
  }

  /* ── 6) saveStatus: 변경 없음 → API 호출 없이 모달만 닫힘 ── */
  {
    const { sandbox, calls } = loadAaSandbox();
    sandbox.AA.cache = [{ reservationNo: '20260810-0004', status: '예약접수', note: '메모' }];
    sandbox.AA.selectedNo = '20260810-0004';
    sandbox.document.getElementById('statusSel').value = '예약접수';
    sandbox.document.getElementById('dNote').value = '메모';
    await sandbox.AA.saveStatus();
    check('saveStatus: 변경 없으면 updateStatus 미호출', calls.updateStatus.length === 0);
    check('saveStatus: 변경 없으면 update 미호출', calls.update.length === 0);
    check('saveStatus: 변경 없어도 모달은 닫힘', sandbox.AA.selectedNo === null);
  }

  /* ── 7) loadAll: 목록 조회 실패 시 renderTable이 오류 문구를 표시(빈 결과 문구와 구분) ── */
  {
    const { sandbox, store } = loadAaSandbox();
    sandbox.sheetsServiceMock.getAllImpl = async () => ({ ok: false, error: '네트워크 오류', data: [] });
    await sandbox.AA.loadAll();
    check('loadAll: 실패 시 cache 비워짐', sandbox.AA.cache.length === 0);
    check('loadAll: 실패 시 목록 영역에 "불러오지 못했습니다" 문구 표시', store.mainTable.innerHTML.includes('불러오지 못했습니다'), store.mainTable.innerHTML);
    check('loadAll: 실패 시 신규 시각요소(spinner 등) 없이 텍스트만', !store.mainTable.innerHTML.includes('spinner') && !store.mainTable.innerHTML.includes('class="loader'));
  }

  /* ── 8) loadAll: 성공 시 필터 결과 0건이면 기존 "조회된 예약이 없습니다" 문구(회귀) ── */
  {
    const { sandbox, store } = loadAaSandbox();
    sandbox.sheetsServiceMock.getAllImpl = async () => ({ ok: true, data: [], source: 'mock', count: 0 });
    await sandbox.AA.loadAll();
    check('loadAll: 성공+빈 목록 시 기존 문구 유지(회귀)', store.mainTable.innerHTML.includes('조회된 예약이 없습니다'), store.mainTable.innerHTML);
  }

  /* ── 9) openModal: 캐시 우선 조회, 캐시에 없으면 getOne fallback ── */
  {
    const { sandbox, calls, store } = loadAaSandbox();
    sandbox.AA.cache = [{ reservationNo: '20260810-0005', status: '예약접수', note: '캐시메모', name: '캐시테스트', birth: '1990-01-01', phone: '010-1111-2222', gender: '남성', program: 'BASIC', wishDate: '2026-08-10', wishTime: '09:00', sleep: '일반', company: '', optionalTests: [], createdAt: '2026-08-01 09:00:00', updatedAt: '2026-08-01 09:00:00' }];
    await sandbox.AA.openModal('20260810-0005');
    check('openModal: 캐시에 있으면 getOne 미호출', calls.getOne.length === 0);
    check('openModal: dNote가 textarea.value로 채워짐', store.dNote.value === '캐시메모', store.dNote.value);

    sandbox.sheetsServiceMock.getOneImpl = async (no) => ({ ok: true, data: { reservationNo: no, status: '예약접수', note: '폴백메모', name: '폴백테스트', birth: '1991-01-01', phone: '010-3333-4444', gender: '여성', program: 'SMART', wishDate: '2026-08-11', wishTime: '10:00', sleep: '수면', company: '', optionalTests: '', createdAt: '2026-08-02 09:00:00', updatedAt: '2026-08-02 09:00:00' } });
    await sandbox.AA.openModal('20260810-9999');
    check('openModal: 캐시에 없으면 getOne 호출(fallback)', calls.getOne.length === 1 && calls.getOne[0] === '20260810-9999', JSON.stringify(calls.getOne));
    check('openModal: fallback 데이터로 정상 표시', store.dNote.value === '폴백메모', store.dNote.value);
  }

  /* ── 결과 집계 ── */
  const failCount = results.filter((r) => !r.pass).length;
  const csvLines = ['name,pass,detail', ...results.map((r) => `"${r.name}",${r.pass},"${(r.detail || '').replace(/"/g, '""')}"`)];
  fs.writeFileSync(RESULT_CSV, csvLines.join('\n'), 'utf8');

  console.log('\n──────────────────────────────');
  console.log(`총 ${results.length}건 중 실패 ${failCount}건`);
  console.log(`결과 저장: ${RESULT_CSV}`);
  process.exit(failCount === 0 ? 0 : 1);
}

run();
