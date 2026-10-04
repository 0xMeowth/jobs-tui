import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from jobs_tui.paths import AppPaths, template_typ


class RenderError(Exception):
    pass


@dataclass
class RenderResult:
    pdf: Path
    pages: int
    previews: list[Path] = field(default_factory=list)


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


def compile(jobs: Path, p: AppPaths) -> Path:
    resume_rel = "/" + str(p.resume_yaml.relative_to(jobs))
    p.preview_dir.mkdir(exist_ok=True)
    cmd = ["typst", "compile", "--root", str(jobs), "--input", f"resume={resume_rel}", str(template_typ(jobs)), str(p.resume_pdf)]
    _run_tool(cmd)
    return p.resume_pdf


def previews(pdf: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("page-*.png"):
        old.unlink(missing_ok=True)
    _run_tool(["pdftoppm", "-r", "110", "-png", str(pdf), str(out_dir / "page")])
    return sorted(out_dir.glob("page-*.png"), key=lambda f: int(f.stem.split("-")[1]))


_render_lock = threading.Lock()  # screens render from separate workers; serialize writes to the preview dir


def render(jobs: Path, p: AppPaths) -> RenderResult:
    with _render_lock:
        pdf = compile(jobs, p)
        pages = page_count(pdf)
        return RenderResult(pdf=pdf, pages=pages, previews=previews(pdf, p.preview_dir))
