from __future__ import annotations
import os
import re
from pathlib import Path
import streamlit as st
import anthropic
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

DOCS_DIR = BASE_DIR / "docs"
MAX_HISTORY = 10
TOP_K_CHUNKS = 4

st.set_page_config(page_title="FAQ 챗봇", page_icon="💬")
st.title("💬 FAQ 챗봇")
st.caption("궁금한 점을 물어보세요")


def split_chunks(text: str, source: str) -> list[dict]:
    """MD 파일을 헤더 기준으로 청크 분할."""
    chunks = []
    current = []
    for line in text.splitlines():
        if re.match(r"^#{1,3} ", line) and current:
            chunks.append({"text": "\n".join(current), "source": source})
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append({"text": "\n".join(current), "source": source})
    return [c for c in chunks if len(c["text"].strip()) > 20]


@st.cache_resource(show_spinner=False)
def load_index():
    """청크 로드 + TF-IDF 학습 (앱 시작 시 1회만 실행)."""
    chunks = []
    for path in sorted(DOCS_DIR.glob("**/*.md")):
        rel = str(path.relative_to(DOCS_DIR))
        content = path.read_text(encoding="utf-8").strip()
        chunks.extend(split_chunks(content, rel))
    if not chunks:
        return [], None, None
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    tfidf_matrix = vectorizer.fit_transform(texts)
    return chunks, vectorizer, tfidf_matrix


def retrieve(query: str, top_k: int = TOP_K_CHUNKS) -> str:
    """TF-IDF로 질문과 가장 관련 높은 청크 반환."""
    chunks, vectorizer, tfidf_matrix = load_index()
    if not chunks:
        return "관련 문서가 없습니다."
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, tfidf_matrix)[0]
    top_idx = scores.argsort()[::-1][:top_k]
    selected = [f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top_idx if scores[i] > 0]
    return "\n\n---\n\n".join(selected) if selected else "관련 문서를 찾을 수 없습니다."


def build_system_prompt(context: str) -> str:
    return f"""당신은 회사 FAQ 챗봇입니다. 아래 관련 문서를 바탕으로 질문에 답변하세요.

문서에 없는 내용은 "해당 내용은 문서에서 찾을 수 없습니다."라고 솔직하게 답하세요.
답변은 한국어로, 친절하고 간결하게 해주세요.

---
{context}
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
            load_index.clear()
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
                load_index.clear()
                st.rerun()
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

    # 히스토리 최근 10개 유지
    history = st.session_state.messages[-MAX_HISTORY:]

    # RAG: 관련 청크 검색
    context = retrieve(prompt)
    system_prompt = build_system_prompt(context)

    with st.chat_message("assistant"):
        client = get_client()

        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=history,
        ) as stream:
            response_text = st.write_stream(
                chunk for chunk in stream.text_stream
            )

    st.session_state.messages.append({"role": "assistant", "content": response_text})
