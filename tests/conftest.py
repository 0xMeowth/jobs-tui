import shutil
from pathlib import Path

import pytest

ASSETS = Path(__file__).resolve().parents[1] / "jobs_tui" / "assets"


@pytest.fixture
def jobs_dir(tmp_path, monkeypatch) -> Path:
    jobs = tmp_path / "jobs"
    (jobs / "templates").mkdir(parents=True)
    (jobs / "companies").mkdir()
    if (ASSETS / "resume.typ").exists():
        shutil.copy(ASSETS / "resume.typ", jobs / "templates" / "resume.typ")
    if (ASSETS / "resume-example.yaml").exists():
        shutil.copy(ASSETS / "resume-example.yaml", jobs / "templates" / "resume-master.yaml")
    monkeypatch.setenv("JOBS_DIR", str(jobs))
    monkeypatch.setenv("HERDR_ENV", "0")
    return jobs
