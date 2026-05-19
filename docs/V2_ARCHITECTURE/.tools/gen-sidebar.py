#!/usr/bin/env python3
"""Generate _sidebar.md for the V2_ARCHITECTURE docsify site.

Rules:
  * ROADMAP.md is pinned at the very top.
  * Top-level .md files are grouped: numbered "Documents", then "Audits & Tasks".
  * Each PHASE_* subdirectory becomes its own section, tasks sorted by TASK number.
  * Reserved docsify files (_sidebar, _navbar, _coverpage, README, index.html) skipped.
  * File is only rewritten when content actually changes.
"""
import re
import sys
from pathlib import Path

ROOT = Path("/home/piotrszmidt/ai-gm/docs/V2_ARCHITECTURE")
RESERVED = {"_sidebar.md", "_navbar.md", "_coverpage.md", "README.md"}

ACRONYMS = {
    "DB", "MCP", "NPC", "HP", "XP", "AI", "UI", "UX", "API", "SQL",
    "JSON", "YAML", "HTTP", "HTTPS", "URL", "ID", "GM", "RNG", "MVP",
    "JWT", "CORS", "ACL", "TTS", "STT", "LLM", "RAG", "V2", "OS",
}

_DATE_RE = re.compile(r"\b(\d{4})[ _-](\d{2})[ _-](\d{2})\b")


def _smart_case(text: str) -> str:
    text = _DATE_RE.sub(r"\1-\2-\3", text)
    out = []
    for w in text.split():
        if w.upper() in ACRONYMS:
            out.append(w.upper())
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", w):
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def title_from_filename(stem: str) -> str:
    s = re.sub(r"^\d+[_-]", "", stem)
    s = re.sub(r"^TASK[_-](\d+[A-Z]?[_-])?", "", s, flags=re.I)
    s = s.replace("_", " ").strip()
    return _smart_case(s) or stem


def section_title(folder: str) -> str:
    m = re.match(r"PHASE[_-](\d+)[_-](.+)$", folder, flags=re.I)
    if m:
        return f"Phase {m.group(1)} · {_smart_case(m.group(2).replace('_', ' '))}"
    return _smart_case(folder.replace("_", " "))


def task_label(stem: str) -> str:
    m = re.match(r"TASK[_-](\d+[A-Z]?)[_-](.+)$", stem, flags=re.I)
    if m:
        return f"{m.group(1)} · {_smart_case(m.group(2).replace('_', ' '))}"
    return title_from_filename(stem)


def top_sort_key(name: str):
    m = re.match(r"^(\d+)", name)
    return (0, int(m.group(1)), name) if m else (1, 0, name)


def task_sort_key(f: Path):
    m = re.match(r"TASK[_-](\d+)([A-Z]?)", f.stem, flags=re.I)
    return (int(m.group(1)), m.group(2) or "") if m else (10_000, f.name)


def main() -> int:
    top_level: list[str] = []
    sections: dict[str, list[Path]] = {}
    for entry in sorted(ROOT.iterdir()):
        if entry.is_file() and entry.suffix == ".md" and entry.name not in RESERVED:
            top_level.append(entry.name)
        elif entry.is_dir() and not entry.name.startswith("."):
            files = [f for f in sorted(entry.glob("*.md")) if f.name not in RESERVED]
            if files:
                sections[entry.name] = files

    out: list[str] = []
    if "ROADMAP.md" in top_level:
        out += ["- [\U0001F4CD Roadmap](ROADMAP.md)", ""]
        top_level.remove("ROADMAP.md")

    top_level.sort(key=top_sort_key)
    numbered = [n for n in top_level if re.match(r"^\d+", n)]
    others = [n for n in top_level if not re.match(r"^\d+", n)]

    if numbered:
        out.append("- **Documents**")
        for n in numbered:
            out.append(f"  - [{title_from_filename(Path(n).stem)}]({n})")
        out.append("")

    if others:
        out.append("- **Audits & Tasks**")
        for n in sorted(others):
            out.append(f"  - [{title_from_filename(Path(n).stem)}]({n})")
        out.append("")

    for folder in sorted(sections.keys()):
        out.append(f"- **{section_title(folder)}**")
        for f in sorted(sections[folder], key=task_sort_key):
            out.append(f"  - [{task_label(f.stem)}]({folder}/{f.name})")
        out.append("")

    content = "\n".join(out).rstrip() + "\n"
    target = ROOT / "_sidebar.md"
    existing = target.read_text() if target.exists() else ""
    if existing == content:
        print("no change")
        return 0
    target.write_text(content)
    print(f"sidebar updated ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
