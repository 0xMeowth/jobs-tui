import json
from datetime import date

import pytest

from jobs_tui import application, paths


def test_create_writes_meta_and_copies_master(jobs_dir):
    paths.master_yaml(jobs_dir).write_text("name: Test\nsections: []\n")
    p = application.create(jobs_dir, "Northwind", "AI Analyst", "https://x/1")
    assert p.root.is_dir()
    meta = json.loads(p.meta.read_text())
    assert meta == {
        "company": "Northwind", "role": "AI Analyst", "url": "https://x/1",
        "created": date.today().isoformat(), "submitted_date": None, "fit": {},
    }
    assert p.resume_yaml.read_text() == "name: Test\nsections: []\n"


def test_create_refuses_duplicate(jobs_dir):
    paths.master_yaml(jobs_dir).write_text("name: T\n")
    application.create(jobs_dir, "A", "B", None)
    with pytest.raises(FileExistsError):
        application.create(jobs_dir, "A", "B", None)


def test_load_save_roundtrip(jobs_dir):
    paths.master_yaml(jobs_dir).write_text("name: T\n")
    p = application.create(jobs_dir, "A", "B", None)
    app = application.load(p)
    app.submitted_date = "2026-09-30"
    app.fit = {"leading": "0.45em"}
    application.save(p, app)
    again = application.load(p)
    assert again.submitted_date == "2026-09-30"
    assert again.fit == {"leading": "0.45em"}


def test_summary_from_files(jobs_dir):
    paths.master_yaml(jobs_dir).write_text("name: T\n")
    p = application.create(jobs_dir, "A", "B", None)
    s = application.summary(p)
    assert s == {"jd": False, "edits_total": 0, "edits_pending": 0, "pages": None, "submitted": None}
    p.jd_md.write_text("# x")
    assert application.summary(p)["jd"] is True
