from __future__ import annotations
import os
import re
from datetime import datetime
from pathlib import Path
import streamlit as st
import anthropic
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

DOCS_DIR = BASE_DIR / "docs"
MAX_HISTORY = 10
TOP_K_CHUNKS = 4

st.set_page_config(page_title="울산대학교 총무인사팀 챗봇", page_icon="💬")
st.title("💬 울산대학교 총무인사팀 챗봇")
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
    return f"""당신은 회사 총무인사팀의 FAQ 챗봇입니다. 아래 관련 문서를 바탕으로 질문에 답변하세요.

[답변 규칙]
1. 친절하지만 간결하게 답변하세요. 불필요한 설명은 생략합니다.
2. 문서에 없는 내용은 "죄송합니다, 해당 내용은 제가 알고 있는 범위를 벗어납니다."라고 솔직하게 말하세요.
3. 모든 답변 마지막에 짧은 인사로 마무리하세요. (예: "도움이 되셨길 바랍니다 😊", "좋은 하루 되세요!", "언제든지 질문해 주세요!")
4. 문서에 없거나 추가 확인이 필요한 경우, "자세한 사항은 총무인사팀으로 Teams 메시지를 보내주시면 안내해 드리겠습니다."라고 안내하세요.

---
{context}
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
    log_to_sheets(prompt, response_text)
