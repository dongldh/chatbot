document.addEventListener('DOMContentLoaded', async () => {
  const apiKeyEl    = document.getElementById('apiKey');
  const employeeEl  = document.getElementById('employeeId');
  const serverEl    = document.getElementById('serverUrl');
  const statusEl    = document.getElementById('status');
  const modeEl      = document.getElementById('modeIndicator');

  // ── 저장된 값 불러오기 ─────────────────────────────────
  const s = await chrome.storage.local.get(['apiKey', 'employeeId', 'serverUrl']);
  if (s.apiKey)     apiKeyEl.value   = s.apiKey;
  if (s.employeeId) employeeEl.value = s.employeeId;
  if (s.serverUrl)  serverEl.value   = s.serverUrl;

  updateModeIndicator(s.serverUrl);

  serverEl.addEventListener('input', () => updateModeIndicator(serverEl.value));

  // ── 저장 ──────────────────────────────────────────────
  document.getElementById('save').addEventListener('click', async () => {
    const apiKey     = apiKeyEl.value.trim();
    const employeeId = employeeEl.value.trim();
    const serverUrl  = serverEl.value.trim();

    // 유효성 검사
    if (!serverUrl && !apiKey) {
      showStatus('API 키 또는 서버 URL 중 하나는 입력해 주세요.', 'err');
      return;
    }
    if (!serverUrl && apiKey && !apiKey.startsWith('sk-ant-')) {
      showStatus('Anthropic API 키는 sk-ant-로 시작합니다.', 'err');
      return;
    }

    await chrome.storage.local.set({ apiKey, employeeId, serverUrl });
    updateModeIndicator(serverUrl);
    showStatus('✓ 저장되었습니다!', 'ok');
  });

  function updateModeIndicator(serverUrl) {
    if (serverUrl && serverUrl.trim()) {
      modeEl.textContent  = '🔌 내부 서버 모드 (DB 연동)';
      modeEl.className    = 'mode-indicator mode-server';
    } else {
      modeEl.textContent  = '☁️ Anthropic 직접 연결 모드';
      modeEl.className    = 'mode-indicator mode-direct';
    }
  }

  function showStatus(msg, cls) {
    statusEl.textContent = msg;
    statusEl.className   = 'status ' + cls;
    if (cls === 'ok') setTimeout(() => { statusEl.textContent = ''; }, 2500);
  }
});
