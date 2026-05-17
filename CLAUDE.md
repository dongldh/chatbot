# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

울산대학교 총무인사팀 FAQ 챗봇. Streamlit 기반 단일 파일 앱(`streamlit_app.py`)으로, 사내 업무 매뉴얼(MD 파일)을 RAG로 검색하여 Claude가 답변합니다.

## 실행 명령

```bash
# 앱 실행
streamlit run streamlit_app.py

# 의존성 설치
pip install -r requirements.txt
```

## 필수 환경 변수 / 시크릿

`.env` 파일에 API 키 저장:
- `ANTHROPIC_API_KEY` — Claude 호출용
- `OPENAI_API_KEY` — 임베딩(text-embedding-3-small) 생성용

`.streamlit/secrets.toml`에 저장:
- `gcp_service_account` — Google Sheets 로깅용 서비스 계정 JSON
- `SHEET_URL` — 질문 로그를 기록할 Google Sheets URL
- `ADMIN_PASSWORD` — 사이드바 문서 관리 기능 잠금 비밀번호

## 아키텍처

```
streamlit_app.py          # 앱 전체 (단일 파일)
docs/                     # 챗봇 지식 소스 — MD 파일들
index.npz                 # 임베딩 디스크 캐시 (자동 생성, git 제외)
.streamlit/
  config.toml             # 테마 설정 (primaryColor #00A86B)
  secrets.toml            # 시크릿 (git 제외)
```

### 핵심 흐름

1. **인덱스 구축** (`build_index`): 앱 시작 시 `docs/` 내 모든 MD 파일을 `##` 섹션 단위로 청크 분리 → OpenAI 임베딩 생성 → `index.npz`에 캐시. 이미 캐시가 있으면 로드만 함.

2. **RAG 검색** (`retrieve_cached`): 사용자 질문을 임베딩하여 코사인 유사도로 상위 6개 청크 반환. 동일 질문은 24시간 캐싱.

3. **답변 생성**: `claude-haiku-4-5-20251001` 모델 사용. 시스템 프롬프트(`SYSTEM_INSTRUCTIONS`)에 `cache_control: ephemeral`을 적용해 프롬프트 캐싱 활성화. 답변은 스트리밍으로 출력.

4. **로깅**: 모든 질문/답변을 Google Sheets에 타임스탬프와 함께 기록.

### 문서 관리 (관리자)

사이드바에서 비밀번호 입력 후:
- MD 파일 업로드/삭제
- 인덱스 재구축 버튼 (`_rebuild_index`: `index.npz` 삭제 + 캐시 초기화)
- Google Sheets 질문 로그 조회

## 문서 추가 시 주의사항

- `docs/` 에 MD 파일을 추가한 뒤 **반드시 인덱스 재구축** 필요 (`index.npz` 삭제 또는 관리자 페이지에서 재구축)
- 청크는 `##` 헤더 기준으로 분리되며 80자 미만 섹션은 제외됨
- 답변에서 마크다운 헤더(`#`, `##` 등) 사용 금지 — `SYSTEM_INSTRUCTIONS`에 명시됨

## 모델 / 의존성

- LLM: `claude-haiku-4-5-20251001` (Anthropic)
- 임베딩: `text-embedding-3-small` (OpenAI)
- UI: Streamlit ≥ 1.35, 테마는 `.streamlit/config.toml`에서 관리
