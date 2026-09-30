import json

from jobs_tui.edits import Decision, Edit, base_id, counts, label, load_edits, load_feedback, load_request, save_feedback, state_of, status_of

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
    d = {"e1": Decision("accepted", "final text", ""), "e2": Decision("pending", None, "too long")}
    save_feedback(p, d)
    again = load_feedback(p)
    assert again["e1"].final == "final text"
    assert again["e2"].comment == "too long"
    assert status_of("e1", again) == "accepted"
    assert status_of("e9", again) == "pending"
    assert json.loads(p.read_text())["decisions"]["e2"]["status"] == "pending"


def test_counts_and_label(tmp_path):
    p = tmp_path / "proposed-edits.json"; p.write_text(json.dumps(SAMPLE))
    es = load_edits(p)
    d = {"e1": Decision("accepted"), "e3": Decision("rejected")}
    assert counts(es, d) == {"open": 1, "rework": 0, "rejected": 1, "accepted": 1, "sent": 0, "pending": 1}
    assert label(es[0]) == "acme.b1"
    assert label(es[1]) == "+ globex"
    assert label(es[2]) == "- globex.b1"


def test_decision_migrates_old_fields(tmp_path):
    p = tmp_path / "review-feedback.json"
    p.write_text(json.dumps({"decisions": {
        "e1": {"status": "needs_revision", "final": None, "feedback": "shorter"},
        "e2": {"status": "accepted", "final": "x", "feedback": ""},
    }}))
    d = load_feedback(p)
    assert d["e1"].status == "pending" and d["e1"].comment == "shorter"
    assert d["e2"].status == "accepted" and d["e2"].comment == ""
    assert d["e1"].before is None and d["e1"].applied_id is None and d["e1"].sent_proposed is None


def test_state_of_is_derived_from_status_and_comment():
    d = {
        "open": Decision("pending"),
        "rework": Decision("pending", comment="tighten"),
        "rej": Decision("rejected"),
        "acc": Decision("accepted", final="x", comment="ignored"),
    }
    assert state_of("open", d) == "open"
    assert state_of("rework", d) == "rework"
    assert state_of("rej", d) == "rejected"
    assert state_of("acc", d) == "accepted"
    assert state_of("missing", d) == "open"


def test_counts_by_state():
    edits = [Edit(id=i, path=f"{i}.text") for i in ("a", "b", "c", "d")]
    d = {"a": Decision("pending", comment="x"), "b": Decision("rejected"), "c": Decision("accepted", final="y")}
    c = counts(edits, d)
    assert c == {"open": 1, "rework": 1, "rejected": 1, "accepted": 1, "sent": 0, "pending": 2}


def test_sent_state_needs_matching_proposed():
    d = {"a": Decision("pending", comment="x", sent_proposed="old")}
    assert state_of("a", d) == "rework"
    assert state_of("a", d, "old") == "sent"
    assert state_of("a", d, "new") == "rework"
    c = counts([Edit(id="a", path="a.text", proposed="old")], d)
    assert c["sent"] == 1 and c["rework"] == 0 and c["pending"] == 1


def test_request_block_roundtrip_and_preserved(tmp_path):
    p = tmp_path / "review-feedback.json"
    assert load_request(p) == {"round": 0, "items": []}
    req = {"round": 1, "items": [{"id": "e1", "action": "revise", "comment": "shorter", "proposed": "old"}]}
    save_feedback(p, {"e1": Decision("pending", comment="shorter", sent_proposed="old")}, request=req)
    assert load_request(p) == req
    save_feedback(p, {"e1": Decision("accepted", final="z")})
    assert load_request(p) == req
    assert load_feedback(p)["e1"].status == "accepted"


def test_base_id_strips_round_suffix():
    assert base_id("e3") == "e3"
    assert base_id("e3-r2") == "e3"
    assert base_id("acme.b1-r10") == "acme.b1"
    assert base_id("e3-rx") == "e3-rx"


def test_edit_loads_revises(tmp_path):
    p = tmp_path / "proposed-edits.json"
    p.write_text(json.dumps({"edits": [{"id": "e3-r2", "revises": "e3", "path": "a.b1.text", "proposed": "n"}]}))
    e = load_edits(p)[0]
    assert e.revises == "e3"
