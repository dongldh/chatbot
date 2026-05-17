document.addEventListener('DOMContentLoaded', async () => {
  const keyInput = document.getElementById('apiKey');
  const statusEl = document.getElementById('status');

  const { apiKey } = await chrome.storage.local.get('apiKey');
  if (apiKey) {
    keyInput.value = apiKey;
    statusEl.textContent = '✓ API 키가 설정되어 있습니다';
    statusEl.className = 'status ok';
  }

  document.getElementById('save').addEventListener('click', async () => {
    const key = keyInput.value.trim();
    if (!key) {
      show('API 키를 입력해 주세요.', 'err');
      return;
    }
    if (!key.startsWith('sk-ant-')) {
      show('Anthropic API 키는 sk-ant- 로 시작합니다.', 'err');
      return;
    }
    await chrome.storage.local.set({ apiKey: key });
    show('✓ 저장되었습니다!', 'ok');
  });

  function show(msg, cls) {
    statusEl.textContent = msg;
    statusEl.className = 'status ' + cls;
  }
});
