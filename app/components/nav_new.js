/**
 * CMC Health Screening Platform v1.0
 * app/components/nav_new.js — 공통 네비게이션 주입
 */
'use strict';

const CMC_Nav = {
  /** page: 'dashboard' | 'reservation' | 'admin' */
  render(page) {
    const links = [
      { id: 'dashboard',   href: 'admin_dashboard_new.html',    label: '📊 대시보드' },
      { id: 'reservation', href: 'reservation_new.html',        label: '📋 예약신청' },
      { id: 'admin',       href: 'admin_reservations_new.html', label: '📁 예약관리' },
    ];

    const navHTML = `
      <header class="site-header">
        <div class="header-inner">
          <div class="header-logo">🏥</div>
          <div class="header-title">
            <h1>천안의료원 건강검진센터</h1>
            <p class="header-sub">CMC Health Screening Platform v1.0</p>
          </div>
          <nav class="header-nav">
            ${links.map(l => `<a href="${l.href}" class="${l.id === page ? 'active' : ''}">${l.label}</a>`).join('')}
          </nav>
          <button class="hamburger" id="navToggle" aria-label="메뉴">☰</button>
        </div>
        <div class="mobile-nav" id="mobileNav">
          ${links.map(l => `<a href="${l.href}" class="${l.id === page ? 'active' : ''}">${l.label}</a>`).join('')}
        </div>
      </header>`;

    document.body.insertAdjacentHTML('afterbegin', navHTML);

    document.getElementById('navToggle')?.addEventListener('click', () => {
      document.getElementById('mobileNav')?.classList.toggle('open');
    });
  },
};
