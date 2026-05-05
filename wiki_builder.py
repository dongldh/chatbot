"""
wiki_builder.py — docs/ 폴더를 읽어 wiki/ 폴더에 구조화된 위키 페이지를 생성합니다.
build_wiki.py(CLI)와 streamlit_app.py(관리자 버튼) 양쪽에서 사용합니다.

docs/ 파일을 자동 분석하여 위키 구조를 결정하므로,
새 문서를 추가한 뒤 build_wiki.py를 다시 실행하면 자동으로 반영됩니다.
"""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
import anthropic


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _plan_wiki(client: anthropic.Anthropic, docs_dir: Path) -> list[dict]:
    """docs 파일 목록을 Claude에게 분석시켜 위키 페이지 구조를 제안받는다."""
    all_stems: list[tuple[str, str]] = []
    for path in sorted(docs_dir.glob("*.md")):
        stem = _nfc(path.stem)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        preview = " ".join(lines[:2])[:80]
        all_stems.append((stem, preview))

    stem_list = "\n".join(
        f'{i+1}. "{stem}" — {preview}'
        for i, (stem, preview) in enumerate(all_stems)
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    "아래는 docs 폴더의 파일 목록입니다. 번호와 큰따옴표 안의 파일명을 확인하세요.\n\n"
                    "[규칙]\n"
                    "- 관련 파일은 하나의 위키 페이지로 통합, 독립 주제는 별도 페이지\n"
                    "- filename은 한글_구분.md 형식\n"
                    "- sources 배열에는 큰따옴표 안의 파일명을 글자 하나도 틀리지 않고 정확히 복사\n"
                    "- instruction은 한 문장\n\n"
                    "JSON 배열만 반환 (설명 없이):\n"
                    '[{"filename":"...","title":"...","sources":["파일명 정확히"],"instruction":"..."}]\n\n'
                    f"파일 목록:\n{stem_list}"
                ),
            }
        ],
    )

    text = response.content[0].text.strip()
    match = re.search(r"\[[\s\S]*\]", text)
    raw = match.group() if match else text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON이 잘린 경우 재시도
        fix_response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": "다음 JSON을 올바르게 수정하여 완성된 JSON 배열만 반환하세요:\n" + raw},
            ],
        )
        fixed = fix_response.content[0].text.strip()
        match2 = re.search(r"\[[\s\S]*\]", fixed)
        return json.loads(match2.group() if match2 else fixed)


def _read_docs_by_stems(docs_dir: Path, stems: list[str]) -> str:
    """stems 목록에 해당하는 docs 파일을 읽어 하나의 문자열로 반환.
    정확한 일치 우선, 없으면 파일명이 stem으로 시작하는 것도 포함."""
    targets_nfc = [_nfc(s) for s in stems]
    parts: list[str] = []
    for path in sorted(docs_dir.glob("*.md")):
        stem_nfc = _nfc(path.stem)
        matched = any(
            stem_nfc == t or stem_nfc.startswith(t) or t in stem_nfc
            for t in targets_nfc
        )
        if matched:
            content = path.read_text(encoding="utf-8").strip()
            parts.append(f"=== {stem_nfc} ===\n{content}")
    return "\n\n".join(parts)


def _build_page(client: anthropic.Anthropic, title: str, doc_content: str, instruction: str) -> str:
    """Claude로 단일 위키 페이지를 생성."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    "당신은 울산대학교 총무인사팀 업무 매뉴얼 위키 편집자입니다.\n\n"
                    f"아래 원본 문서들을 바탕으로 **'{title}'** 위키 페이지를 작성하세요.\n\n"
                    f"[작성 지침]\n{instruction}\n\n"
                    "[공통 규칙]\n"
                    "- 마크다운 형식으로 작성 (## 소제목 자유롭게 사용)\n"
                    "- 단계별 절차는 번호 목록으로 표기\n"
                    "- 여러 문서 내용은 논리적 흐름으로 통합, 중복 제거\n"
                    "- 중요 주의사항은 **굵게** 표시\n"
                    "- 시스템 메뉴 경로는 `코드` 형식으로 표기\n\n"
                    f"[원본 문서]\n{doc_content}"
                ),
            }
        ],
    )
    return response.content[0].text


def _build_index(page_titles: dict[str, str]) -> str:
    """생성된 wiki 페이지 목록으로 index.md를 생성."""
    lines = ["# 위키 인덱스\n"]
    categories: dict[str, list[tuple[str, str]]] = {}
    for fname, title in sorted(page_titles.items()):
        prefix = fname.split("_")[0] if "_" in fname else fname.replace(".md", "")
        categories.setdefault(prefix, []).append((fname, title))
    for cat, items in sorted(categories.items()):
        lines.append(f"## {cat}\n")
        for fname, title in items:
            lines.append(f"- [{fname}]({fname}) — {title}")
        lines.append("")
    return "\n".join(lines)


def build_all(docs_dir: Path, wiki_dir: Path, api_key: str, log=print) -> list[str]:
    """
    docs/ 파일을 자동 분석하여 wiki 페이지를 생성하고 index.md를 작성합니다.
    생성된 파일 목록을 반환합니다.
    """
    wiki_dir.mkdir(exist_ok=True)
    client = anthropic.Anthropic(api_key=api_key)

    log("  문서 구조 분석 중...")
    plan = _plan_wiki(client, docs_dir)
    log(f"  위키 페이지 {len(plan)}개 계획됨")

    created: list[str] = []
    page_titles: dict[str, str] = {}

    for defn in plan:
        fname: str = defn["filename"]
        title: str = defn["title"]
        sources: list[str] = defn["sources"]
        instruction: str = defn["instruction"]

        log(f"  생성 중: {fname} ...")
        doc_content = _read_docs_by_stems(docs_dir, sources)
        if not doc_content.strip():
            log(f"  건너뜀 (소스 없음): {fname}")
            continue

        page_content = _build_page(client, title, doc_content, instruction)
        (wiki_dir / fname).write_text(page_content, encoding="utf-8")
        created.append(fname)
        page_titles[fname] = title
        log(f"  완료: {fname}")

    index_content = _build_index(page_titles)
    (wiki_dir / "index.md").write_text(index_content, encoding="utf-8")
    created.append("index.md")
    log("  완료: index.md")

    return created
