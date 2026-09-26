import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from jobs_tui import application
from jobs_tui.paths import AppPaths, template_typ

LADDER: list[dict[str, str]] = [
    {},
    {"leading": "0.45em", "section_gap": "8pt", "entry_gap": "6pt"},
    {"leading": "0.4em", "section_gap": "7pt", "entry_gap": "5pt"},
    {"leading": "0.35em", "section_gap": "6pt", "entry_gap": "4pt"},
    {"leading": "0.3em", "section_gap": "5pt", "entry_gap": "4pt"},
]


class RenderError(Exception):
    pass


@dataclass
class RenderResult:
    pdf: Path
    pages: int
    previews: list[Path] = field(default_factory=list)
    knobs: dict[str, str] = field(default_factory=dict)


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if not m:
        raise RenderError(f"pdfinfo gave no page count for {pdf}")
    return int(m.group(1))


def compile(jobs: Path, p: AppPaths, knobs: dict[str, str]) -> Path:
    resume_rel = "/" + str(p.resume_yaml.relative_to(jobs))
    cmd = ["typst", "compile", "--root", str(jobs), "--input", f"resume={resume_rel}"]
    for k, v in knobs.items():
        cmd += ["--input", f"{k}={v}"]
    cmd += [str(template_typ(jobs)), str(p.resume_pdf)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(proc.stderr.strip() or "typst failed")
    return p.resume_pdf


def previews(pdf: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("page-*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-r", "110", "-png", str(pdf), str(out_dir / "page")], check=True)
    return sorted(out_dir.glob("page-*.png"), key=lambda f: int(f.stem.split("-")[1]))


def _run(jobs: Path, p: AppPaths, knobs: dict[str, str]) -> RenderResult:
    pdf = compile(jobs, p, knobs)
    pages = page_count(pdf)
    return RenderResult(pdf=pdf, pages=pages, previews=previews(pdf, p.preview_dir), knobs=dict(knobs))


def render(jobs: Path, p: AppPaths) -> RenderResult:
    return _run(jobs, p, application.load(p).fit)


def autofit(jobs: Path, p: AppPaths) -> RenderResult:
    result = None
    for knobs in LADDER:
        result = _run(jobs, p, knobs)
        if result.pages <= 2:
            break
    app = application.load(p)
    app.fit = dict(result.knobs)
    application.save(p, app)
    return result
