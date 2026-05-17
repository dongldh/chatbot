importScripts('wiki_content.js');

const SYSTEM_PROMPT = `당신은 울산대학교 총무인사팀 업무 도우미입니다.
직원이 그룹웨어를 사용하는 도중 옆에서 도와주는 선배 동료처럼 안내하세요.

[답변 방식]
1. 현재 화면 정보와 직원 개인정보(부서, 예산 등)를 함께 고려해 맥락에 맞게 답변하세요.
2. 개인화된 정보가 있으면 반드시 활용하세요. (예: "○○부서는 □□ 예산코드를 사용하시면 됩니다")
3. 신입 직원도 이해할 수 있도록 단계별로 설명하세요.
4. 짧고 실용적으로 — 핵심만 먼저, 필요하면 상세 설명 추가.
5. 친근하고 따뜻한 톤. 딱딱한 공문 말투 금지.
6. 마크다운 헤더(#, ##)는 사용하지 마세요. 강조는 **굵게**만.
7. 모르는 내용은 "총무인사팀에 직접 확인해 보세요 😊"라고 솔직하게.

[지식 베이스]
${WIKI_CONTENT}`;

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== 'CHAT') return;
  handleChat(msg).then(sendResponse).catch(e => sendResponse({ error: e.message }));
  return true;
});

async function handleChat({ history, context }) {
  const settings = await chrome.storage.local.get(['apiKey', 'serverUrl', 'employeeId']);

  // ── Phase 2: 내부 서버 모드 (DB 연동) ─────────────────
  if (settings.serverUrl && settings.serverUrl.trim()) {
    return callInternalServer(settings.serverUrl.trim(), {
      history,
      context,
      employeeId: settings.employeeId || '',
    });
  }

  // ── Phase 1: Anthropic 직접 호출 ──────────────────────
  if (!settings.apiKey) {
    throw new Error('API 키가 없습니다. 확장 아이콘(🌿)을 클릭해 설정해 주세요.');
  }
  return callAnthropic(settings.apiKey, history, context, settings.employeeId || '');
}

// ── Anthropic 직접 호출 ───────────────────────────────────
async function callAnthropic(apiKey, history, context, employeeId) {
  const userTag = employeeId ? `[사용자 사번: ${employeeId}]` : '';
  const system = `${SYSTEM_PROMPT}\n\n[현재 화면 정보]\n${context}${userTag ? '\n' + userTag : ''}`;

  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 1024,
      system,
      messages: history,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error?.message || `API 오류 (${resp.status})`);
  }

  const data = await resp.json();
  return { text: data.content[0].text };
}

// ── 내부 서버 호출 (Phase 2) ─────────────────────────────
async function callInternalServer(serverUrl, { history, context, employeeId }) {
  const url = serverUrl.replace(/\/$/, '') + '/chat';

  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ history, context, employee_id: employeeId }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `서버 오류 (${resp.status})`);
  }

  return resp.json();
}
