import os
import time
from pathlib import Path

from jobs_tui import paths


def test_jobs_dir_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DIR", str(tmp_path))
    assert paths.jobs_dir() == tmp_path


def test_jobs_dir_default(monkeypatch):
    monkeypatch.delenv("JOBS_DIR", raising=False)
    assert paths.jobs_dir() == Path.home() / "dev" / "jobs"


def test_slug():
    assert paths.slug("Pastry Chef") == "pastry-chef"
    assert paths.slug("  Northwind  ") == "northwind"
    assert paths.slug("Ernst & Young") == "ernst-young"


def test_app_paths(jobs_dir):
    p = paths.app_paths(jobs_dir, "Northwind", "AI Analyst")
    assert p.root == jobs_dir / "companies" / "northwind" / "ai-analyst"
    assert p.meta == p.root / "application.json"
    assert p.jd_md == p.root / "jd.md"
    assert p.jd_html == p.root / "jd.html"
    assert p.resume_yaml == p.root / "resume.yaml"
    assert p.review_request == p.root / "review-request.md"
    assert p.proposed_edits == p.root / "proposed-edits.json"
    assert p.review_feedback == p.root / "review-feedback.json"
    assert p.resume_pdf == p.root / "resume.pdf"
    assert p.preview_dir == p.root / "preview"
    assert p.submitted_pdf == p.root / "resume-submitted.pdf"
    assert p.company_slug == "northwind" and p.role_slug == "ai-analyst"


def test_list_applications_newest_first(jobs_dir):
    a = paths.app_paths(jobs_dir, "A", "x"); a.root.mkdir(parents=True)
    time.sleep(0.01)
    b = paths.app_paths(jobs_dir, "B", "y"); b.root.mkdir(parents=True)
    os.utime(b.root, None)
    roots = [p.root for p in paths.list_applications(jobs_dir)]
    assert roots == [b.root, a.root]


def test_template_paths(jobs_dir):
    assert paths.master_yaml(jobs_dir) == jobs_dir / "templates" / "resume-master.yaml"
    assert paths.template_typ(jobs_dir) == jobs_dir / "templates" / "resume.typ"
    assert paths.tracker_md(jobs_dir) == jobs_dir / "tracker.md"


def test_compact_folds_spacing_case_and_punctuation():
    assert paths.compact("Fab rikam") == "fabrikam"
    assert paths.compact("fab-rikam") == "fabrikam"
    assert paths.compact("FABRIKAM") == "fabrikam"
    assert paths.compact("Meta") != paths.compact("Metabase")
