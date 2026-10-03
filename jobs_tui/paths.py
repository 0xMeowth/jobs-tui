import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


def jobs_dir() -> Path:
    return Path(os.environ.get("JOBS_DIR", "~/dev/jobs")).expanduser()


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")


def compact(text: str) -> str:
    return slug(text).replace("-", "")


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def company_slug(self) -> str: return self.root.parent.name
    @property
    def role_slug(self) -> str: return self.root.name
    @property
    def meta(self) -> Path: return self.root / "application.json"
    @property
    def jd_md(self) -> Path: return self.root / "jd.md"
    @property
    def jd_html(self) -> Path: return self.root / "jd.html"
    @property
    def resume_yaml(self) -> Path: return self.root / "resume.yaml"
    @property
    def review_request(self) -> Path: return self.root / "review-request.md"
    @property
    def proposed_edits(self) -> Path: return self.root / "proposed-edits.json"
    @property
    def review_feedback(self) -> Path: return self.root / "review-feedback.json"
    @property
    def resume_pdf(self) -> Path: return self.preview_dir / "resume.pdf"
    @property
    def preview_dir(self) -> Path: return self.root / "preview"
    @property
    def final_check(self) -> Path: return self.root / "final-check.json"
    @property
    def notes_md(self) -> Path: return self.root / "notes.md"


def app_paths(jobs: Path, company: str, role: str) -> AppPaths:
    return AppPaths(jobs / "companies" / slug(company) / slug(role))


def list_applications(jobs: Path) -> list[AppPaths]:
    companies = jobs / "companies"
    if not companies.exists():
        return []
    roots = [r for c in companies.iterdir() if c.is_dir() for r in c.iterdir() if r.is_dir()]
    roots.sort(key=lambda r: r.stat().st_mtime, reverse=True)
    return [AppPaths(r) for r in roots]


def master_yaml(jobs: Path) -> Path: return jobs / "templates" / "resume-master.yaml"
def template_typ(jobs: Path) -> Path: return jobs / "templates" / "resume.typ"
def tracker_md(jobs: Path) -> Path: return jobs / "tracker.md"
def settings_json(jobs: Path) -> Path: return jobs / "settings.json"
