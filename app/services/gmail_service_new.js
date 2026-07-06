/**
 * CMC Health Screening Platform v1.0 — Phase 3
 * app/services/gmail_service_new.js
 *
 * Gmail API Adapter — 예약 관련 이메일 발송
 *  - Mock 모드: 이메일 내용을 localStorage에 기록 + 콘솔 출력
 *  - Live 모드: Gmail API v1 호출 (운영 전 설정 필요)
 *
 * [보안] 수검자 이메일은 개인정보이므로 서버사이드 처리 권장.
 * 클라이언트사이드 Gmail API 사용 시 OAuth 사용자 동의 필수.
 */
'use strict';

const CMC_GmailService = {

  STORAGE_KEY: 'cmc_mail_log_v1',
  _mockDelay: 500,

  /* ─────────────────────────────────────────────────────────
     공개 인터페이스
  ───────────────────────────────────────────────────────── */

  /** 예약접수 확인 메일 */
  async sendReceived(reservation, toEmail) {
    const mail = this._buildReceived(reservation, toEmail);
    return this._send(mail);
  },

  /** 예약확정 안내 메일 */
  async sendConfirmed(reservation, toEmail) {
    const mail = this._buildConfirmed(reservation, toEmail);
    return this._send(mail);
  },

  /** 예약취소 안내 메일 */
  async sendCancelled(reservation, toEmail) {
    const mail = this._buildCancelled(reservation, toEmail);
    return this._send(mail);
  },

  /** 일정변경 안내 메일 */
  async sendRescheduled(reservation, toEmail, newDate, newTime) {
    const mail = this._buildRescheduled(reservation, toEmail, newDate, newTime);
    return this._send(mail);
  },

  /** 발송 로그 조회 (Mock 모드) */
  getLog() {
    try { return JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '[]'); }
    catch { return []; }
  },

  /** 연결 테스트 */
  async ping() {
    if (!CMC_CONFIG.isGoogle()) return { ok: true, mode: 'mock', message: 'Mock 모드 — 메일 로그만 기록됨' };
    return this._livePing();
  },

  /* ─────────────────────────────────────────────────────────
     공통 발송 라우터
  ───────────────────────────────────────────────────────── */

  async _send(mail) {
    if (!CMC_CONFIG.notifications.emailOnReceive && mail._type === 'received') return { ok: true, skipped: true };
    if (!CMC_CONFIG.notifications.emailOnConfirm && mail._type === 'confirmed') return { ok: true, skipped: true };
    if (!CMC_CONFIG.notifications.emailOnCancel  && mail._type === 'cancelled') return { ok: true, skipped: true };
    return CMC_CONFIG.isGoogle() ? this._liveSend(mail) : this._mockSend(mail);
  },

  /* ─────────────────────────────────────────────────────────
     메일 본문 빌더
  ───────────────────────────────────────────────────────── */

  _buildReceived(r, to) {
    return {
      _type:   'received',
      to,
      from:    `${CMC_CONFIG.hospital.name} <${CMC_CONFIG.google.senderEmail || 'noreply@cheonanmc.or.kr'}>`,
      subject: `[천안의료원 건강검진센터] 예약 접수 확인 — ${r.name}님 (${r.reservationNo})`,
      html: this._wrap(`
        <h2 style="color:#1a4f8a">예약 접수가 완료되었습니다</h2>
        <p>${r.name}님의 건강검진 예약 신청이 접수되었습니다.<br>
        담당자가 <strong>1~2 영업일 내</strong> 확인 연락을 드리겠습니다.</p>
        ${this._infoTable(r)}
        <p style="color:#666;font-size:13px">예약번호: <strong>${r.reservationNo}</strong></p>
        <p>문의: <strong>${CMC_CONFIG.hospital.tel}</strong> (평일 08:00~17:00)</p>
      `),
    };
  },

  _buildConfirmed(r, to) {
    return {
      _type:   'confirmed',
      to,
      from:    `${CMC_CONFIG.hospital.name} <${CMC_CONFIG.google.senderEmail || 'noreply@cheonanmc.or.kr'}>`,
      subject: `[천안의료원 건강검진센터] 예약이 확정되었습니다 — ${r.name}님 (${r.wishDate})`,
      html: this._wrap(`
        <h2 style="color:#2e7d32">✅ 예약이 확정되었습니다</h2>
        <p>${r.name}님의 건강검진 예약이 확정되었습니다.</p>
        ${this._infoTable(r)}
        <h3 style="color:#1a4f8a;margin-top:20px">검진 전 주의사항</h3>
        <ul style="line-height:2">
          <li>검진 당일 <strong>자정부터 금식</strong>이 필요합니다 (물·약 복용 여부는 사전 문의).</li>
          <li>수면 검진 선택 시 검진 후 <strong>운전 불가</strong> — 보호자 동반 또는 대중교통 이용.</li>
          <li>검진 당일 편안한 복장으로 방문해 주세요.</li>
          <li>접수는 검진 시간 <strong>20분 전</strong> 도착을 권장합니다.</li>
        </ul>
        <p>문의: <strong>${CMC_CONFIG.hospital.tel}</strong></p>
      `),
    };
  },

  _buildCancelled(r, to) {
    return {
      _type:   'cancelled',
      to,
      from:    `${CMC_CONFIG.hospital.name} <${CMC_CONFIG.google.senderEmail || 'noreply@cheonanmc.or.kr'}>`,
      subject: `[천안의료원 건강검진센터] 예약 취소 안내 — ${r.name}님`,
      html: this._wrap(`
        <h2 style="color:#c62828">예약이 취소되었습니다</h2>
        <p>${r.name}님의 건강검진 예약(${r.reservationNo})이 취소 처리되었습니다.</p>
        <p>재예약을 원하시면 아래로 연락 주세요.</p>
        <p>문의: <strong>${CMC_CONFIG.hospital.tel}</strong> (평일 08:00~17:00)</p>
      `),
    };
  },

  _buildRescheduled(r, to, newDate, newTime) {
    return {
      _type:   'rescheduled',
      to,
      from:    `${CMC_CONFIG.hospital.name} <${CMC_CONFIG.google.senderEmail || 'noreply@cheonanmc.or.kr'}>`,
      subject: `[천안의료원 건강검진센터] 검진 일정 변경 안내 — ${r.name}님`,
      html: this._wrap(`
        <h2 style="color:#e65100">🔄 검진 일정이 변경되었습니다</h2>
        <p>${r.name}님의 검진 일정이 아래와 같이 변경되었습니다.</p>
        <table style="border-collapse:collapse;width:100%;margin:12px 0">
          <tr style="background:#f5f5f5"><th style="padding:8px 12px;text-align:left;border:1px solid #ddd">구분</th><th style="padding:8px 12px;text-align:left;border:1px solid #ddd">일정</th></tr>
          <tr><td style="padding:8px 12px;border:1px solid #ddd;color:#666">변경 전</td><td style="padding:8px 12px;border:1px solid #ddd">${r.wishDate} ${r.wishTime}</td></tr>
          <tr style="background:#fff8e1"><td style="padding:8px 12px;border:1px solid #ddd;font-weight:700">변경 후</td><td style="padding:8px 12px;border:1px solid #ddd;font-weight:700;color:#e65100">${newDate} ${newTime}</td></tr>
        </table>
        <p>문의: <strong>${CMC_CONFIG.hospital.tel}</strong></p>
      `),
    };
  },

  _infoTable(r) {
    return `
      <table style="border-collapse:collapse;width:100%;margin:14px 0">
        <tr style="background:#e8f0fb"><th colspan="2" style="padding:9px 12px;text-align:left;color:#1a4f8a;border:1px solid #c8d8f0">예약 정보</th></tr>
        <tr><td style="padding:8px 12px;border:1px solid #ddd;color:#666;width:110px">예약번호</td><td style="padding:8px 12px;border:1px solid #ddd;font-family:monospace">${r.reservationNo}</td></tr>
        <tr style="background:#fafafa"><td style="padding:8px 12px;border:1px solid #ddd;color:#666">프로그램</td><td style="padding:8px 12px;border:1px solid #ddd;font-weight:700">${r.program}</td></tr>
        <tr><td style="padding:8px 12px;border:1px solid #ddd;color:#666">희망일시</td><td style="padding:8px 12px;border:1px solid #ddd;font-weight:700">${r.wishDate} ${r.wishTime}</td></tr>
        <tr style="background:#fafafa"><td style="padding:8px 12px;border:1px solid #ddd;color:#666">수면검진</td><td style="padding:8px 12px;border:1px solid #ddd">${r.sleep}</td></tr>
        ${r.company ? `<tr><td style="padding:8px 12px;border:1px solid #ddd;color:#666">사업장</td><td style="padding:8px 12px;border:1px solid #ddd">${r.company}</td></tr>` : ''}
      </table>`;
  },

  _wrap(content) {
    return `<!DOCTYPE html><html lang="ko"><body style="font-family:'Malgun Gothic',sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#333">
      <div style="background:#1a4f8a;padding:16px 24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:18px">🏥 ${CMC_CONFIG.hospital.name}</h1>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px">
        ${content}
        <hr style="margin:24px 0;border:none;border-top:1px solid #eee">
        <p style="color:#999;font-size:12px;line-height:1.8">
          ${CMC_CONFIG.hospital.address}<br>
          Tel: ${CMC_CONFIG.hospital.tel}<br>
          본 메일은 발신 전용입니다. CMC Health Screening Platform v1.0
        </p>
      </div>
    </body></html>`;
  },

  /* ─────────────────────────────────────────────────────────
     Mock 구현 — 로컬 로그 저장
  ───────────────────────────────────────────────────────── */

  _delay() { return new Promise(r => setTimeout(r, this._mockDelay)); },

  async _mockSend(mail) {
    await this._delay();
    const log = this.getLog();
    const entry = { ...mail, sentAt: new Date().toISOString(), mode: 'mock', messageId: `mock_${Date.now()}` };
    delete entry.html;  // 로그에는 HTML 본문 제외 (용량 절약)
    log.unshift(entry);
    if (log.length > 50) log.splice(50);  // 최대 50건 유지
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(log));
    console.log(`[GmailService Mock] send → ${mail._type}`, `to: ${mail.to}`, `subject: ${mail.subject}`);
    return { ok: true, messageId: entry.messageId, source: 'local', mail: entry };
  },

  /* ─────────────────────────────────────────────────────────
     Live 구현 (Gmail API v1)
     [운영 전 구현 필요] — 서버사이드 처리 권장
  ───────────────────────────────────────────────────────── */

  async _getToken() {
    throw new Error('Google OAuth 토큰 미설정 — CMC_CONFIG.google.clientId 확인 필요');
  },

  async _liveSend(mail) {
    const token  = await this._getToken();
    const raw    = this._toBase64(mail);
    const res    = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', {
      method:  'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify({ raw }),
    });
    if (!res.ok) throw new Error(`Gmail API 오류: ${res.status}`);
    const body = await res.json();
    return { ok: true, messageId: body.id, source: 'google' };
  },

  _toBase64(mail) {
    const mime = [
      `From: ${mail.from}`,
      `To: ${mail.to}`,
      `Subject: =?UTF-8?B?${btoa(unescape(encodeURIComponent(mail.subject)))}?=`,
      'MIME-Version: 1.0',
      'Content-Type: text/html; charset=UTF-8',
      '',
      mail.html,
    ].join('\r\n');
    return btoa(unescape(encodeURIComponent(mime))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  },

  async _livePing() {
    try {
      const token = await this._getToken();
      const res   = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/profile', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const body = await res.json();
        return { ok: true, mode: 'live', message: `Gmail 연결 성공: ${body.emailAddress}` };
      }
      return { ok: false, mode: 'live', message: `연결 실패: ${res.status}` };
    } catch (e) {
      return { ok: false, mode: 'live', message: e.message };
    }
  },
};
