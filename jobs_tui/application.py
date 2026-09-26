import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from jobs_tui.paths import AppPaths, app_paths, master_yaml


@dataclass
class Application:
    company: str
    role: str
    url: str | None
    created: str
    submitted_date: str | None = None
    fit: dict[str, str] = field(default_factory=dict)


def load(p: AppPaths) -> Application:
    return Application(**json.loads(p.meta.read_text()))


def save(p: AppPaths, app: Application) -> None:
    p.meta.write_text(json.dumps(asdict(app), indent=2) + "\n")


def create(jobs: Path, company: str, role: str, url: str | None) -> AppPaths:
    p = app_paths(jobs, company, role)
    if p.root.exists():
        raise FileExistsError(p.root)
    p.root.mkdir(parents=True)
    save(p, Application(company=company, role=role, url=url or None, created=date.today().isoformat()))
    shutil.copy(master_yaml(jobs), p.resume_yaml)
    return p


def summary(p: AppPaths) -> dict:
    total = pending = 0
    if p.proposed_edits.exists():
        try:
            from jobs_tui import edits as edits_mod  # local import: edits.py is added in Task 4
            es = edits_mod.load_edits(p.proposed_edits)
            decisions = edits_mod.load_feedback(p.review_feedback)
            total = len(es)
            pending = sum(1 for e in es if edits_mod.status_of(e.id, decisions) == "pending")
        except Exception:
            total = pending = 0
    pages = None
    if p.resume_pdf.exists():
        try:
            from jobs_tui.render import page_count  # added in Task 6
            pages = page_count(p.resume_pdf)
        except Exception:
            pages = None
    return {
        "jd": p.jd_md.exists(),
        "edits_total": total,
        "edits_pending": pending,
        "pages": pages,
        "submitted": load(p).submitted_date,
    }
