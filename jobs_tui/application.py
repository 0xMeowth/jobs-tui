import json
import shutil
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from jobs_tui.paths import AppPaths, app_paths, compact, list_applications, master_yaml


@dataclass
class Application:
    company: str
    role: str
    url: str | None
    created: str
    submitted_date: str | None = None


def load(p: AppPaths) -> Application:
    raw = json.loads(p.meta.read_text())
    return Application(**{k: v for k, v in raw.items() if k in Application.__dataclass_fields__})


def save(p: AppPaths, app: Application) -> None:
    p.meta.write_text(json.dumps(asdict(app), indent=2) + "\n")


def _display_names(jobs: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    for p in list_applications(jobs):
        if p.company_slug in names:
            continue
        try:
            names[p.company_slug] = load(p).company
        except (OSError, ValueError, TypeError):
            continue
    return names


def company_names(jobs: Path) -> list[str]:
    return list(_display_names(jobs).values())


def existing_company(jobs: Path, typed: str) -> str | None:
    key = compact(typed)
    if not key:
        return None
    for folder, name in _display_names(jobs).items():
        if compact(folder) == key:
            return name
    return None


def create(jobs: Path, company: str, role: str, url: str | None) -> AppPaths:
    p = app_paths(jobs, company, role)
    if p.root.exists():
        raise FileExistsError(p.root)
    p.root.mkdir(parents=True)
    p.preview_dir.mkdir()
    try:
        shutil.copy(master_yaml(jobs), p.resume_yaml)
        save(p, Application(company=company, role=role, url=url or None, created=date.today().isoformat()))
    except OSError:
        shutil.rmtree(p.root)
        raise
    return p


def summary(p: AppPaths) -> dict:
    total = pending = 0
    if p.proposed_edits.exists():
        try:
            from jobs_tui import edits as edits_mod  # local import: edits.py is added in Task 4
            es = edits_mod.load_edits(p.proposed_edits)
            decisions = edits_mod.load_feedback(p.review_feedback)
            total = len(es)
            pending = edits_mod.counts(es, decisions)["pending"]
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


def delete(p: AppPaths) -> None:
    shutil.rmtree(p.root)
