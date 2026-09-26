import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from jobs_tui.jd import CHROME
from jobs_tui.paths import master_yaml, template_typ


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _typst_fonts() -> str:
    try:
        return subprocess.run(["typst", "fonts"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return ""


def run(jobs: Path) -> list[Check]:
    checks = []
    hints = {
        "typst": "brew install typst, or download the release binary from https://github.com/typst/typst/releases into ~/.local/bin",
        "pdfinfo": "brew install poppler",
        "pdftoppm": "brew install poppler",
    }
    for tool, hint in hints.items():
        path = shutil.which(tool)
        checks.append(Check(tool, path is not None, path or hint))
    checks.append(Check("chrome", Path(CHROME).exists(), CHROME if Path(CHROME).exists() else "install Google Chrome (browser tier of JD import)", required=False))
    herdr = shutil.which("herdr")
    checks.append(Check("herdr", herdr is not None and os.environ.get("HERDR_ENV") == "1",
                        "running inside herdr" if os.environ.get("HERDR_ENV") == "1" else "not inside herdr; prompts will be copied to the clipboard", required=False))
    nunito = "nunito" in _typst_fonts().lower()
    checks.append(Check("nunito", nunito, "font found" if nunito else "brew install --cask font-nunito"))
    ok = template_typ(jobs).exists() and master_yaml(jobs).exists()
    checks.append(Check("template", ok, str(jobs / "templates") if ok else f"run: jobs-tui init  (JOBS_DIR={jobs})"))
    return checks
