"""
api_server.py — 크롬 확장 Phase 2 내부 API 서버

역할: 사번으로 DB 조회 → 개인화 컨텍스트 생성 → Claude 호출 → 응답 반환

실행:
  pip install fastapi uvicorn anthropic python-dotenv
  python api_server.py

Mac/Windows 공통. 기본 포트: 8000
"""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Any

import anthropic
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 환경 설정 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

app = FastAPI(title="울산대학교 업무 도우미 API", version="1.0")

# Chrome 확장에서 오는 요청 허용 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 운영 시 특정 도메인으로 제한 권장
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── 위키 로드 ──────────────────────────────────────────────
def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def load_wiki() -> str:
    wiki_dir = BASE_DIR / "wiki"
    if not wiki_dir.exists():
        return ""
    pages = []
    idx = wiki_dir / "index.md"
    if idx.exists():
        pages.append(f"=== index ===\n{idx.read_text(encoding='utf-8').strip()}")
    for p in sorted(wiki_dir.glob("*.md")):
        if p.name == "index.md":
            continue
        pages.append(f"=== {_nfc(p.stem)} ===\n{p.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(pages)

WIKI_CONTENT = load_wiki()

SYSTEM_PROMPT = f"""당신은 울산대학교 총무인사팀 업무 도우미입니다.
직원이 그룹웨어를 사용하는 도중 옆에서 도와주는 선배 동료처럼 안내하세요.

[답변 방식]
1. 직원의 부서·예산 정보 등 개인화 데이터가 있으면 반드시 활용해 구체적으로 답하세요.
   예) "○○부서는 □□ 예산코드를 사용하시면 됩니다"
2. 신입 직원도 이해할 수 있도록 단계별로 설명하세요.
3. 짧고 실용적으로 — 핵심 먼저, 필요하면 상세 추가.
4. 친근하고 따뜻한 톤. 마크다운 헤더(#, ##) 사용 금지.
5. 모르는 내용은 "총무인사팀에 직접 확인해 보세요 😊"

[지식 베이스]
{WIKI_CONTENT}"""


# ── 요청/응답 모델 ─────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    history: list[Message]
    context: str
    employee_id: str = ""


# ── DB 조회 함수 (여기에 실제 DB 연결 구현) ───────────────
def get_employee_info(employee_id: str) -> dict[str, Any]:
    """
    사번으로 직원 정보를 DB에서 조회합니다.

    [구현 방법 — 전산팀과 협의 후 아래 중 선택]

    # SQLite (테스트용):
    # import sqlite3
    # conn = sqlite3.connect("employees.db")
    # row = conn.execute(
    #     "SELECT name, dept, budget_code, team FROM employees WHERE id = ?",
    #     [employee_id]
    # ).fetchone()
    # return {"name": row[0], "dept": row[1], "budget_code": row[2], "team": row[3]}

    # MySQL/MariaDB:
    # import mysql.connector
    # conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    # cursor = conn.cursor(dictionary=True)
    # cursor.execute("SELECT * FROM employees WHERE employee_id = %s", [employee_id])
    # return cursor.fetchone() or {}

    # MS SQL Server (학교 시스템에 많이 사용):
    # import pyodbc
    # conn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_HOST};...")
    # cursor = conn.cursor()
    # cursor.execute("SELECT * FROM TB_EMPLOYEE WHERE EMP_NO = ?", employee_id)
    # row = cursor.fetchone()
    # return dict(zip([col[0] for col in cursor.description], row)) if row else {}
    """

    # ── 임시 샘플 데이터 (실제 DB 연결 전 테스트용) ────────
    SAMPLE_DB = {
        "202401001": {
            "name": "김대현",
            "dept": "총무인사팀",
            "team": "인사",
            "budget_code": "A001",
            "budget_desc": "총무인사팀 운영비",
            "position": "팀장",
        },
        "202401002": {
            "name": "이정환",
            "dept": "총무인사팀",
            "team": "채용",
            "budget_code": "A001",
            "budget_desc": "총무인사팀 운영비",
            "position": "담당자",
        },
        "202301010": {
            "name": "홍길동",
            "dept": "산학협력단",
            "team": "사업관리",
            "budget_code": "B205",
            "budget_desc": "산학협력단 사업비",
            "position": "연구원",
            "note": "사업단 예산 사용 시 별도 품의 필요",
        },
    }
    return SAMPLE_DB.get(employee_id, {})


def build_employee_context(info: dict[str, Any]) -> str:
    """직원 정보를 Claude 컨텍스트 문자열로 변환."""
    if not info:
        return ""
    lines = ["[직원 개인화 정보]"]
    if info.get("name"):   lines.append(f"이름: {info['name']}")
    if info.get("dept"):   lines.append(f"부서: {info['dept']}")
    if info.get("team"):   lines.append(f"팀: {info['team']}")
    if info.get("position"): lines.append(f"직급: {info['position']}")
    if info.get("budget_code"):
        lines.append(f"예산코드: {info['budget_code']} ({info.get('budget_desc', '')})")
    if info.get("note"):   lines.append(f"특이사항: {info['note']}")
    return "\n".join(lines)


# ── 엔드포인트 ─────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "service": "울산대학교 업무 도우미 API"}


@app.post("/chat")
def chat(req: ChatRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="서버에 ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    # 직원 정보 조회
    employee_info = get_employee_info(req.employee_id) if req.employee_id else {}
    employee_ctx  = build_employee_context(employee_info)

    # 시스템 프롬프트 조합
    system = SYSTEM_PROMPT
    system += f"\n\n[현재 화면 정보]\n{req.context}"
    if employee_ctx:
        system += f"\n\n{employee_ctx}"

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system,
        messages=[m.model_dump() for m in req.history],
    )

    return {"text": response.content[0].text}


# ── 실행 ───────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"\n🌿 업무 도우미 API 서버 시작")
    print(f"   주소: http://localhost:{port}")
    print(f"   위키: {len(WIKI_CONTENT):,}자 로드됨")
    print(f"   종료: Ctrl+C\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
