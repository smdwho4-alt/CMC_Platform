/**
 * CSHSP AI Chat Widget — Sprint F
 * 예약 페이지 어디든 삽입 가능한 AI 예약비서 위젯.
 *
 * 사용법:
 *   <link rel="stylesheet" href="chat_widget.css">
 *   <script src="chat_widget.js"></script>
 *   <script>CSHSPChat.init({ apiBase: 'http://localhost:8600' });</script>
 *
 * 원칙: AI는 예약을 확정하지 않는다. 서버 세션의 본인확인 상태(UNVERIFIED/
 * VERIFIED_BASIC/VERIFIED_PHONE)에 따라 기능과 개인정보 표시가 제한된다.
 */
'use strict';

const CSHSPChat = (() => {
  let apiBase = 'http://localhost:8600';
  let sessionId = null;
  let verifyState = 'UNVERIFIED';
  let lastTransport = null; // 'stream' | 'fallback' (검증용)
  let els = {};

  const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const STATE_LABEL = { UNVERIFIED: '미인증', VERIFIED_BASIC: '기본인증', VERIFIED_PHONE: '휴대폰인증' };

  function addMsg(role, text, blocked = false) {
    const div = document.createElement('div');
    div.className = `cshsp-msg ${role}${blocked ? ' blocked' : ''}`;
    div.innerHTML = `<div class="bubble">${esc(text)}</div>`;
    els.msgs.appendChild(div);
    els.msgs.scrollTop = els.msgs.scrollHeight;
    return div;
  }

  function setState(v) {
    verifyState = v || verifyState;
    els.state.textContent = `본인확인: ${STATE_LABEL[verifyState] || verifyState}`;
  }

  async function api(path, body) {
    const res = await fetch(apiBase + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return { ok: res.ok, data: await res.json().catch(() => ({})) };
  }

  /* Sprint I: SSE 스트리밍 수신 — 청크 단위로 말풍선을 채운다. 실패 시 /chat 폴백. */
  async function sendStreaming(message, context) {
    const res = await fetch(apiBase + '/api/agents/chat/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, message, context: context || {} }),
    });
    if (!res.ok || !res.body) throw new Error('stream ' + res.status);

    const wrap = addMsg('bot', '');
    const bubble = wrap.querySelector('.bubble');
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', meta = {}, event = 'message';

    const handleLine = (line) => {
      if (line.startsWith('event: ')) { event = line.slice(7).trim(); return; }
      if (!line.startsWith('data: ')) return;
      const payload = line.slice(6);
      if (event === 'meta') {
        meta = JSON.parse(payload || '{}');
        setState(meta.verifyState);
        if (meta.blocked) wrap.classList.add('blocked');
      } else if (event !== 'done') {
        bubble.textContent += JSON.parse(payload); // 텍스트 청크 누적
        els.msgs.scrollTop = els.msgs.scrollHeight;
      }
      event = 'message';
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n')) >= 0) {
        handleLine(buf.slice(0, idx).replace(/\r$/, ''));
        buf = buf.slice(idx + 1);
      }
    }
    if (!bubble.textContent) bubble.textContent = '(응답 없음)';
    lastTransport = 'stream';
    if (meta.needVerification) showVerifyForm();
    if (meta.needInput && meta.needInput.length && !meta.needVerification) showReservationForm();
  }

  async function send(message, context) {
    if (!message) return;
    addMsg('user', message);
    els.input.value = '';
    try {
      await sendStreaming(message, context);          // 기본: 스트리밍
      return;
    } catch (e) { /* 스트리밍 실패 → 일반 경로 폴백 */ }
    lastTransport = 'fallback';
    const { ok, data } = await api('/api/agents/chat', { sessionId, message, context: context || {} });
    if (!ok) { addMsg('bot', '서버 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.', true); return; }
    setState(data.verifyState);
    addMsg('bot', data.message || '(응답 없음)', !!data.blocked);
    if (data.needVerification) showVerifyForm();
    if (data.needInput && data.needInput.length && !data.needVerification) showReservationForm();
  }

  /* ── 본인확인 폼 (1단계 이름+전화 → 2단계 인증번호) ── */
  function showVerifyForm() {
    const wrap = addMsg('bot', '');
    wrap.querySelector('.bubble').innerHTML = `
      <div class="cshsp-form">
        <b style="font-size:12.5px">본인확인</b>
        <label>성함</label><input class="v-name" placeholder="홍길동">
        <label>휴대폰 번호</label><input class="v-phone" placeholder="010-0000-0000">
        <button class="v-basic">기본 확인</button>
        <label style="margin-top:10px">인증번호 (Mock: 문자로 발송됨)</label><input class="v-code" placeholder="6자리">
        <button class="v-code-btn" style="background:#0f4c81">인증번호 확인</button>
      </div>`;
    wrap.querySelector('.v-basic').onclick = async () => {
      const { data } = await api('/api/agents/verify', {
        sessionId, name: wrap.querySelector('.v-name').value.trim(),
        phone: wrap.querySelector('.v-phone').value.trim(),
      });
      setState(data.verifyState);
      addMsg('bot', data.message || '확인 실패');
    };
    wrap.querySelector('.v-code-btn').onclick = async () => {
      const { data } = await api('/api/agents/verify', {
        sessionId, code: wrap.querySelector('.v-code').value.trim(),
      });
      setState(data.verifyState);
      addMsg('bot', data.message || '확인 실패');
    };
  }

  /* ── 예약 신청 미니 폼 ── */
  function showReservationForm() {
    const wrap = addMsg('bot', '');
    wrap.querySelector('.bubble').innerHTML = `
      <div class="cshsp-form">
        <b style="font-size:12.5px">예약 신청 정보</b>
        <label>프로그램</label>
        <select class="r-prog">
          <option value="PRG-BASIC">BASIC (남44/여49만)</option>
          <option value="PRG-SMART">SMART (남77/여82만)</option>
          <option value="PRG-VIP">VIP (남110/여120만)</option>
          <option value="PRG-PREMIUM">PREMIUM (남130/여140만)</option>
          <option value="PRG-YOUNG">YOUNG (20~25만, 만19~38세)</option>
          <option value="PRG-ONKIME">온김에검진 (국가검진 동시)</option>
        </select>
        <label>희망 날짜</label><input class="r-date" type="date">
        <label>희망 시간</label>
        <select class="r-time">
          ${['08:00','08:30','09:00','09:30','10:00','10:30','11:00','13:00','13:30','14:00']
            .map((t) => `<option>${t}</option>`).join('')}
        </select>
        <button class="r-go">예약 신청 (직원 확인 후 확정)</button>
      </div>`;
    wrap.querySelector('.r-go').onclick = () => send('예약 신청할게요', {
      programId: wrap.querySelector('.r-prog').value,
      date: wrap.querySelector('.r-date').value,
      time: wrap.querySelector('.r-time').value,
    });
  }

  function build(mount) {
    const fab = document.createElement('button');
    fab.className = 'cshsp-chat-fab';
    fab.textContent = '💬';
    fab.title = 'AI 예약비서';

    const panel = document.createElement('div');
    panel.className = 'cshsp-chat-panel hidden';
    panel.innerHTML = `
      <div class="cshsp-chat-head">
        <b>천안의료원 AI 예약비서</b><span class="state">본인확인: 미인증</span>
      </div>
      <div class="cshsp-chat-msgs"></div>
      <div class="cshsp-quick">
        <button data-q="검진 프로그램 추천해 주세요">프로그램 추천</button>
        <button data-q="검진 전에 금식해야 하나요?">금식 안내</button>
        <button data-q="예약 신청할게요">예약 신청</button>
        <button data-q="내 예약 확인해줘">내 예약 확인</button>
        <button data-q="상담원 연결해 주세요">상담원 연결</button>
      </div>
      <div class="cshsp-chat-input">
        <input placeholder="메시지를 입력하세요" aria-label="메시지 입력">
        <button>전송</button>
      </div>
      <div class="cshsp-notice">AI는 예약 신청까지만 접수하며, 확정은 직원 확인 후 진행됩니다. 의료 상담은 041-570-7333.</div>`;

    (mount || document.body).appendChild(fab);
    (mount || document.body).appendChild(panel);

    els = {
      panel, msgs: panel.querySelector('.cshsp-chat-msgs'),
      state: panel.querySelector('.state'),
      input: panel.querySelector('.cshsp-chat-input input'),
    };
    fab.onclick = () => panel.classList.toggle('hidden');
    panel.querySelector('.cshsp-chat-input button').onclick = () => send(els.input.value.trim());
    els.input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(els.input.value.trim()); });
    panel.querySelector('.cshsp-quick').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-q]');
      if (b) send(b.dataset.q);
    });

    addMsg('bot', '안녕하세요! 천안의료원 건강검진센터 AI 예약비서입니다.\n'
      + '프로그램 안내·예약 신청·문진을 도와드립니다.\n'
      + '※ 예약은 직원 확인 후 확정됩니다.');
  }

  function init(opts = {}) {
    apiBase = opts.apiBase || apiBase;
    sessionId = sessionStorage.getItem('cshsp_chat_session')
      || ('CHAT-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36));
    sessionStorage.setItem('cshsp_chat_session', sessionId);
    build(opts.mount);
    return { sessionId };
  }

  return { init, send, get state() { return { sessionId, verifyState, lastTransport }; } };
})();
