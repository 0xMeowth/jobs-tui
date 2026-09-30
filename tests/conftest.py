import shutil
from pathlib import Path

import pytest

ASSETS = Path(__file__).resolve().parents[1] / "jobs_tui" / "assets"
SAMPLE = Path(__file__).resolve().parent / "fixtures" / "resume-sample.yaml"


@pytest.fixture
def jobs_dir(tmp_path, monkeypatch) -> Path:
    jobs = tmp_path / "jobs"
    (jobs / "templates").mkdir(parents=True)
    (jobs / "companies").mkdir()
    if (ASSETS / "resume.typ").exists():
        shutil.copy(ASSETS / "resume.typ", jobs / "templates" / "resume.typ")
    shutil.copy(SAMPLE, jobs / "templates" / "resume-master.yaml")
    monkeypatch.setenv("JOBS_DIR", str(jobs))
    monkeypatch.setenv("HERDR_ENV", "0")
    from jobs_tui.app import JobsApp
    monkeypatch.setattr(JobsApp, "pair_on_launch", False, raising=False)
    from jobs_tui.screens import render_screen
    monkeypatch.setattr(render_screen, "open_pdf", lambda path: None, raising=False)
    return jobs
