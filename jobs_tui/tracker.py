import re
from dataclasses import dataclass
from pathlib import Path

HEADER = "| Submitted | Company | Role | Files | URL | Notes |\n|---|---|---|---|---|---|\n"
LINK = re.compile(r"\[[^\]]*\]\(([^)]*)\)")


@dataclass
class Row:
    submitted: str
    company: str
    role: str
    folder: str
    url: str
    notes: str


def _esc(s: str) -> str:
    return s.replace("|", r"\|")


def _unesc(s: str) -> str:
    return s.replace(r"\|", "|").strip()


def _format(r: Row) -> str:
    files = f"[open]({r.folder})"
    url = f"[posting]({r.url})" if r.url else ""
    return f"| {_esc(r.submitted)} | {_esc(r.company)} | {_esc(r.role)} | {files} | {url} | {_esc(r.notes)} |\n"


def insert(path: Path, row: Row) -> None:
    text = path.read_text() if path.exists() else HEADER
    if not text.startswith(HEADER):
        text = HEADER + text
    path.write_text(text[: len(HEADER)] + _format(row) + text[len(HEADER):])


def _split(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [_unesc(c) for c in cells[1:-1]]


def read(path: Path) -> list[Row]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines()[2:]:
        if not line.startswith("|"):
            continue
        s, company, role, files, url, notes = _split(line)
        folder = (LINK.search(files) or [None, ""])[1]
        link = LINK.search(url)
        rows.append(Row(s, company, role, folder, link.group(1) if link else "", notes))
    return rows
