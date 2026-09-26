import re
from dataclasses import dataclass
from pathlib import Path

HEADER = "| Submitted | Company | Role | Files | URL | Notes |\n|---|---|---|---|---|---|\n"
LINK_ANGLE = re.compile(r"\[[^\]]*\]\(<([^>]*)>\)")
LINK_BARE = re.compile(r"\[[^\]]*\]\(([^)\s]*)\)")
HEADER_LINE = re.compile(r"^\|\s*submitted", re.IGNORECASE)
SEP_LINE = re.compile(r"^\|\s*:?-+")


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


def _extract_link(s: str) -> str:
    m = LINK_ANGLE.search(s)
    if m:
        return m.group(1)
    m = LINK_BARE.search(s)
    return m.group(1) if m else ""


def _format(r: Row) -> str:
    files = f"[open](<{_esc(r.folder)}>)"
    url = f"[posting](<{_esc(r.url)}>)" if r.url else ""
    return f"| {_esc(r.submitted)} | {_esc(r.company)} | {_esc(r.role)} | {files} | {url} | {_esc(r.notes)} |\n"


def insert(path: Path, row: Row) -> None:
    text = path.read_text() if path.exists() else ""
    lines = text.splitlines(keepends=True)
    insert_at = None
    for i, line in enumerate(lines):
        if HEADER_LINE.match(line):
            if i + 1 < len(lines) and SEP_LINE.match(lines[i + 1]):
                insert_at = i + 2
            else:
                insert_at = i + 1
            break
    if insert_at is None:
        lines = list(HEADER.splitlines(keepends=True)) + lines
        insert_at = 2
    lines.insert(insert_at, _format(row))
    path.write_text("".join(lines))


def _split(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [_unesc(c) for c in cells[1:-1]]


def read(path: Path) -> list[Row]:
    if not path.exists():
        return []
    rows = []
    started = False
    for line in path.read_text().splitlines():
        if not started:
            if HEADER_LINE.match(line):
                started = True
            continue
        if SEP_LINE.match(line):
            continue
        if not line.startswith("|"):
            continue
        cells = _split(line)
        if len(cells) != 6:
            continue
        s, company, role, files, url, notes = cells
        rows.append(Row(s, company, role, _extract_link(files), _extract_link(url), notes))
    return rows
