from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
import streamlit as st
import anthropic
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

DOCS_DIR = BASE_DIR / "docs"
MAX_HISTORY = 10

st.set_page_config(page_title="울산대학교 총무인사팀 챗봇", page_icon="🌿", layout="centered")

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, sans-serif !important;
}

/* 전체 배경 */
.stApp { background: #F5F7F5; }

/* 헤더 카드 */
.toss-header {
    background: #ffffff;
    border-radius: 24px;
    padding: 28px 32px;
    margin-bottom: 20px;
    box-shadow: 0 2px 16px rgba(0,168,107,0.08);
    display: flex;
    align-items: center;
    gap: 16px;
}
.toss-header .icon {
    width: 52px; height: 52px;
    background: #E8F8F2;
    border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    font-size: 26px; flex-shrink: 0;
}
.toss-header h1 {
    font-size: 20px; font-weight: 700;
    color: #191F28; margin: 0;
}
.toss-header p {
    font-size: 13px; color: #8B95A1;
    margin: 4px 0 0;
}

/* 채팅 메시지 */
[data-testid="stChatMessage"] {
    background: #ffffff !important;
    border-radius: 20px !important;
    padding: 16px !important;
    margin: 6px 0 !important;
    box-shadow: 0 1px 8px rgba(0,0,0,0.05) !important;
    border: none !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: #E8F8F2 !important;
}

/* 아바타 */
[data-testid="chatAvatarIcon-assistant"] > * {
    background: #00A86B !important;
    border-radius: 12px !important;
}
[data-testid="chatAvatarIcon-user"] > * {
    background: #4CAF82 !important;
    border-radius: 12px !important;
}
[data-testid="chatAvatarIcon-assistant"] svg,
[data-testid="chatAvatarIcon-user"] svg {
    fill: #ffffff !important;
}

/* 입력창 */
[data-testid="stChatInput"] {
    background: #ffffff;
    border-radius: 20px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border: 1.5px solid #E4EDE8 !important;
    padding: 4px 8px;
}
[data-testid="stChatInput"] textarea {
    border: none !important;
    background: transparent !important;
    font-size: 15px !important;
}
[data-testid="stChatInput"] button {
    background: #00A86B !important;
    border-radius: 12px !important;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #EEF2EE;
}
[data-testid="stSidebar"] .stTextInput input {
    border-radius: 12px !important;
    border: 1.5px solid #E4EDE8 !important;
}

/* 버튼 */
.stButton button {
    border-radius: 12px !important;
    font-weight: 600 !important;
}

/* divider */
hr { border-color: #EEF2EE !important; }

/* 채팅 내 헤더 크기 일반 텍스트로 고정 */
[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3,
[data-testid="stChatMessage"] h4 {
    font-size: 15px !important;
    font-weight: 600 !important;
    margin: 4px 0 !important;
}
</style>

<div class="toss-header">
    <div class="icon">🌿</div>
    <div>
        <h1>울산대학교 총무인사팀 챗봇</h1>
        <p>궁금한 점을 질문해 주세요. 빠르게 안내해 드리겠습니다.</p>
    </div>
</div>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_docs() -> str:
    """전체 MD 파일을 하나의 문자열로 합침 (캐싱)."""
    parts = []
    for path in sorted(DOCS_DIR.glob("**/*.md")):
        rel = path.relative_to(DOCS_DIR)
        content = path.read_text(encoding="utf-8").strip()
        parts.append(f"=== {rel} ===\n{content}")
    return "\n\n".join(parts)


def build_system_prompt() -> str:
    docs = load_docs()
    return f"""당신은 울산대학교 총무인사팀의 FAQ 챗봇입니다. 아래 문서를 바탕으로 질문에 답변하세요.

[답변 규칙]
1. 친절하지만 간결하게 답변하세요. 불필요한 설명은 생략합니다.
2. 문서에 없는 내용은 "죄송합니다, 해당 내용은 제가 알고 있는 범위를 벗어납니다."라고 솔직하게 말하세요.
3. 모든 답변 마지막에 짧은 인사로 마무리하세요. (예: "도움이 되셨길 바랍니다 😊", "좋은 하루 되세요!", "언제든지 질문해 주세요!")
4. 문서에 없거나 추가 확인이 필요한 경우, "자세한 사항은 총무인사팀으로 Teams 메시지를 보내주시면 안내해 드리겠습니다."라고 안내하세요.
5. 답변에 #, ##, ### 등 마크다운 헤더를 절대 사용하지 마세요. 제목이나 강조가 필요하면 **굵은 글씨**만 사용하세요.

---
{docs}
---"""


@st.cache_resource(show_spinner=False)
def get_sheet():
    """Google Sheets 연결 (1회 캐싱)."""
    creds_dict = dict(st.secrets.get("gcp_service_account", {}))
    if not creds_dict:
        return None
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sheet_url = st.secrets.get("SHEET_URL", "")
    return gc.open_by_url(sheet_url).sheet1


def log_to_sheets(question: str, answer: str):
    """질문/답변을 Google Sheets에 기록."""
    try:
        sheet = get_sheet()
        if sheet is None:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, question, answer])
    except Exception:
        pass


def get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    return anthropic.Anthropic(api_key=api_key)


# 사이드바 - 관리자 문서 관리
with st.sidebar:
    st.header("📂 문서 관리")
    pw = st.text_input("관리자 비밀번호", type="password")
    admin_pw = st.secrets.get("ADMIN_PASSWORD", "")

    if pw == admin_pw and pw != "":
        uploaded = st.file_uploader("MD 파일 업로드", type=["md"], accept_multiple_files=True)
        if uploaded:
            for f in uploaded:
                save_path = DOCS_DIR / f.name
                save_path.write_bytes(f.read())
            load_docs.clear()
            st.success(f"{len(uploaded)}개 파일 저장됨")
            st.rerun()

        st.divider()
        files = sorted(DOCS_DIR.glob("**/*.md"))
        st.caption(f"현재 문서 {len(files)}개")
        for f in files:
            col1, col2 = st.columns([4, 1])
            col1.text(f.name)
            if col2.button("삭제", key=f.name):
                f.unlink()
                load_docs.clear()
                st.rerun()
        st.divider()
        if st.button("📊 질문 로그 보기"):
            sheet = get_sheet()
            if sheet:
                rows = sheet.get_all_values()
                if len(rows) > 1:
                    import pandas as pd
                    df = pd.DataFrame(rows[1:], columns=["시간", "질문", "답변"])
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("아직 기록된 질문이 없습니다.")
    elif pw != "":
        st.error("비밀번호가 틀렸습니다")

# 채팅
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    history = st.session_state.messages[-MAX_HISTORY:]

    with st.chat_message("assistant"):
        client = get_client()

        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": build_system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=history,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        ) as stream:
            response_text = st.write_stream(
                chunk for chunk in stream.text_stream
            )

    st.session_state.messages.append({"role": "assistant", "content": response_text})
    log_to_sheets(prompt, response_text)
