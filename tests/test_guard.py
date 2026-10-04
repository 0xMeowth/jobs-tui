import os

import pytest

from jobs_tui import application, guard, paths


@pytest.fixture
def app(jobs_dir):
    paths.master_yaml(jobs_dir).write_text("name: T\nsections: []\n")
    return application.create(jobs_dir, "A", "B", None)


def test_create_snapshots_and_locks_resume(app):
    assert app.resume_snapshot.read_bytes() == app.resume_yaml.read_bytes()
    assert not os.stat(app.resume_yaml).st_mode & 0o222
    with pytest.raises(PermissionError):
        app.resume_yaml.write_text("agent was here")
    assert guard.outside_change(app) is False


def test_outside_change_detected_and_adopted(app):
    app.resume_yaml.chmod(0o644)
    app.resume_yaml.write_text("name: changed\nsections: []\n")
    assert guard.outside_change(app) is True
    guard.snapshot(app)
    assert guard.outside_change(app) is False


def test_missing_snapshot_is_not_a_change(app):
    app.resume_snapshot.unlink()
    assert guard.outside_change(app) is False
