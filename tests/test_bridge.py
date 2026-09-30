import json
from pathlib import Path

import pytest

from jobs_tui import bridge

LIST = {"result": {"panes": [
    {"pane_id": "w6:p1", "workspace_id": "w6", "agent": "claude", "agent_status": "working", "cwd": "/a", "terminal_title_stripped": "t1"},
    {"pane_id": "wK:p1", "workspace_id": "wK", "agent": "codex", "agent_status": "idle", "cwd": "/b", "terminal_title_stripped": "t2"},
    {"pane_id": "w1:p1", "cwd": "/c", "agent_status": "unknown", "terminal_title_stripped": "shell"},
]}}
WORKSPACES = {"result": {"workspaces": [
    {"workspace_id": "w6", "label": "cv rewriting"},
    {"workspace_id": "wK", "label": "jobs"},
]}}
GET = {"result": {"pane": {"pane_id": "wK:p1", "agent": "codex", "agent_status": "idle", "cwd": "/b", "terminal_title_stripped": "t2"}}}


@pytest.fixture
def fake_run(monkeypatch):
    calls = []
    def _run(args):
        calls.append(args)
        if args[:2] == ["pane", "list"]:
            return json.dumps(LIST)
        if args[:2] == ["workspace", "list"]:
            return json.dumps(WORKSPACES)
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


def test_list_agent_panes_fills_workspace(fake_run):
    panes = bridge.list_agent_panes()
    assert panes[0].workspace == "cv rewriting"
    assert panes[1].workspace == "jobs"


def test_list_agent_panes_without_workspaces(fake_run, monkeypatch):
    real = bridge._run
    def _run(args):
        if args[:2] == ["workspace", "list"]:
            raise RuntimeError("boom")
        return real(args)
    monkeypatch.setattr(bridge, "_run", _run)
    panes = bridge.list_agent_panes()
    assert [p.pane_id for p in panes] == ["w6:p1", "wK:p1"]
    assert all(p.workspace == "" for p in panes)


def test_pane_label():
    long = "Improve the resume bullets for the analytics role at Northwind"
    p = bridge.Pane("wK:p1", "codex", "idle", "/b", long, "jobs")
    assert bridge.pane_label(p) == "codex · jobs · " + long[:39] + "…"
    assert bridge.pane_label(bridge.Pane("x", "claude", "idle", "/", "short", "")) == "claude · short"
    assert bridge.pane_label(bridge.Pane("x", "claude", "idle", "/", "", "ws")) == "claude · ws"


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


def test_deliver_copies_when_run_fails(fake_run, monkeypatch):
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(bridge.shutil, "which", lambda n: "/x/herdr")
    def boom(pane_id, text):
        raise RuntimeError("gone")
    monkeypatch.setattr(bridge, "run_in_pane", boom)
    copied = []
    monkeypatch.setattr(bridge, "copy_to_clipboard", lambda t: copied.append(t))
    b = bridge.Bridge(pane_id="wK:p1")
    assert b.deliver("hello") == "copied"
    assert copied == ["hello"]


def test_list_agent_panes_returns_empty_on_failure(monkeypatch):
    def boom(args):
        raise RuntimeError("boom")
    monkeypatch.setattr(bridge, "_run", boom)
    assert bridge.list_agent_panes() == []


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
    f = bridge.feedback_prompt(root, 1)
    assert "review-feedback.json" in f and '"revise"' in f
    assert bridge.free_text_prompt(root, "shorten b2") == f"Regarding {root}: shorten b2"
    assert bridge.free_text_prompt(None, "hi") == "hi"


def test_feedback_prompt_is_deterministic_per_action():
    root = Path("/j/companies/northwind/analyst")
    f = bridge.feedback_prompt(root, 2)
    assert str(root) in f
    assert '"request" block in review-feedback.json' in f
    assert 'action "revise"' in f and '"<base>-r2"' in f and '"revises"' in f
    assert '"rejected"' not in f
    assert "Leave every edit not listed" in f
    assert "Do not ask me questions" in f and "Do not edit resume.yaml" in f
