import shutil
from pathlib import Path

import pytest

from jobs_tui.model import Resume, apply_edit, split_path

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "resume-sample.yaml"


@pytest.fixture
def resume(tmp_path):
    shutil.copy(EXAMPLE, tmp_path / "resume.yaml")
    return Resume.load(tmp_path / "resume.yaml")


def test_split_path():
    assert split_path("acme.b1.text") == ("acme.b1", "text")
    assert split_path("acme.title") == ("acme", "title")


def test_get_set_roundtrip(resume, tmp_path):
    assert resume.get("acme.b1.text").startswith("Built a churn model")
    resume.set("acme.title", "Lead Data Analyst")
    resume.save(tmp_path / "resume.yaml")
    again = Resume.load(tmp_path / "resume.yaml")
    assert again.get("acme.title") == "Lead Data Analyst"


def test_get_unknown_id_raises(resume):
    with pytest.raises(KeyError):
        resume.get("nope.b1.text")


def test_add_bullet_uses_next_free_number_and_position(resume):
    new_id = resume.add_bullet("acme", "New bullet", after="acme.b1")
    assert new_id == "acme.b3"
    ids = [b["id"] for b in resume.node("acme")["bullets"]]
    assert ids == ["acme.b1", "acme.b3", "acme.b2"]


def test_add_bullet_at_end_when_after_is_none(resume):
    new_id = resume.add_bullet("skills", "Interests: hiking", after=None)
    assert new_id == "skills.b3"
    assert [b["id"] for b in resume.node("skills")["bullets"]][-1] == "skills.b3"


def test_add_bullet_unknown_after_raises_keyerror(resume):
    with pytest.raises(KeyError):
        resume.add_bullet("acme", "x", after="globex.b1")


def test_remove_keeps_other_ids(resume):
    resume.remove("acme.b1")
    assert [b["id"] for b in resume.node("acme")["bullets"]] == ["acme.b2"]
    assert resume.add_bullet("acme", "x", None) == "acme.b3"


def test_units_lists_entries_and_bullets(resume):
    ids = [u[0] for u in resume.units()]
    assert ids[:4] == ["acme", "acme.b1", "acme.b2", "globex"]
    assert "skills.b1" in ids and "nus.b1" in ids


def test_apply_replace_with_final_override(resume):
    edit = {"id": "e1", "op": "replace", "path": "acme.b2.text", "current": "old", "proposed": "proposed text"}
    assert apply_edit(resume, edit, final="my text") == "acme.b2"
    assert resume.get("acme.b2.text") == "my text"


def test_apply_add_and_remove(resume):
    add = {"id": "e2", "op": "add", "entry": "globex", "after": "globex.b1", "proposed": "Added"}
    assert apply_edit(resume, add, None) == "globex.b2"
    assert resume.get("globex.b2.text") == "Added"
    rem = {"id": "e3", "op": "remove", "path": "globex.b1.text"}
    assert apply_edit(resume, rem, None) == "globex.b1"
    assert [b["id"] for b in resume.node("globex")["bullets"]] == ["globex.b2"]


def test_apply_remove_with_bare_id_removes_only_that_bullet(resume):
    rem = {"id": "e1", "op": "remove", "path": "acme.b1"}
    assert apply_edit(resume, rem, None) == "acme.b1"
    assert [b["id"] for b in resume.node("acme")["bullets"]] == ["acme.b2"]


def test_set_unknown_field_raises(resume):
    with pytest.raises(KeyError):
        resume.set("acme.b1.txt", "x")
    assert "txt" not in resume.node("acme.b1")
