(function () {
  'use strict';
  if (document.getElementById('uu-helper')) return;

  // ─── Inject HTML ──────────────────────────────────────
  const el = document.createElement('div');
  el.id = 'uu-helper';
  el.className = 'uu-closed';
  el.innerHTML = `
    <button id="uu-toggle" title="업무 도우미">
      🌿
      <span id="uu-badge"></span>
    </button>
    <div id="uu-panel">
      <div id="uu-header">
        <span id="uu-title">🌿 업무 도우미</span>
        <button id="uu-close">✕</button>
      </div>
      <div id="uu-context-bar">현재 페이지를 분석 중...</div>
      <div id="uu-messages"></div>
      <div id="uu-input-row">
        <textarea id="uu-input" placeholder="궁금한 점을 물어보세요..." rows="1"></textarea>
        <button id="uu-send">↑</button>
      </div>
    </div>
  `;
  document.body.appendChild(el);

  const widget     = document.getElementById('uu-helper');
  const badge      = document.getElementById('uu-badge');
  const contextBar = document.getElementById('uu-context-bar');
  const messages   = document.getElementById('uu-messages');
  const input      = document.getElementById('uu-input');
  const send       = document.getElementById('uu-send');

  let history = [];
  let currentContext = '';
  let isOpen = false;

  // ─── Page context reader ──────────────────────────────
  function readContext() {
    const title = document.title.replace(/[-|].*$/, '').trim();
    const url   = location.href;

    // 메뉴/경로 감지 (그룹웨어 공통 패턴)
    const nav = [];
    document.querySelectorAll(
      '.breadcrumb li, .location span, .gnb .on, .lnb .on, ' +
      '[class*="depth"] .on, [class*="menu"] .active, .tab.on'
    ).forEach(e => {
      const t = e.textContent.trim();
      if (t && t.length < 30 && !nav.includes(t)) nav.push(t);
    });

    // 화면의 폼 필드 레이블
    const fields = [];
    document.querySelectorAll('label, th, .form-tit, .field-name').forEach(e => {
      const t = e.textContent.trim();
      if (t && t.length < 25 && !fields.includes(t)) fields.push(t);
    });

    // 알림/주요 텍스트 (그룹웨어 공통)
    const alerts = [];
    document.querySelectorAll('.alarm-list li, .notice-list li, [class*="alert"]').forEach(e => {
      const t = e.textContent.trim().substring(0, 60);
      if (t) alerts.push(t);
    });

    // 본문 텍스트 (제한)
    const body = (document.querySelector('main, #content, .content, #wrap') || document.body)
      .innerText.replace(/\s+/g, ' ').trim().substring(0, 600);

    return { title, url, nav: nav.slice(0, 4), fields: fields.slice(0, 8), alerts: alerts.slice(0, 3), body };
  }

  function ctxToString(c) {
    let s = `현재 페이지: ${c.title || '(알 수 없음)'}`;
    if (c.nav.length)    s += `\n메뉴 경로: ${c.nav.join(' > ')}`;
    if (c.fields.length) s += `\n화면 항목: ${c.fields.join(', ')}`;
    if (c.alerts.length) s += `\n알림: ${c.alerts.join(' / ')}`;
    s += `\n화면 내용: ${c.body.substring(0, 400)}`;
    return s;
  }

  function updateContextBar() {
    const c = readContext();
    currentContext = ctxToString(c);
    const label = c.nav.length ? c.nav.join(' > ') : (c.title || location.pathname);
    contextBar.textContent = '📍 ' + label;
    return c;
  }

  // ─── Message helpers ──────────────────────────────────
  function appendMsg(role, text) {
    const d = document.createElement('div');
    d.className = 'uu-msg uu-msg-' + role;
    d.textContent = text;
    messages.appendChild(d);
    messages.scrollTop = messages.scrollHeight;
    return d;
  }

  // ─── Open / Close ─────────────────────────────────────
  document.getElementById('uu-toggle').addEventListener('click', () => {
    isOpen = !isOpen;
    widget.classList.toggle('uu-open', isOpen);
    widget.classList.toggle('uu-closed', !isOpen);
    badge.classList.remove('show');

    if (isOpen) {
      const c = updateContextBar();
      if (messages.children.length === 0) {
        const greeting = c.nav.length
          ? `안녕하세요! 지금 **${c.nav[c.nav.length - 1]}** 화면을 보고 계시네요.\n궁금한 점이나 작성 방법을 물어보세요 😊`
          : `안녕하세요! 업무 도우미입니다. 궁금한 점을 편하게 물어보세요 😊`;
        appendMsg('assistant', greeting);
      }
      setTimeout(() => input.focus(), 50);
    }
  });

  document.getElementById('uu-close').addEventListener('click', () => {
    isOpen = false;
    widget.classList.remove('uu-open');
    widget.classList.add('uu-closed');
  });

  // ─── Send message ─────────────────────────────────────
  async function sendMessage() {
    const text = input.value.trim();
    if (!text || send.disabled) return;

    input.value = '';
    input.style.height = 'auto';
    appendMsg('user', text);

    updateContextBar();
    history.push({ role: 'user', content: text });
    if (history.length > 10) history = history.slice(-10);

    const typing = appendMsg('assistant', '');
    typing.classList.add('uu-streaming');
    send.disabled = true;

    try {
      const res = await chrome.runtime.sendMessage({
        type: 'CHAT',
        history: history.slice(),
        context: currentContext,
      });

      typing.classList.remove('uu-streaming');

      if (res.error) {
        typing.textContent = '⚠️ ' + res.error;
      } else {
        typing.textContent = res.text;
        history.push({ role: 'assistant', content: res.text });
      }
    } catch (e) {
      typing.classList.remove('uu-streaming');
      typing.textContent = '⚠️ 연결 오류. 확장 아이콘을 클릭해 API 키를 확인해 주세요.';
    }

    send.disabled = false;
    messages.scrollTop = messages.scrollHeight;
  }

  send.addEventListener('click', sendMessage);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 80) + 'px';
  });

  // ─── Page change detection (SPA 대응) ─────────────────
  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      if (isOpen) {
        updateContextBar();
        appendMsg('system', '── 페이지가 변경되었습니다 ──');
      } else {
        badge.classList.add('show');
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
})();
