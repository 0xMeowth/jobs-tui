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


def test_create_without_master_leaves_no_folder(jobs_dir):
    paths.master_yaml(jobs_dir).unlink(missing_ok=True)
    with pytest.raises(FileNotFoundError):
        application.create(jobs_dir, "A", "B", None)
    assert not paths.app_paths(jobs_dir, "A", "B").root.exists()


def test_delete_removes_application_folder(jobs_dir):
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    application.delete(p)
    assert not p.root.exists()


def test_company_names_lists_existing_display_names(jobs_dir):
    application.create(jobs_dir, "Fabrikam", "PM", None)
    application.create(jobs_dir, "Fabrikam", "Analyst", None)
    application.create(jobs_dir, "Northwind", "Analyst", None)
    assert sorted(application.company_names(jobs_dir)) == ["Fabrikam", "Northwind"]


def test_existing_company_snaps_to_display_name(jobs_dir):
    application.create(jobs_dir, "Fabrikam", "PM", None)
    assert application.existing_company(jobs_dir, "fab rikam") == "Fabrikam"
    assert application.existing_company(jobs_dir, "FABRIKAM") == "Fabrikam"
    assert application.existing_company(jobs_dir, "Meta") is None


def test_summary_pending_counts_open_and_rework_only(jobs_dir):
    import json
    from jobs_tui.edits import Decision, save_feedback
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps({"edits": [
        {"id": "a", "path": "acme.b1.text", "proposed": "x"},
        {"id": "b", "path": "acme.b2.text", "proposed": "y"},
        {"id": "c", "path": "acme.b1.text", "proposed": "z"},
    ]}))
    save_feedback(p.review_feedback, {"a": Decision("pending", comment="rework me"), "b": Decision("rejected"), "c": Decision("accepted", final="z")})
    s = application.summary(p)
    assert s["edits_total"] == 3 and s["edits_pending"] == 1
