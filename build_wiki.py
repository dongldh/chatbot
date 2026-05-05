#!/usr/bin/env python3
"""
위키 빌더 CLI — docs/ 폴더를 읽어 wiki/ 폴더에 위키 페이지를 생성합니다.
docs 변경 시 이 스크립트를 다시 실행하세요.

Usage: python build_wiki.py
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("오류: ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    sys.exit(1)

from wiki_builder import build_all  # noqa: E402

print("위키 빌드 시작...")
created = build_all(
    docs_dir=BASE_DIR / "docs",
    wiki_dir=BASE_DIR / "wiki",
    api_key=api_key,
)
print(f"\n완료! 총 {len(created)}개 파일 생성됨:")
for f in created:
    print(f"  wiki/{f}")
