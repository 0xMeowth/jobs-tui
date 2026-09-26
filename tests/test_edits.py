import json

from jobs_tui.edits import Decision, Edit, counts, label, load_edits, load_feedback, save_feedback, status_of

SAMPLE = {"edits": [
    {"id": "e1", "path": "acme.b1.text", "current": "a", "proposed": "b", "reason": "r", "jd_alignment": ["sql"]},
    {"id": "e2", "op": "add", "entry": "globex", "after": "globex.b1", "proposed": "new", "reason": "gap"},
    {"id": "e3", "op": "remove", "path": "globex.b1.text", "current": "old", "reason": "space"},
]}


def test_load_edits_defaults(tmp_path):
    p = tmp_path / "proposed-edits.json"
    p.write_text(json.dumps(SAMPLE))
    es = load_edits(p)
    assert [e.id for e in es] == ["e1", "e2", "e3"]
    assert es[0].op == "replace" and es[0].jd_alignment == ["sql"]
    assert es[1].op == "add" and es[1].entry == "globex" and es[1].after == "globex.b1"
    assert es[2].op == "remove"
    assert es[0].as_dict()["path"] == "acme.b1.text"


def test_load_edits_missing_file(tmp_path):
    assert load_edits(tmp_path / "none.json") == []


def test_feedback_roundtrip_and_status(tmp_path):
    p = tmp_path / "review-feedback.json"
    assert load_feedback(p) == {}
    d = {"e1": Decision("accepted", "final text", ""), "e2": Decision("needs_revision", None, "too long")}
    save_feedback(p, d)
    again = load_feedback(p)
    assert again["e1"].final == "final text"
    assert again["e2"].feedback == "too long"
    assert status_of("e1", again) == "accepted"
    assert status_of("e9", again) == "pending"
    assert json.loads(p.read_text())["decisions"]["e2"]["status"] == "needs_revision"


def test_counts_and_label(tmp_path):
    p = tmp_path / "proposed-edits.json"; p.write_text(json.dumps(SAMPLE))
    es = load_edits(p)
    d = {"e1": Decision("accepted"), "e3": Decision("rejected")}
    assert counts(es, d) == {"pending": 1, "accepted": 1, "rejected": 1, "needs_revision": 0}
    assert label(es[0]) == "acme.b1"
    assert label(es[1]) == "+ globex"
    assert label(es[2]) == "- globex.b1"
