import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from jobs_tui import application
from jobs_tui.paths import AppPaths, template_typ

LADDER: list[dict[str, str]] = [
    {},
    {"leading": "0.6em", "section_gap": "12pt", "entry_gap": "10pt"},
    {"leading": "0.55em", "section_gap": "10pt", "entry_gap": "8pt", "margin_y": "1cm"},
    {"leading": "0.5em", "section_gap": "9pt", "entry_gap": "7pt", "margin_y": "1cm"},
    {"leading": "0.45em", "section_gap": "8pt", "entry_gap": "6pt", "margin_y": "0.9cm"},
    {"leading": "0.4em", "section_gap": "7pt", "entry_gap": "5pt", "margin_y": "0.9cm"},
]


class RenderError(Exception):
    pass


@dataclass
class RenderResult:
    pdf: Path
    pages: int
    previews: list[Path] = field(default_factory=list)
    knobs: dict[str, str] = field(default_factory=dict)


def _run_tool(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as e:
        raise RenderError(f"{cmd[0]} not found: {e}") from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise RenderError(f"{cmd[0]} failed (exit {e.returncode})" + (f": {stderr}" if stderr else "")) from e


def page_count(pdf: Path) -> int:
    out = _run_tool(["pdfinfo", str(pdf)]).stdout
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
    _run_tool(cmd)
    return p.resume_pdf


def previews(pdf: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("page-*.png"):
        old.unlink()
    _run_tool(["pdftoppm", "-r", "110", "-png", str(pdf), str(out_dir / "page")])
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
