"""
wiki/ 폴더의 MD 파일을 읽어 chrome-extension/wiki_content.js를 생성합니다.
위키를 업데이트한 뒤 이 스크립트를 다시 실행하면 확장 프로그램에 반영됩니다.
"""
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).parent
WIKI_DIR = BASE_DIR / "wiki"
OUT_FILE = BASE_DIR / "chrome-extension" / "wiki_content.js"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def build():
    if not WIKI_DIR.exists():
        print("❌ wiki/ 폴더가 없습니다. 위키를 먼저 빌드해 주세요.")
        return

    pages = []
    index = WIKI_DIR / "index.md"
    if index.exists():
        pages.append(f"=== index ===\n{index.read_text(encoding='utf-8').strip()}")

    for p in sorted(WIKI_DIR.glob("*.md")):
        if p.name == "index.md":
            continue
        content = p.read_text(encoding="utf-8").strip()
        pages.append(f"=== {nfc(p.stem)} ===\n{content}")

    wiki_text = "\n\n".join(pages)
    # JS template literal 이스케이프
    wiki_text = wiki_text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    OUT_FILE.write_text(
        f"// 자동 생성 — build_extension.py 재실행 시 갱신됩니다\n"
        f"const WIKI_CONTENT = `{wiki_text}`;\n",
        encoding="utf-8",
    )
    print(f"✅ wiki_content.js 생성 완료 ({len(wiki_text):,}자, {len(pages)}개 페이지)")


if __name__ == "__main__":
    build()
