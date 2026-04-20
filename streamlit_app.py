import os
from pathlib import Path
import streamlit as st
import anthropic
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

DOCS_DIR = BASE_DIR / "docs"

st.set_page_config(page_title="FAQ 챗봇", page_icon="💬")
st.title("💬 FAQ 챗봇")
st.caption("궁금한 점을 물어보세요")


def load_docs() -> str:
    parts = []
    for path in sorted(DOCS_DIR.glob("**/*.md")):
        rel = path.relative_to(DOCS_DIR)
        content = path.read_text(encoding="utf-8").strip()
        parts.append(f"=== {rel} ===\n{content}")
    return "\n\n".join(parts)


def get_system_prompt() -> str:
    docs = load_docs()
    return f"""당신은 회사 FAQ 챗봇입니다. 아래 문서를 바탕으로 질문에 답변하세요.

문서에 없는 내용은 "해당 내용은 문서에서 찾을 수 없습니다."라고 솔직하게 답하세요.
답변은 한국어로, 친절하고 간결하게 해주세요.

---
{docs}
---"""


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
                st.rerun()
    elif pw != "":
        st.error("비밀번호가 틀렸습니다")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        client = get_client()
        response_text = ""

        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=get_system_prompt(),
            messages=st.session_state.messages,
        ) as stream:
            response_text = st.write_stream(
                chunk for chunk in stream.text_stream
            )

    st.session_state.messages.append({"role": "assistant", "content": response_text})
