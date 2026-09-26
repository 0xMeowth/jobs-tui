import json
from pathlib import Path

import pytest

from jobs_tui import bridge

LIST = {"result": {"panes": [
    {"pane_id": "w6:p1", "agent": "claude", "agent_status": "working", "cwd": "/a", "terminal_title_stripped": "t1"},
    {"pane_id": "wK:p1", "agent": "codex", "agent_status": "idle", "cwd": "/b", "terminal_title_stripped": "t2"},
    {"pane_id": "w1:p1", "cwd": "/c", "agent_status": "unknown", "terminal_title_stripped": "shell"},
]}}
GET = {"result": {"pane": {"pane_id": "wK:p1", "agent": "codex", "agent_status": "idle", "cwd": "/b", "terminal_title_stripped": "t2"}}}


@pytest.fixture
def fake_run(monkeypatch):
    calls = []
    def _run(args):
        calls.append(args)
        if args[:2] == ["pane", "list"]:
            return json.dumps(LIST)
        if args[:2] == ["pane", "get"]:
            return json.dumps(GET) if args[2] == "wK:p1" else (_ for _ in ()).throw(RuntimeError("not found"))
        return ""
    monkeypatch.setattr(bridge, "_run", _run)
    return calls


def test_in_herdr(monkeypatch):
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(bridge.shutil, "which", lambda n: "/usr/local/bin/herdr")
    assert bridge.in_herdr() is True
    monkeypatch.setenv("HERDR_ENV", "0")
    assert bridge.in_herdr() is False


def test_list_agent_panes_filters(fake_run):
    panes = bridge.list_agent_panes()
    assert [(p.pane_id, p.agent, p.status) for p in panes] == [("w6:p1", "claude", "working"), ("wK:p1", "codex", "idle")]


def test_get_pane(fake_run):
    assert bridge.get_pane("wK:p1").status == "idle"
    assert bridge.get_pane("gone") is None


def test_deliver_sent_when_idle(fake_run, monkeypatch):
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(bridge.shutil, "which", lambda n: "/x/herdr")
    b = bridge.Bridge(pane_id="wK:p1")
    assert b.deliver("hello") == "sent"
    assert fake_run[-1] == ["pane", "run", "wK:p1", "hello"]


def test_deliver_busy_when_working_unless_forced(fake_run, monkeypatch):
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(bridge.shutil, "which", lambda n: "/x/herdr")
    busy = dict(GET); busy["result"] = {"pane": {**GET["result"]["pane"], "agent_status": "working"}}
    monkeypatch.setattr(bridge, "_run", lambda args: json.dumps(busy) if args[:2] == ["pane", "get"] else "")
    b = bridge.Bridge(pane_id="wK:p1")
    assert b.deliver("x") == "busy"
    assert b.deliver("x", force=True) == "sent"


def test_deliver_copies_when_no_pane(monkeypatch):
    monkeypatch.setenv("HERDR_ENV", "0")
    copied = []
    monkeypatch.setattr(bridge, "copy_to_clipboard", lambda t: copied.append(t))
    assert bridge.Bridge(pane_id=None).deliver("text") == "copied"
    assert copied == ["text"]


def test_prompts_mention_folder_and_files():
    root = Path("/j/companies/northwind/analyst")
    s = bridge.start_review_prompt(root)
    assert str(root) in s and "review-request.md" in s and "proposed-edits.json" in s and "Do not edit resume.yaml" in s
    f = bridge.feedback_prompt(root)
    assert "review-feedback.json" in f and "needs_revision" in f
    t = bridge.trim_prompt(root, 3)
    assert "3 pages" in t and "resume.yaml" in t
    assert bridge.free_text_prompt(root, "shorten b2") == f"Regarding {root}: shorten b2"
    assert bridge.free_text_prompt(None, "hi") == "hi"
