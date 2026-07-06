/**
 * CSHSP Admin Console — UI Controller (Sprint C)
 * AdminAPI(admin_api.js)를 통해서만 데이터에 접근한다.
 */
'use strict';

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const VIEW_TITLES = {
  dashboard: 'Dashboard 요약', pending: '예약 승인 대기', reservations: '전체 예약 목록',
  detail: '예약 상세', slots: 'Slot 관리', schedules: '일정 관리', audit: '감사로그',
};
const AUDIT_ACTIONS = [
  'RESERVATION_REQUESTED', 'RESERVATION_APPROVED', 'RESERVATION_CANCELLED', 'RESERVATION_REJECTED',
  'RESERVATION_CHANGED', 'RESERVATION_NO_SHOW', 'RESERVATION_COMPLETED',
  'SLOT_HELD', 'SLOT_RELEASED', 'SLOT_FULL', 'INVALID_TRANSITION', 'DUPLICATED_REJECTED',
];

let currentView = 'dashboard';
let currentActor = 'USR-0002';
let lastListView = 'reservations';

/* ── 공통 ── */
function toast(msg, ok = true) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = `show ${ok ? 'ok' : 'err'}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.className = ''), 3000);
}

function statusBadge(status) {
  const m = STATUS_META[status] || { label: status, color: '#64748b' };
  return `<span class="badge" style="background:${m.color}">${esc(m.label)} ${esc(status)}</span>`;
}
function slotBadge(status) {
  const m = SLOT_STATUS_META[status] || { label: status, color: '#64748b' };
  return `<span class="badge" style="background:${m.color}">${esc(status)}</span>`;
}
function table(headers, rowsHtml, emptyMsg) {
  if (!rowsHtml) return `<div class="empty">${esc(emptyMsg || '데이터가 없습니다.')}</div>`;
  return `<table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rowsHtml}</tbody></table>`;
}

function showView(view) {
  currentView = view;
  document.querySelectorAll('main section').forEach((s) => s.classList.add('hidden'));
  $(`#view-${view}`).classList.remove('hidden');
  $('#viewTitle').textContent = VIEW_TITLES[view] || view;
  document.querySelectorAll('#menu button').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === view));
  if (view !== 'detail') lastListView = ['pending', 'reservations', 'dashboard'].includes(view) ? view : lastListView;
  render(view);
}

function render(view) {
  ({ dashboard: renderDashboard, pending: renderPending, reservations: renderReservations,
     slots: renderSlots, schedules: renderSchedules, audit: renderAudit }[view] || (() => {}))();
  $('#pendingCount').textContent = `(${AdminAPI.pendingReservations().length})`;
}

/* ── Dashboard ── */
function renderDashboard() {
  const k = AdminAPI.computeKPI();
  const cards = [
    ['오늘 예약 신청', k.todayRequested, '건'], ['승인 대기', k.pending, '건'],
    ['확정 예약', k.confirmed, '건'], ['취소 예약', k.cancelled, '건'],
    ['노쇼', k.noShow, '건'], ['Slot 가동률', k.slotUtilization, '%'],
    ['온라인 예약 비율', k.onlineRatio, '%'],
  ];
  $('#kpiGrid').innerHTML = cards.map(([label, v, unit]) =>
    `<div class="kpi-card"><div class="k-label">${esc(label)}</div><div class="k-value">${esc(v)}<small style="font-size:13px;color:var(--ink-sub)"> ${unit}</small></div></div>`).join('');
  $('#dashPending').innerHTML = pendingTableHtml(true);
}

/* ── 승인 대기함 ── */
function pendingRowHtml(r) {
  const p = AdminAPI.byId('Patient', r.patientId) || {};
  const prog = AdminAPI.byId('Program', r.programId) || {};
  return `<tr data-id="${esc(r.id)}" class="resv-row">
    <td>${esc(r.reservationNo || r.id)}</td>
    <td>${esc(String(r.requestedAt || r.createdAt).slice(0, 16).replace('T', ' '))}</td>
    <td>${esc(p.name || '-')}</td>
    <td>${esc(Privacy.maskBirth(p.birthDate))}</td>
    <td>${esc(prog.code || r.programId)}</td>
    <td>${esc(r.reservationDate)} ${esc(r.wishTime || '')}</td>
    <td>${esc(r.channel || '-')}</td>
    <td>${statusBadge(r.status)}</td>
    <td>
      <button class="btn btn-approve" data-act="approve" data-id="${esc(r.id)}">승인</button>
      <button class="btn btn-reject" data-act="reject" data-id="${esc(r.id)}">거절</button>
    </td></tr>`;
}
function pendingTableHtml(compact = false) {
  const rows = AdminAPI.pendingReservations();
  return table(
    ['예약번호', '신청일시', '수검자명', '생년월일', '프로그램', '희망일시', '신청경로', '상태', '처리'],
    rows.map(pendingRowHtml).join(''),
    '승인 대기 중인 예약이 없습니다.');
}
function renderPending() { $('#pendingTable').innerHTML = pendingTableHtml(); }

/* ── 전체 예약 목록 ── */
function renderReservations() {
  const status = $('#statusFilter').value;
  const query = $('#searchInput').value;
  const rows = AdminAPI.filterReservations({ status, query });
  $('#resvCount').textContent = `${rows.length}건`;
  $('#resvTable').innerHTML = table(
    ['예약번호', '수검자명', '생년월일', '전화번호', '프로그램', '검진일', '시간', '경로', '상태'],
    rows.map((r) => {
      const p = AdminAPI.byId('Patient', r.patientId) || {};
      const prog = AdminAPI.byId('Program', r.programId) || {};
      return `<tr data-id="${esc(r.id)}" class="resv-row">
        <td>${esc(r.reservationNo || r.id)}</td>
        <td>${esc(p.name || '-')}</td>
        <td>${esc(Privacy.maskBirth(p.birthDate))}</td>
        <td>${esc(Privacy.maskPhone(p.phone))}</td>
        <td>${esc(prog.code || r.programId)}</td>
        <td>${esc(r.reservationDate)}</td>
        <td>${esc(r.wishTime || '-')}</td>
        <td>${esc(r.channel || '-')}</td>
        <td>${statusBadge(r.status)}</td></tr>`;
    }).join(''),
    '조건에 맞는 예약이 없습니다.');
}

/* ── 예약 상세 ── */
function renderDetail(reservationId) {
  const d = AdminAPI.reservationDetail(reservationId);
  if (!d) { toast('예약을 찾을 수 없습니다.', false); return; }
  const { reservation: r, patient: p, program: prog, slot: s } = d;
  const full = Privacy.detailLevel((AdminAPI.byId('User', currentActor) || {}).roleId) === 'FULL';

  const actions = d.allowedNext.map((n) => `<span class="chip">${esc(n)}</span>`).join(' ') || '<span class="chip">종결 상태</span>';
  const buttons = [];
  if (d.allowedNext.includes('CONFIRMED')) buttons.push(`<button class="btn btn-approve" data-act="approve" data-id="${esc(r.id)}">승인 (CONFIRMED)</button>`);
  if (d.allowedNext.includes('REJECTED')) buttons.push(`<button class="btn btn-reject" data-act="reject" data-id="${esc(r.id)}">거절 (REJECTED)</button>`);
  if (d.allowedNext.includes('CANCELLED')) buttons.push(`<button class="btn btn-warn" data-act="cancel" data-id="${esc(r.id)}">취소 (CANCELLED)</button>`);

  $('#detailPanel').innerHTML = `
    <h3>${esc(r.reservationNo || r.id)} ${statusBadge(r.status)}</h3>
    <div class="detail-grid" style="margin-top:12px">
      <dl><dt>예약 기본정보</dt><dd>${esc(r.id)}</dd>
        <dt>검진 희망일시</dt><dd>${esc(r.reservationDate)} ${esc(r.wishTime || '')}</dd>
        <dt>신청경로 / 신청자</dt><dd>${esc(r.channel || '-')} / ${esc(r.requestedBy || '-')}</dd>
        <dt>신청일시</dt><dd>${esc(r.requestedAt || r.createdAt)}</dd>
        <dt>승인자 / 승인일시</dt><dd>${esc(r.approvedBy || '-')} / ${esc(r.approvedAt || '-')}</dd>
        <dt>메모</dt><dd>${esc(r.memo || '-')}</dd></dl>
      <dl><dt>수검자</dt><dd>${esc((p || {}).name || '-')} (${esc((p || {}).id || '-')})</dd>
        <dt>생년월일</dt><dd>${full ? esc((p || {}).birthDate || '-') : esc(Privacy.maskBirth((p || {}).birthDate))}</dd>
        <dt>연락처</dt><dd>${full ? esc((p || {}).phone || '-') : esc(Privacy.maskPhone((p || {}).phone))}</dd>
        <dt>성별</dt><dd>${esc((p || {}).gender || '-')}</dd></dl>
      <dl><dt>프로그램</dt><dd>${esc((prog || {}).name || r.programId)}</dd>
        <dt>선택검사</dt><dd>${esc((r.optionalTestIds || []).join(', ') || '없음')}</dd>
        <dt>수면내시경</dt><dd>${r.sleepEndoscopy ? '예' : '아니오'}</dd></dl>
      <dl><dt>Slot</dt><dd>${esc(r.slotId || '-')}</dd>
        <dt>Slot 상태</dt><dd>${s ? slotBadge(s.status) : '-'}</dd>
        <dt>정원 / 예약</dt><dd>${s ? `${esc(s.reservedCount)} / ${esc(s.capacity)}` : '-'}</dd></dl>
    </div>
    <div class="next-actions">
      <b style="font-size:13px">가능한 다음 상태:</b> ${actions} ${buttons.join(' ')}
    </div>
    <h3 style="margin-top:18px">감사로그 이력</h3>
    ${table(['일시', '이벤트', '수행자', '내용'],
      d.auditTrail.map((l) => `<tr class="no-click">
        <td>${esc(String(l.timestamp).slice(0, 19).replace('T', ' '))}</td>
        <td>${esc(l.action)}</td>
        <td>${esc(l.actorUserId)}</td>
        <td>${esc(l.note || JSON.stringify(l.after || {}))}</td></tr>`).join(''),
      '이 예약에 대한 감사로그가 없습니다.')}`;
  $('#detailPanel').dataset.reservationId = reservationId;
  showViewRaw('detail');
}
function showViewRaw(view) {
  currentView = view;
  document.querySelectorAll('main section').forEach((s) => s.classList.add('hidden'));
  $(`#view-${view}`).classList.remove('hidden');
  $('#viewTitle').textContent = VIEW_TITLES[view] || view;
}

/* ── Slot 관리 ── */
function renderSlots() {
  const f = $('#slotStatusFilter').value;
  const rows = AdminAPI.slotRows().filter((s) => !f || s.status === f);
  $('#slotTable').innerHTML = table(
    ['날짜', '시간', '검사실', '장비', '담당의(당일)', '간호사(당일)', '정원', '예약', '대기', '상태', '관리'],
    rows.map((s) => `<tr class="no-click">
      <td>${esc(s.date)}</td><td>${esc(s.time)}</td><td>${esc(s.roomName)}</td>
      <td>${esc(s.equipmentNames)}</td><td>${esc(s.doctorNames)}</td><td>${esc(s.nurseNames)}</td>
      <td>${esc(s.capacity)}</td><td>${esc(s.reservedCount)}</td><td>${esc(s.waitingCount ?? 0)}</td>
      <td>${slotBadge(s.status)}</td>
      <td>${s.status === 'HOLD' ? `<button class="btn btn-warn" data-act="releaseHold" data-id="${esc(s.id)}">HOLD 해제</button>` : '-'}</td>
    </tr>`).join(''),
    '조건에 맞는 Slot이 없습니다.');
}

/* ── 일정 관리 ── */
let schedTab = 'doctor';
function renderSchedules() {
  const data = AdminAPI.scheduleTab(schedTab);
  const fmtSch = (list) => list.map((s) =>
    `${s.date} ${s.startTime || ''}~${s.endTime || ''} [${s.status}] ${s.note || ''}`).join('<br>') || '-';
  let html;
  if (schedTab === 'holiday') {
    html = table(['날짜', '구분', '상태', '내용'],
      data.map((s) => `<tr class="no-click"><td>${esc(s.date)}</td><td>${esc(s.type)}</td>
        <td>${esc(s.status)}</td><td>${esc(s.note || '-')}</td></tr>`).join(''),
      '등록된 휴진일이 없습니다.');
  } else {
    const label = { doctor: '근무요일', nurse: '근무요일', room: '층/순번', equipment: '모델' }[schedTab];
    html = table(['이름', '상태', label, '등록 일정'],
      data.map((x) => {
        const mid = schedTab === 'room' ? `${x.floor}층 / ${x.order ?? '-'}`
          : schedTab === 'equipment' ? (x.model || '-')
          : (x.workDays || []).join(', ');
        return `<tr class="no-click"><td>${esc(x.name)}</td><td>${esc(x.status)}</td>
          <td>${esc(mid)}</td><td style="white-space:normal">${fmtSch(x.schedules || [])}</td></tr>`;
      }).join(''), '데이터가 없습니다.');
  }
  $('#schedPanel').innerHTML = html;
}

/* ── 감사로그 ── */
function renderAudit() {
  const rows = AdminAPI.filterAudit({
    action: $('#auditAction').value, query: $('#auditQuery').value, date: $('#auditDate').value,
  });
  $('#auditTable').innerHTML = table(
    ['발생일시', '이벤트', '대상', '수행자', '상세'],
    rows.map((l) => `<tr class="no-click">
      <td>${esc(String(l.timestamp).slice(0, 19).replace('T', ' '))}</td>
      <td>${esc(l.action)}</td>
      <td>${esc(l.entityType)} ${esc(l.entityId || '-')}</td>
      <td>${esc(l.actorUserId)} ${l.actorRole ? `(${esc(l.actorRole)})` : ''}</td>
      <td style="white-space:normal">${esc(l.note || JSON.stringify(l.after || {}))}</td></tr>`).join(''),
    '감사로그가 없습니다.');
}

/* ── 조작 핸들러 (mock=동기 / live=REST 비동기 — Promise.resolve로 통일) ── */
async function handleAction(act, id) {
  let result;
  if (act === 'approve') result = await Promise.resolve(AdminAPI.approveReservation(id, currentActor));
  else if (act === 'reject') result = await Promise.resolve(AdminAPI.rejectReservation(id, currentActor, '관리자 거절'));
  else if (act === 'cancel') result = await Promise.resolve(AdminAPI.cancelReservation(id, currentActor, '관리자 취소'));
  else if (act === 'releaseHold') result = await Promise.resolve(AdminAPI.releaseHold(id, currentActor));
  else return;
  toast(result.success
    ? `${act === 'releaseHold' ? id + ' HOLD 해제' : id + ' 처리'} 완료 (감사로그 기록됨)`
    : result.error, result.success);
  if (currentView === 'detail') renderDetail($('#detailPanel').dataset.reservationId);
  else render(currentView);
  $('#pendingCount').textContent = `(${AdminAPI.pendingReservations().length})`;
}

/* ── 이벤트 바인딩 ── */
function bind() {
  $('#menu').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-view]');
    if (btn) showView(btn.dataset.view);
  });
  document.body.addEventListener('click', (e) => {
    const actBtn = e.target.closest('button[data-act]');
    if (actBtn) { e.stopPropagation(); handleAction(actBtn.dataset.act, actBtn.dataset.id); return; }
    const row = e.target.closest('tr.resv-row');
    if (row) renderDetail(row.dataset.id);
  });
  $('#backLink').addEventListener('click', () => showView(lastListView === 'dashboard' ? 'dashboard' : lastListView));
  $('#statusFilter').addEventListener('change', renderReservations);
  $('#searchInput').addEventListener('input', renderReservations);
  $('#slotStatusFilter').addEventListener('change', renderSlots);
  $('#schedTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-tab]');
    if (!b) return;
    schedTab = b.dataset.tab;
    document.querySelectorAll('#schedTabs button').forEach((x) => x.classList.toggle('active', x === b));
    renderSchedules();
  });
  ['auditAction', 'auditQuery', 'auditDate'].forEach((id) =>
    $(`#${id}`).addEventListener(id === 'auditQuery' ? 'input' : 'change', renderAudit));
  $('#actorSelect').addEventListener('change', (e) => {
    currentActor = e.target.value;
    AdminAPI.setActor(currentActor); // live 모드 X-User-Id 헤더 동기화
    toast(`현재 사용자: ${e.target.selectedOptions[0].textContent}`);
    if (currentView === 'detail') renderDetail($('#detailPanel').dataset.reservationId);
  });
}

/* ── 초기화 ── */
async function init() {
  // 상태 필터 옵션
  $('#statusFilter').innerHTML = '<option value="">전체 상태</option>' +
    Object.keys(STATUS_META).map((s) => `<option value="${s}">${s} (${STATUS_META[s].label})</option>`).join('');
  $('#auditAction').innerHTML = '<option value="">전체 이벤트</option>' +
    AUDIT_ACTIONS.map((a) => `<option>${a}</option>`).join('');
  // 모드 배너
  const banner = document.querySelector('.mode');
  if (banner && AdminAPI.MODE === 'live') {
    banner.innerHTML = `<b>Live 모드</b><br>Reservation Engine API 연동 중<br>(${esc(AdminAPI.API_BASE)})`;
    banner.style.background = 'rgba(102,187,106,.2)';
    banner.style.color = '#a5d6a7';
  }
  try {
    await AdminAPI.loadAll();
  } catch (err) {
    $('#kpiGrid').innerHTML = `<div class="panel" style="grid-column:1/-1;color:var(--bad)">
      데이터 로드 실패: ${esc(err.message)}<br>
      로컬 서버로 실행하세요: <code>python -m http.server 4173</code> (CMC_Platform_new 폴더에서) →
      http://localhost:4173/admin/</div>`;
    return;
  }
  // 직원 선택 (승인 권한 데모: AI 계정 선택 시 승인 거부됨)
  $('#actorSelect').innerHTML = AdminAPI.all('User')
    .map((u) => `<option value="${esc(u.id)}" ${u.id === currentActor ? 'selected' : ''}>${esc(u.name)} (${esc(u.roleId)})</option>`).join('');
  bind();
  showView('dashboard');
}
document.addEventListener('DOMContentLoaded', init);
