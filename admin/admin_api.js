/**
 * CSHSP Admin Console — API Adapter (Sprint C)
 *
 * MODE = 'mock' : data/*.json을 fetch로 읽고, 조작(승인/거절/취소/HOLD해제)은
 *                 세션 메모리에서 Sprint B Reservation Engine 로직을 미러링한다.
 * MODE = 'live' : Sprint D REST API로 교체 예정 — 함수 시그니처는
 *                 reservation_engine.py(approve_reservation 등)와 1:1 대응.
 *
 * 개인정보 표시 기준(Privacy)과 상태 전이표(StateMachine)는
 * 별도 객체로 분리하여 향후 RBAC 적용 지점을 명확히 한다.
 */
'use strict';

/* ── 상태 전이표: src/reservation/state_machine.py 미러 ── */
const StateMachine = {
  TRANSITIONS: {
    REQUESTED:        ['PENDING_APPROVAL', 'CANCELLED', 'REJECTED'],
    PENDING_APPROVAL: ['CONFIRMED', 'CANCELLED', 'REJECTED'],
    CONFIRMED:        ['COMPLETED', 'CANCELLED', 'CHANGED', 'NO_SHOW'],
    CHANGED:          ['PENDING_APPROVAL'],
    WAITING:          ['PENDING_APPROVAL', 'CANCELLED', 'REJECTED'],
    COMPLETED: [], CANCELLED: [], NO_SHOW: [], REJECTED: [],
  },
  allowedNext(status) { return (this.TRANSITIONS[status] || []).slice().sort(); },
  canTransition(cur, next) { return (this.TRANSITIONS[cur] || []).includes(next); },
};

/* ── 개인정보 표시 기준 (향후 RBAC 연동 지점) ── */
const Privacy = {
  // 목록 화면: 최소 표시
  maskBirth(b)  { return b ? String(b).slice(0, 4) + '****' : '-'; },
  maskPhone(p)  {
    const m = String(p || '').match(/^(\d{2,3})-?(\d{3,4})-?(\d{4})$/);
    return m ? `${m[1]}-****-${m[3]}` : (p ? '***' : '-');
  },
  // 상세 화면: 역할 기반 표시 수준 (Sprint D에서 서버 RBAC로 대체)
  detailLevel(roleId) {
    return ['ROLE-ADMIN', 'ROLE-STAFF', 'ROLE-DIRECTOR'].includes(roleId) ? 'FULL' : 'MASKED';
  },
};

/* ── 상태 라벨/색상 ── */
const STATUS_META = {
  REQUESTED:        { label: '예약 신청',   color: '#1565c0' },
  PENDING_APPROVAL: { label: '승인 대기',   color: '#e65100' },
  CONFIRMED:        { label: '예약 확정',   color: '#2e7d32' },
  CANCELLED:        { label: '예약 취소',   color: '#c62828' },
  CHANGED:          { label: '예약 변경',   color: '#6a1b9a' },
  COMPLETED:        { label: '검진 완료',   color: '#4527a0' },
  NO_SHOW:          { label: '노쇼',        color: '#37474f' },
  WAITING:          { label: '대기예약',    color: '#00695c' },
  REJECTED:         { label: '예약 불가',   color: '#880e4f' },
};
const SLOT_STATUS_META = {
  AVAILABLE: { label: '예약 가능', color: '#2e7d32' },
  FULL:      { label: '정원 마감', color: '#c62828' },
  WAITING:   { label: '대기 접수', color: '#00695c' },
  DUPLICATED:{ label: '중복 감지', color: '#6a1b9a' },
  HOLD:      { label: '보류',      color: '#e65100' },
  BLOCKED:   { label: '차단',      color: '#37474f' },
};

const AdminAPI = (() => {
  // Sprint D: URL ?mode=live 로 REST API 연동, 기본은 mock (세션 메모리)
  const _params = new URLSearchParams(location.search);
  const MODE = _params.get('mode') === 'live' ? 'live' : 'mock';
  const API_BASE = _params.get('api') || 'http://localhost:8600';
  let liveActor = 'USR-0002'; // X-User-Id 헤더 (Mock 인증)
  const FILES = {
    Reservation: 'reservations.json', Patient: 'patients.json', Program: 'programs.json',
    Slot: 'slots.json', Room: 'rooms.json', Equipment: 'equipment.json',
    Doctor: 'doctors.json', Nurse: 'nurses.json', Schedule: 'schedules.json',
    AuditLog: 'audit_logs.json', User: 'users.json', Role: 'roles.json',
  };
  const WEEKDAY = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

  let db = {};          // entity → records (세션 메모리)
  let mockAuditSeq = 0; // mock 감사로그 채번

  async function loadAll(base = '../data/') {
    const entries = await Promise.all(Object.entries(FILES).map(async ([entity, file]) => {
      const res = await fetch(base + file);
      if (!res.ok) throw new Error(`데이터 로드 실패: ${file} (${res.status})`);
      const doc = await res.json();
      return [entity, Array.isArray(doc) ? doc : (doc.records || [])];
    }));
    db = Object.fromEntries(entries);
    return db;
  }

  const all  = (entity) => db[entity] || [];
  const byId = (entity, id) => all(entity).find((r) => r.id === id) || null;
  const nowISO = () => new Date().toISOString().slice(0, 19) + '+09:00';
  const todayStr = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  /* ── 권한: users.json + roles.json (엔진 _has_permission 미러) ── */
  function hasPermission(userId, perm) {
    const user = byId('User', userId);
    if (!user || user.status !== 'ACTIVE') return false;
    const role = byId('Role', user.roleId);
    const perms = (role && role.permissions) || [];
    return perms.includes('*') || perms.includes(perm);
  }

  /* ── 감사로그 (mock: 메모리 append / live: 서버 기록) ── */
  function appendAudit(action, entityType, entityId, actorUserId, before, after, note) {
    const user = byId('User', actorUserId);
    const rec = {
      id: `AUD-MOCK-${String(++mockAuditSeq).padStart(4, '0')}`,
      timestamp: nowISO(),
      actorUserId, actorRole: user ? user.roleId : null,
      action, entityType, entityId,
      before: before || null, after: after || null,
      channel: 'ADMIN_WEB', note: note || undefined,
    };
    all('AuditLog').push(rec);
    return rec;
  }

  /* ── Slot 점유/해제 (엔진 로직 미러) ── */
  function occupySlot(slotId, actor) {
    const slot = byId('Slot', slotId);
    if (!slot) return;
    slot.reservedCount = (slot.reservedCount || 0) + 1;
    const full = slot.reservedCount >= (slot.capacity || 0);
    slot.status = full ? 'FULL' : 'AVAILABLE';
    delete slot.holdReason;
    slot.updatedAt = nowISO();
    if (full) appendAudit('SLOT_FULL', 'Slot', slotId, actor, null, { status: 'FULL', reservedCount: slot.reservedCount });
  }
  function releaseSlot(slotId, actor, wasConfirmed, note) {
    const slot = byId('Slot', slotId);
    if (!slot) return;
    const before = { status: slot.status, reservedCount: slot.reservedCount };
    if (wasConfirmed && slot.reservedCount > 0) slot.reservedCount -= 1;
    slot.status = slot.reservedCount < (slot.capacity || 0) ? 'AVAILABLE' : 'FULL';
    delete slot.holdReason;
    slot.updatedAt = nowISO();
    appendAudit('SLOT_RELEASED', 'Slot', slotId, actor, before,
      { status: slot.status, reservedCount: slot.reservedCount }, note);
  }

  /* ── 예약 조작: reservation_engine.py 시그니처 1:1 대응 ── */
  function approveReservation(reservationId, approverUserId) {
    if (!hasPermission(approverUserId, 'reservation:approve'))
      return { success: false, error: `승인 권한 없음: ${approverUserId} (reservation:approve 필요)` };
    const rec = byId('Reservation', reservationId);
    if (!rec) return { success: false, error: `예약 없음: ${reservationId}` };
    if (!StateMachine.canTransition(rec.status, 'CONFIRMED')) {
      appendAudit('INVALID_TRANSITION', 'Reservation', reservationId, approverUserId,
        { status: rec.status }, { status: 'CONFIRMED' }, '허용되지 않는 전이');
      return { success: false, error: `허용되지 않는 전이: ${rec.status} → CONFIRMED` };
    }
    const before = rec.status;
    Object.assign(rec, { status: 'CONFIRMED', approvedBy: approverUserId, approvedAt: nowISO(), updatedAt: nowISO() });
    if (rec.slotId) occupySlot(rec.slotId, approverUserId);
    appendAudit('RESERVATION_APPROVED', 'Reservation', reservationId, approverUserId,
      { status: before }, { status: 'CONFIRMED' });
    return { success: true, reservation: rec };
  }

  function rejectReservation(reservationId, actorUserId, reason) {
    if (!hasPermission(actorUserId, 'reservation:approve'))
      return { success: false, error: `거절 권한 없음: ${actorUserId}` };
    const rec = byId('Reservation', reservationId);
    if (!rec) return { success: false, error: `예약 없음: ${reservationId}` };
    if (!StateMachine.canTransition(rec.status, 'REJECTED')) {
      appendAudit('INVALID_TRANSITION', 'Reservation', reservationId, actorUserId,
        { status: rec.status }, { status: 'REJECTED' }, '허용되지 않는 전이');
      return { success: false, error: `허용되지 않는 전이: ${rec.status} → REJECTED` };
    }
    const before = rec.status;
    Object.assign(rec, { status: 'REJECTED', cancelReason: reason || null, updatedAt: nowISO() });
    if (rec.slotId) releaseSlot(rec.slotId, actorUserId, false, `${reservationId} 거절로 Slot 복구`);
    appendAudit('RESERVATION_REJECTED', 'Reservation', reservationId, actorUserId,
      { status: before }, { status: 'REJECTED' }, reason);
    return { success: true, reservation: rec };
  }

  function cancelReservation(reservationId, actorUserId, reason) {
    if (!hasPermission(actorUserId, 'reservation:cancel'))
      return { success: false, error: `취소 권한 없음: ${actorUserId}` };
    const rec = byId('Reservation', reservationId);
    if (!rec) return { success: false, error: `예약 없음: ${reservationId}` };
    if (!StateMachine.canTransition(rec.status, 'CANCELLED')) {
      appendAudit('INVALID_TRANSITION', 'Reservation', reservationId, actorUserId,
        { status: rec.status }, { status: 'CANCELLED' }, '허용되지 않는 전이');
      return { success: false, error: `허용되지 않는 전이: ${rec.status} → CANCELLED` };
    }
    const before = rec.status;
    Object.assign(rec, { status: 'CANCELLED', cancelReason: reason || null, updatedAt: nowISO() });
    if (rec.slotId) releaseSlot(rec.slotId, actorUserId, before === 'CONFIRMED', `${reservationId} 취소로 Slot 복구`);
    appendAudit('RESERVATION_CANCELLED', 'Reservation', reservationId, actorUserId,
      { status: before }, { status: 'CANCELLED' }, reason);
    return { success: true, reservation: rec };
  }

  /* ── Slot HOLD 해제 ── */
  function releaseHold(slotId, actorUserId) {
    if (!hasPermission(actorUserId, 'slot:manage'))
      return { success: false, error: `Slot 관리 권한 없음: ${actorUserId}` };
    const slot = byId('Slot', slotId);
    if (!slot) return { success: false, error: `Slot 없음: ${slotId}` };
    if (slot.status !== 'HOLD') return { success: false, error: `HOLD 상태가 아님: ${slot.status}` };
    releaseSlot(slotId, actorUserId, false, 'HOLD 수동 해제');
    return { success: true, slot };
  }

  /* ── 조회/필터/검색 ── */
  function filterReservations({ status = '', query = '' } = {}) {
    const q = query.trim().toLowerCase();
    return all('Reservation').filter((r) => {
      if (status && r.status !== status) return false;
      if (!q) return true;
      const patient = byId('Patient', r.patientId) || {};
      const program = byId('Program', r.programId) || {};
      const phoneLast4 = String(patient.phone || '').replace(/\D/g, '').slice(-4);
      return [r.id, r.reservationNo, patient.name, program.code, program.name, r.reservationDate]
        .some((v) => String(v || '').toLowerCase().includes(q)) || phoneLast4 === q;
    }).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  }

  const pendingReservations = () => filterReservations({ status: 'PENDING_APPROVAL' });

  function reservationDetail(reservationId) {
    const rec = byId('Reservation', reservationId);
    if (!rec) return null;
    return {
      reservation: rec,
      patient: byId('Patient', rec.patientId),
      program: byId('Program', rec.programId),
      slot: byId('Slot', rec.slotId),
      auditTrail: all('AuditLog')
        .filter((l) => l.entityId === reservationId || (l.entityType === 'Slot' && l.entityId === rec.slotId))
        .sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp))),
      allowedNext: StateMachine.allowedNext(rec.status),
    };
  }

  function slotRows() {
    return all('Slot').map((s) => {
      const room = byId('Room', s.roomId) || {};
      const wd = WEEKDAY[new Date(s.date + 'T00:00:00').getDay()];
      return {
        ...s,
        roomName: room.name || s.roomId,
        equipmentNames: all('Equipment').filter((e) => e.roomId === s.roomId).map((e) => e.name).join(', ') || '-',
        doctorNames: all('Doctor').filter((d) => d.status === 'ACTIVE' && (d.workDays || []).includes(wd)).map((d) => d.name).join(', ') || '-',
        nurseNames: all('Nurse').filter((n) => n.status === 'ACTIVE' && (n.workDays || []).includes(wd)).map((n) => n.name).join(', ') || '-',
      };
    }).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
  }

  function scheduleTab(tab) {
    const S = all('Schedule');
    switch (tab) {
      case 'doctor':  return all('Doctor').map((d) => ({ ...d, schedules: S.filter((s) => s.refId === d.id) }));
      case 'nurse':   return all('Nurse').map((n) => ({ ...n, schedules: S.filter((s) => s.refId === n.id) }));
      case 'room':    return all('Room').map((r) => ({ ...r, schedules: S.filter((s) => s.refId === r.id) }));
      case 'equipment': return all('Equipment').map((e) => ({ ...e, schedules: S.filter((s) => s.refId === e.id) }));
      case 'holiday': return S.filter((s) => s.type === 'HOLIDAY');
      default: return [];
    }
  }

  function filterAudit({ action = '', query = '', date = '' } = {}) {
    const q = query.trim().toLowerCase();
    return all('AuditLog').filter((l) => {
      if (action && l.action !== action) return false;
      if (date && !String(l.timestamp).startsWith(date)) return false;
      if (!q) return true;
      return [l.entityId, l.actorUserId, l.action, l.note].some((v) => String(v || '').toLowerCase().includes(q));
    }).sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
  }

  /* ── Dashboard KPI ── */
  function computeKPI(today = todayStr()) {
    const R = all('Reservation');
    const slots = all('Slot').filter((s) => s.status !== 'BLOCKED');
    const cap = slots.reduce((a, s) => a + (s.capacity || 0), 0);
    const reserved = slots.reduce((a, s) => a + (s.reservedCount || 0), 0);
    const online = R.filter((r) => ['WEB', 'AI_ASSISTANT'].includes(r.channel)).length;
    return {
      todayRequested: R.filter((r) => String(r.requestedAt || r.createdAt).startsWith(today)).length,
      pending: R.filter((r) => r.status === 'PENDING_APPROVAL').length,
      confirmed: R.filter((r) => r.status === 'CONFIRMED').length,
      cancelled: R.filter((r) => r.status === 'CANCELLED').length,
      noShow: R.filter((r) => r.status === 'NO_SHOW').length,
      slotUtilization: cap ? Math.round((reserved / cap) * 1000) / 10 : 0,
      onlineRatio: R.length ? Math.round((online / R.length) * 1000) / 10 : 0,
    };
  }

  const api = {
    MODE, API_BASE, loadAll, all, byId, todayStr, hasPermission,
    approveReservation, rejectReservation, cancelReservation, releaseHold,
    filterReservations, pendingReservations, reservationDetail,
    slotRows, scheduleTab, filterAudit, computeKPI,
    setActor(userId) { liveActor = userId; },
  };

  /* ── Sprint D: live 모드 — Reservation Engine REST API 연동 ──
     조회(필터/검색/KPI/상세 조인)는 번들 스냅샷 기반으로 동일하게 동작하고,
     조작은 서버 엔진이 수행한 뒤 번들을 재수신하여 화면과 동기화한다. */
  if (MODE === 'live') {
    const headers = () => ({ 'Content-Type': 'application/json', 'X-User-Id': liveActor });

    api.loadAll = async () => {
      const res = await fetch(`${API_BASE}/api/entities/bundle`, { headers: headers() });
      if (!res.ok) throw new Error(`API 연결 실패 (${res.status}) — ${API_BASE} 에서 api_server 실행 필요`);
      db = await res.json();
      return db;
    };

    async function call(path, body, actor) {
      try {
        const res = await fetch(API_BASE + path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Id': actor || liveActor },
          body: JSON.stringify(body || {}),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const d = data.detail;
          return { success: false, error: typeof d === 'string' ? d : (d && d.reasons ? d.reasons.join('; ') : `HTTP ${res.status}`) };
        }
        await api.loadAll(); // 서버 상태 재동기화
        return { success: true, ...data };
      } catch (err) {
        return { success: false, error: err.message };
      }
    }

    api.approveReservation = (id, actor) => call(`/api/reservations/${id}/approve`, {}, actor);
    api.rejectReservation  = (id, actor, reason) => call(`/api/reservations/${id}/reject`, { reason: reason || '' }, actor);
    api.cancelReservation  = (id, actor, reason) => call(`/api/reservations/${id}/cancel`, { reason: reason || '' }, actor);
    api.releaseHold        = (id, actor) => call(`/api/slots/${id}/release-hold`, {}, actor);
  }

  return api;
})();
