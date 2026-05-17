importScripts('wiki_content.js');

const SYSTEM_PROMPT = `당신은 울산대학교 총무인사팀 업무 도우미입니다.
직원이 그룹웨어를 사용하는 도중 옆에서 도와주는 선배 동료처럼 안내하세요.

[답변 방식]
1. 현재 화면 정보를 보고 맥락에 맞게 답변하세요.
2. 신입 직원도 이해할 수 있도록 단계별로 설명하세요.
3. 짧고 실용적으로 — 핵심만 먼저, 필요하면 상세 설명 추가.
4. 친근하고 따뜻한 톤. 딱딱한 공문 말투 금지.
5. 마크다운 헤더(#, ##)는 사용하지 마세요. 강조는 **굵게**만.
6. 모르는 내용은 "총무인사팀에 직접 확인해 보세요 😊"라고 솔직하게.

[지식 베이스]
${WIKI_CONTENT}`;

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== 'CHAT') return;
  handleChat(msg).then(sendResponse).catch(e => sendResponse({ error: e.message }));
  return true;
});

async function handleChat({ history, context }) {
  const { apiKey } = await chrome.storage.local.get('apiKey');

  if (!apiKey) {
    throw new Error('API 키가 없습니다. 확장 아이콘(🌿)을 클릭해 설정해 주세요.');
  }

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
      system: `${SYSTEM_PROMPT}\n\n[현재 화면 정보]\n${context}`,
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
