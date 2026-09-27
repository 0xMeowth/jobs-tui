import json

import pytest

from jobs_tui import application, paths
from jobs_tui.app import JobsApp


@pytest.fixture
def two_apps(jobs_dir):
    a = application.create(jobs_dir, "Northwind", "AI Analyst", "https://x/1")
    b = application.create(jobs_dir, "Fabrikam", "PM", None)
    return a, b


async def test_applications_screen_lists_and_shows_detail(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import ListView, Static
        lv = app.screen.query_one("#app-list", ListView)
        assert len(lv.children) == 2
        detail = app.screen.query_one("#app-detail", Static)
        text = str(detail.content)
        assert "Fabrikam" in text or "Northwind" in text
        await pilot.press("down")
        await pilot.pause()
        assert app.current is not None


async def test_applications_screen_skips_corrupt_folder(jobs_dir, two_apps):
    a, _ = two_apps
    a.meta.write_text("{}")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import ListView
        lv = app.screen.query_one("#app-list", ListView)
        assert len(lv.children) == 1


async def test_colon_focuses_command_bar(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        from textual.widgets import Input
        assert app.screen.query_one("#agent-input", Input).has_focus


async def test_command_bar_submit_copies_when_no_pane(jobs_dir, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    copied = []
    monkeypatch.setattr(bridge_mod, "copy_to_clipboard", lambda t: copied.append(t))
    monkeypatch.setenv("HERDR_ENV", "0")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("colon")
        await pilot.press(*"hello")
        await pilot.press("enter")
        await pilot.pause()
    assert copied == ["hello"]


async def test_new_application_creates_and_imports_pasted_jd(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, TextArea
        app.screen.query_one("#company", Input).value = "Acme"
        app.screen.query_one("#role", Input).value = "Analyst"
        app.screen.query_one("#paste", TextArea).text = "We need an analyst who knows SQL."
        await pilot.click("#create")
        for _ in range(20):
            await pilot.pause(0.1)
            if app.screen.__class__.__name__ == "BriefScreen":
                break
        assert app.screen.__class__.__name__ == "BriefScreen"
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        p = paths.app_paths(jobs_dir, "Acme", "Analyst")
        assert app.current is not None and app.current.root == p.root
    assert p.meta.exists()
    assert "We need an analyst" in p.jd_md.read_text()


async def test_new_application_url_import_error_keeps_dialog(jobs_dir, monkeypatch):
    from jobs_tui import jd
    monkeypatch.setattr(jd, "fetch_url", lambda url: (_ for _ in ()).throw(jd.JDError("blocked")))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, Static
        app.screen.query_one("#company", Input).value = "Acme"
        app.screen.query_one("#role", Input).value = "PM"
        app.screen.query_one("#url", Input).value = "https://careers.example.com/1"
        await pilot.click("#create")
        for _ in range(20):
            await pilot.pause(0.1)
            if "blocked" in str(app.screen.query_one("#new-status", Static).content):
                break
        assert app.screen.__class__.__name__ == "NewApplicationScreen"
        from textual.widgets import Button, TextArea
        assert "blocked" in str(app.screen.query_one("#new-status", Static).content)
        assert not app.screen.query_one("#create", Button).disabled
        assert app.screen.query_one("#paste", TextArea).has_focus
        assert not paths.app_paths(jobs_dir, "Acme", "PM").root.exists()
        app.screen.query_one("#paste", TextArea).text = "Pasted description."
        await pilot.click("#create")
        await pilot.pause()
    p = paths.app_paths(jobs_dir, "Acme", "PM")
    assert p.meta.exists() and "Pasted description." in p.jd_md.read_text()


async def test_new_application_rejects_empty_slug(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, Static, TextArea
        app.screen.query_one("#company", Input).value = "—"
        app.screen.query_one("#role", Input).value = "Analyst"
        app.screen.query_one("#paste", TextArea).text = "Some description."
        await pilot.click("#create")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "NewApplicationScreen"
        assert str(app.screen.query_one("#new-status", Static).content)
    assert paths.list_applications(jobs_dir) == []


async def test_colon_on_modal_does_not_crash(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.set_focus(None)
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        app.action_focus_bar()
        await pilot.pause()
        assert app.is_running
        assert app.screen.__class__.__name__ == "NewApplicationScreen"


async def test_escape_leaves_command_bar(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        from textual.widgets import Input
        assert not app.screen.query_one("#agent-input", Input).has_focus


async def test_cancel_during_url_fetch_returns_to_list(jobs_dir, monkeypatch):
    import threading
    from jobs_tui import jd
    release = threading.Event()
    monkeypatch.setattr(jd, "fetch_url", lambda url: release.wait(2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input
        app.screen.query_one("#company", Input).value = "Acme"
        app.screen.query_one("#role", Input).value = "PM"
        app.screen.query_one("#url", Input).value = "https://careers.example.com/1"
        await pilot.click("#create")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        release.set()
        await pilot.pause(0.3)
        assert app.is_running
        assert app.screen.__class__.__name__ == "ApplicationsScreen"


async def test_brief_writes_request_and_sends(jobs_dir, two_apps, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(bridge_mod.shutil, "which", lambda n: "/x/herdr")
    pane = bridge_mod.Pane("wK:p1", "codex", "idle", "/j", "t", "jobs")
    monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [pane])
    monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: pane if pid == "wK:p1" else None)
    sent = []
    monkeypatch.setattr(bridge_mod, "run_in_pane", lambda pid, text: sent.append((pid, text)))
    app = JobsApp(jobs_dir)
    app.bridge.pane_id = "wK:p1"
    async with app.run_test(size=(120, 40)) as pilot:
        for _ in range(30):
            await pilot.pause(0.05)
            if app.pane_options:
                break
        await pilot.press("b")
        await pilot.pause()
        from textual.widgets import Label, TextArea
        assert any("Agent pane: codex · jobs · t" in str(l.content) for l in app.screen.query(Label))
        assert not app.screen.query("#pane")
        app.screen.query_one("#brief", TextArea).text = "Focus on analytics leadership."
        await pilot.click("#start")
        for _ in range(30):
            await pilot.pause(0.05)
            if sent:
                break
        assert app.screen.__class__.__name__ == "ReviewScreen"
    a = app.current
    req = a.review_request.read_text()
    assert "Focus on analytics leadership." in req and "jd.md" in req and "proposed-edits.json" in req
    assert sent and sent[0][0] == "wK:p1" and str(a.root) in sent[0][1]
    assert app.bridge.pane_id == "wK:p1"


def two_panes(monkeypatch, listed):
    from jobs_tui import bridge as bridge_mod
    panes = [
        bridge_mod.Pane("wK:p1", "codex", "idle", "/j", "Improve resume bullets", "jobs"),
        bridge_mod.Pane("w6:p2", "claude", "working", "/c", "Draft cover letter", "cv rewriting"),
    ]
    listed.extend(panes)
    monkeypatch.setattr(bridge_mod, "in_herdr", lambda: True)
    monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: list(listed))
    monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: next((p for p in listed if p.pane_id == pid), None))
    return panes


async def wait_for_options(pilot, select, n):
    for _ in range(30):
        await pilot.pause(0.05)
        if len(select._options) - 1 == n:
            break
    assert len(select._options) - 1 == n


async def test_command_bar_lists_panes_and_pairs(jobs_dir, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select, Static
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        assert any("codex · jobs · Improve" in str(label) for label, _ in select._options)
        select.value = "wK:p1"
        await pilot.pause()
        assert app.bridge.pane_id == "wK:p1"
        state = app.screen.query_one("#agent-state", Static)
        for _ in range(30):
            await pilot.pause(0.05)
            if "idle" in str(state.content):
                break
        assert "idle" in str(state.content)


async def test_p_focuses_pair_select(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        from textual.widgets import Select
        select = app.screen.query_one("#agent-pane", Select)
        assert select.has_focus
        await pilot.press("escape")
        await pilot.pause()
        assert not select.has_focus
        assert app.is_running
        assert app.screen.__class__.__name__ == "ApplicationsScreen"


async def test_paired_pane_disappearing_clears_pairing(jobs_dir, monkeypatch):
    listed = []
    two_panes(monkeypatch, listed)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        from jobs_tui.app import CommandBar
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        select.value = "wK:p1"
        await pilot.pause()
        assert app.bridge.pane_id == "wK:p1"
        listed.pop()
        app.screen.query_one(CommandBar).refresh_panes()
        await wait_for_options(pilot, select, 1)
        await pilot.pause(0.1)
        assert app.bridge.pane_id == "wK:p1" and select.value == "wK:p1"
        from jobs_tui import bridge as bridge_mod
        listed.clear()
        monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: None)
        app.screen.query_one(CommandBar).refresh_panes()
        await wait_for_options(pilot, select, 0)
        await pilot.pause()
        assert app.bridge.pane_id is None
        assert select.is_blank()


async def test_transient_list_failure_keeps_pairing(jobs_dir, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    listed = []
    panes = two_panes(monkeypatch, listed)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        from jobs_tui.app import CommandBar
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        select.value = "wK:p1"
        await pilot.pause()
        checked = []
        monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [])
        monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: checked.append(pid) or panes[0])
        app.screen.query_one(CommandBar).refresh_panes()
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)
        assert "wK:p1" in checked
        assert app.bridge.pane_id == "wK:p1"
        assert select.value == "wK:p1" and len(select._options) - 1 == 2


async def test_markup_in_pane_title_survives_screen_push(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    pane = bridge_mod.Pane("wK:p1", "codex", "idle", "/j", "fix [/] bug", "jobs")
    monkeypatch.setattr(bridge_mod, "in_herdr", lambda: True)
    monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [pane])
    monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: pane if pid == "wK:p1" else None)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 1)
        select.value = "wK:p1"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert app.is_running
        assert app.screen.__class__.__name__ == "ReviewScreen"
        assert app.screen.query_one("#agent-pane", Select).value == "wK:p1"


async def test_new_panes_appear_while_paired_pane_left_agent_list(jobs_dir, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    listed = []
    two_panes(monkeypatch, listed)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        from jobs_tui.app import CommandBar
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        select.value = "wK:p1"
        await pilot.pause()
        shell = bridge_mod.Pane("wK:p1", "", "unknown", "/j", "zsh", "")
        fresh = bridge_mod.Pane("w9:p3", "claude", "idle", "/n", "New task", "jobs")
        monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [fresh])
        monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: shell if pid == "wK:p1" else None)
        app.screen.query_one(CommandBar).refresh_panes()
        for _ in range(30):
            await pilot.pause(0.05)
            if "w9:p3" in [v for _, v in select._options]:
                break
        assert sorted(v for _, v in select._options[1:]) == ["w9:p3", "wK:p1"]
        assert app.bridge.pane_id == "wK:p1" and select.value == "wK:p1"


async def test_empty_list_keeps_options_when_unpaired(jobs_dir, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        from jobs_tui.app import CommandBar
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [])
        app.screen.query_one(CommandBar).refresh_panes()
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)
        assert len(select._options) - 1 == 2 and select.is_blank()


async def test_pairing_on_pushed_screen_shows_after_pop(jobs_dir, reviewable, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        await wait_for_options(pilot, app.screen.query_one("#agent-pane", Select), 2)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert app.screen.__class__.__name__ == "ReviewScreen"
        review_select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, review_select, 2)
        review_select.value = "w6:p2"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        select = app.screen.query_one("#agent-pane", Select)
        for _ in range(10):
            await pilot.pause(0.05)
            if select.value == "w6:p2":
                break
        assert select.value == "w6:p2"


async def test_pairing_survives_screen_change(jobs_dir, reviewable, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        select.value = "wK:p1"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert app.screen.__class__.__name__ == "ReviewScreen"
        assert app.bridge.pane_id == "wK:p1"
        assert app.screen.query_one("#agent-pane", Select).value == "wK:p1"


SAMPLE_EDITS = {"edits": [
    {"id": "e1", "path": "acme.b1.text", "current": "Built a churn model", "proposed": "Built and deployed a churn model", "reason": "deployment"},
    {"id": "e2", "path": "acme.b2.text", "current": "Automated weekly reporting", "proposed": "Automated reporting", "reason": "shorter"},
]}


@pytest.fixture
def reviewable(jobs_dir):
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps(SAMPLE_EDITS))
    return p


async def test_review_accept_writes_yaml_and_feedback(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
        await pilot.press("a")
        await pilot.pause(0.3)
        from jobs_tui.model import Resume
        from jobs_tui.edits import load_feedback
        assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "Built and deployed a churn model"
        assert load_feedback(reviewable.review_feedback)["e1"].status == "accepted"
        assert app.pages == 2
        await pilot.press("x")
        await pilot.pause()
        assert load_feedback(reviewable.review_feedback)["e2"].status == "rejected"


async def test_review_comment_and_send_feedback(jobs_dir, reviewable, monkeypatch):
    sent = []
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, force=False: sent.append(text) or "sent")
    from jobs_tui.model import Resume
    original = Resume.load(reviewable.resume_yaml).get("acme.b1.text")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        from textual.widgets import TextArea
        app.screen.query_one("#comment", TextArea).text = "Overstates deployment."
        await pilot.click("#ok")
        await pilot.pause()
        from jobs_tui.edits import load_feedback
        d = load_feedback(reviewable.review_feedback)["e1"]
        assert d.status == "pending" and d.comment == "Overstates deployment."
        from jobs_tui.model import Resume
        assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == original
        await pilot.press("s")
        await pilot.pause()
    assert sent and "review-feedback.json" in sent[0]


async def test_review_inline_edit_uses_final_text(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        from textual.widgets import TextArea
        app.screen.query_one("#edit-text", TextArea).text = "My own wording"
        await pilot.click("#ok")
        await pilot.pause(0.3)
        from jobs_tui.model import Resume
        assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "My own wording"


async def test_review_reloads_when_agent_rewrites_edits(jobs_dir, reviewable):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.5)
        from textual.widgets import ListView
        assert len(app.screen.query_one("#edit-list", ListView).children) == 2
        more = dict(SAMPLE_EDITS); more["edits"] = SAMPLE_EDITS["edits"] + [{"id": "e3", "path": "globex.b1.text", "current": "x", "proposed": "y", "reason": "z"}]
        reviewable.proposed_edits.write_text(json.dumps(more))
        for _ in range(30):
            await pilot.pause(0.1)
            if len(app.screen.query_one("#edit-list", ListView).children) == 3:
                break
        assert len(app.screen.query_one("#edit-list", ListView).children) == 3


async def test_review_survives_partial_write(jobs_dir, reviewable):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.5)
        from textual.widgets import ListView
        reviewable.proposed_edits.write_text('{"edits": [{"id": "e1", "pa')
        await pilot.pause(1.0)
        assert len(app.screen.query_one("#edit-list", ListView).children) == 2
        more = {"edits": SAMPLE_EDITS["edits"] + [{"id": "e3", "path": "globex.b1.text", "current": "x", "proposed": "y", "reason": "z"}]}
        reviewable.proposed_edits.write_text(json.dumps(more))
        for _ in range(30):
            await pilot.pause(0.1)
            if len(app.screen.query_one("#edit-list", ListView).children) == 3:
                break
        assert len(app.screen.query_one("#edit-list", ListView).children) == 3
        assert app.is_running


async def test_review_accept_add_twice_adds_one_bullet(jobs_dir, monkeypatch):
    from jobs_tui import render
    from jobs_tui.model import Resume
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps({"edits": [{"id": "e1", "op": "add", "entry": "acme", "proposed": "Led a pricing study", "reason": "impact"}]}))
    before = len(Resume.load(p.resume_yaml).node("acme")["bullets"])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
        await pilot.press("a")
        await pilot.pause(0.3)
    bullets = Resume.load(p.resume_yaml).node("acme")["bullets"]
    assert len(bullets) == before + 1
    assert [b["text"] for b in bullets].count("Led a pricing study") == 1


async def test_review_shows_markup_literally(jobs_dir):
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    text = "Use [bold] tags and [/] closers"
    p.proposed_edits.write_text(json.dumps({"edits": [{"id": "e1", "path": "acme.b1.text", "current": "x", "proposed": text, "reason": "[/]"}]}))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
        from textual.widgets import Static
        assert text in app.screen.query_one("#edit-detail", Static).render().plain
        assert app.is_running


async def test_render_screen_shows_pages_and_autofit(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 3, [], {}))
    monkeypatch.setattr(render, "autofit", lambda jobs, p: render.RenderResult(p.resume_pdf, 2, [], render.LADDER[1]))
    sent = []
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, force=False: sent.append(text) or "sent")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause(0.3)
        from textual.widgets import Static
        info = app.screen.query_one("#render-info", Static)
        assert "3" in str(info.content) and "limit 2" in str(info.content)
        await pilot.press("a")
        await pilot.pause(0.3)
        assert "0.6em" in str(info.content) and app.pages == 2
        await pilot.press("t")
        await pilot.pause()
    assert sent and "must fit 2" in sent[0]


async def test_render_screen_ignores_superseded_render(jobs_dir, reviewable, monkeypatch):
    import threading
    from jobs_tui import render
    release = threading.Event()

    def slow_render(jobs, p):
        release.wait(5)
        return render.RenderResult(p.resume_pdf, 3, [], {})

    monkeypatch.setattr(render, "render", slow_render)
    monkeypatch.setattr(render, "autofit", lambda jobs, p: render.RenderResult(p.resume_pdf, 2, [], render.LADDER[1]))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        from textual.widgets import Static
        info = app.screen.query_one("#render-info", Static)
        await pilot.press("a")
        for _ in range(50):
            await pilot.pause(0.05)
            if "Pages       2" in str(info.content):
                break
        assert "Pages       2" in str(info.content)
        release.set()
        await pilot.pause(0.3)
        assert "Pages       2" in str(info.content) and app.pages == 2


async def test_finalize_records_submission(jobs_dir, reviewable, monkeypatch):
    from datetime import date
    from jobs_tui import render, tracker
    reviewable.resume_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(render, "page_count", lambda pdf: 2)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "FinalizeScreen"
        await pilot.click("#yes")
        await pilot.pause()
    assert reviewable.submitted_pdf.read_bytes() == b"%PDF-1.4 fake"
    assert application.load(reviewable).submitted_date == date.today().isoformat()
    rows = tracker.read(paths.tracker_md(jobs_dir))
    assert rows[0].company == "Acme" and rows[0].folder == "companies/acme/analyst/"


async def test_finalize_refuses_three_pages(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    reviewable.resume_pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(render, "page_count", lambda pdf: 3)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        from textual.widgets import Button
        assert app.screen.query_one("#yes", Button).disabled
    assert not reviewable.submitted_pdf.exists()


async def test_finalize_rolls_back_on_tracker_error(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render, tracker
    reviewable.resume_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(render, "page_count", lambda pdf: 2)

    def fail(path, row):
        raise OSError("disk full")

    monkeypatch.setattr(tracker, "insert", fail)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "FinalizeScreen"
        from textual.widgets import Button
        assert not app.screen.query_one("#yes", Button).disabled
    assert not reviewable.submitted_pdf.exists()
    assert application.load(reviewable).submitted_date is None
    assert tracker.read(paths.tracker_md(jobs_dir)) == []


async def test_finalize_double_click_records_once(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render, tracker
    reviewable.resume_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(render, "page_count", lambda pdf: 2)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        from textual.widgets import Button
        at = app.screen.query_one("#yes", Button).region.center
        await pilot.click(offset=at)
        await pilot.click(offset=at)
        await pilot.pause()
    assert len(tracker.read(paths.tracker_md(jobs_dir))) == 1
    assert reviewable.submitted_pdf.read_bytes() == b"%PDF-1.4 fake"


async def test_tracker_screen_lists_rows(jobs_dir, two_apps):
    from jobs_tui import tracker
    tracker.insert(paths.tracker_md(jobs_dir), tracker.Row("2026-09-26", "Northwind", "AI Analyst", "companies/northwind/ai-analyst/", "https://x/1", ""))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        from textual.widgets import DataTable
        table = app.screen.query_one("#tracker-table", DataTable)
        assert table.row_count == 1
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert app.current.root == jobs_dir / "companies" / "northwind" / "ai-analyst"


async def test_tracker_screen_handles_duplicate_folder(jobs_dir, two_apps):
    from jobs_tui import tracker
    row = tracker.Row("2026-09-26", "Northwind", "AI Analyst", "companies/northwind/ai-analyst/", "https://x/1", "")
    tracker.insert(paths.tracker_md(jobs_dir), row)
    tracker.insert(paths.tracker_md(jobs_dir), row)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        from textual.widgets import DataTable
        table = app.screen.query_one("#tracker-table", DataTable)
        assert table.row_count == 2
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert app.current.root == jobs_dir / "companies" / "northwind" / "ai-analyst"


def record_notes(app):
    notes = []
    real = app.notify

    def notify(message, *args, **kwargs):
        notes.append(str(message))
        return real(message, *args, **kwargs)

    app.notify = notify
    return notes


async def test_send_twice_to_busy_pane_forces(jobs_dir, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(bridge_mod.shutil, "which", lambda n: "/x/herdr")
    pane = bridge_mod.Pane("wK:p1", "codex", "working", "/j", "t")
    monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [pane])
    monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: pane if pid == "wK:p1" else None)
    sent = []
    monkeypatch.setattr(bridge_mod, "run_in_pane", lambda pid, text: sent.append((pid, text)))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.bridge.pane_id = "wK:p1"
        app.send_to_agent("hello")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert sent == []
        app.send_to_agent("hello")
        await app.workers.wait_for_complete()
        await pilot.pause()
    assert sent == [("wK:p1", "hello")]


async def test_no_pane_notify_explains_pairing(jobs_dir, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    monkeypatch.setattr(bridge_mod, "copy_to_clipboard", lambda t: None)
    monkeypatch.setenv("HERDR_ENV", "0")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        notes = record_notes(app)
        app.send_to_agent("hello")
        await app.workers.wait_for_complete()
        await pilot.pause()
    assert "No agent pane. Prompt copied to clipboard. Press p to pair a pane." in notes


async def test_applications_detail_shows_markup_literally(jobs_dir):
    application.create(jobs_dir, "Acme [b]", "Role [/] & Co", "https://x/[/]")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Static
        text = app.screen.query_one("#app-detail", Static).render().plain
        assert "Role [/] & Co" in text and "Acme [b]" in text and "https://x/[/]" in text
        assert app.is_running


async def test_new_application_without_master_shows_error(jobs_dir):
    paths.master_yaml(jobs_dir).unlink()
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, Static, TextArea
        app.screen.query_one("#company", Input).value = "Acme"
        app.screen.query_one("#role", Input).value = "Analyst"
        app.screen.query_one("#paste", TextArea).text = "Some description."
        await pilot.click("#create")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "NewApplicationScreen"
        assert "resume-master.yaml" in app.screen.query_one("#new-status", Static).render().plain
    assert paths.list_applications(jobs_dir) == []


async def test_new_application_enter_in_input_creates(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, TextArea
        app.screen.query_one("#company", Input).value = "Acme"
        app.screen.query_one("#paste", TextArea).text = "Some description."
        app.screen.query_one("#role", Input).focus()
        await pilot.press(*"PM", "enter")
        for _ in range(20):
            await pilot.pause(0.1)
            if app.screen.__class__.__name__ == "BriefScreen":
                break
    assert paths.app_paths(jobs_dir, "Acme", "PM").meta.exists()


async def test_review_reports_permanently_malformed_edits(jobs_dir):
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps({"edits": [{"id": "e1"}]}))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        from textual.widgets import Static
        for _ in range(30):
            await pilot.pause(0.1)
            if "unreadable" in app.screen.query_one("#edit-detail", Static).render().plain:
                break
        assert "unreadable" in app.screen.query_one("#edit-detail", Static).render().plain
        assert app.is_running


async def test_review_accept_with_corrupt_yaml_keeps_running(jobs_dir, reviewable):
    reviewable.resume_yaml.write_text("a: [1")
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        notes = record_notes(app)
        await pilot.press("a")
        await pilot.pause(0.3)
        assert app.is_running
        assert any("resume.yaml" in n for n in notes)
    assert not reviewable.review_feedback.exists()


async def test_render_screen_keys_match_list(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "RenderScreen"
        await pilot.press("b")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "RenderScreen"
        from textual.widgets import Select
        await pilot.press("p")
        await pilot.pause()
        assert app.screen.query_one("#agent-pane", Select).has_focus
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "FinalizeScreen"


async def test_edit_yaml_splits_editor_command(jobs_dir, reviewable, monkeypatch):
    import contextlib
    from jobs_tui.screens import applications
    from jobs_tui import render
    calls = []
    monkeypatch.setenv("EDITOR", "code --wait")
    monkeypatch.setattr(applications.subprocess, "run", lambda args: calls.append(args))
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    monkeypatch.setattr(app, "suspend", contextlib.nullcontext)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert calls == [["code", "--wait", str(reviewable.resume_yaml)]]


async def test_review_r_renders_and_p_pairs(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
        from textual.widgets import Select
        await pilot.press("p")
        await pilot.pause()
        assert app.screen.query_one("#agent-pane", Select).has_focus
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "RenderScreen"


async def test_enter_in_pair_dropdown_pairs_without_opening_review(jobs_dir, two_apps, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Select
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        await pilot.press("p")
        await pilot.press("enter")
        await pilot.pause()
        assert select.expanded, "Enter on the closed dropdown should open it"
        await pilot.press("down", "enter")
        await pilot.pause()
        assert app.bridge.pane_id == "wK:p1"
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert not select.expanded


async def test_x_confirms_then_deletes_draft(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import ListView
        target = app.current
        assert target is not None
        await pilot.press("x")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "DeleteScreen"
        assert target.root.exists()
        await pilot.click("#yes")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert not target.root.exists()
        assert len(app.screen.query_one("#app-list", ListView).children) == 1
        assert app.current is not None and app.current.root != target.root


async def test_x_cancel_keeps_draft(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        target = app.current
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert target.root.exists()


async def test_x_refuses_submitted_application(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        target = app.current
        meta = application.load(target)
        meta.submitted_date = "2026-09-01"
        application.save(target, meta)
        notices = []
        app.notify = lambda msg, **kw: notices.append(msg)
        await pilot.press("x")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert target.root.exists()
        assert any("submitted" in n for n in notices)


async def test_new_application_reuses_existing_company(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, Static, TextArea
        company = app.screen.query_one("#company", Input)
        assert await company.suggester.get_suggestion("fab") == "Fabrikam"
        company.value = "fab rikam"
        app.screen.query_one("#role", Input).value = "Analyst"
        app.screen.query_one("#paste", TextArea).text = "Analyst needed."
        await pilot.click("#create")
        for _ in range(20):
            await pilot.pause(0.1)
            if app.screen.__class__.__name__ == "BriefScreen":
                break
        p = paths.app_paths(jobs_dir, "Fabrikam", "Analyst")
        assert p.meta.exists()
        assert application.load(p).company == "Fabrikam"
        assert not (jobs_dir / "companies" / "fab-rikam").exists()


async def test_list_keeps_focus_after_command_bar(jobs_dir, two_apps, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    monkeypatch.setattr(bridge_mod, "copy_to_clipboard", lambda t: None)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import ListView
        lv = app.screen.query_one("#app-list", ListView)
        assert lv.index == 0
        await pilot.press("p")
        await pilot.press("escape")
        await pilot.pause()
        assert lv.has_focus
        await pilot.press("colon", *"hi", "enter")
        await pilot.pause()
        assert lv.has_focus
        await pilot.press("down")
        await pilot.pause()
        assert lv.index == 1


async def test_picking_pane_returns_focus_to_list(jobs_dir, two_apps, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import ListView, Select
        select = app.screen.query_one("#agent-pane", Select)
        await wait_for_options(pilot, select, 2)
        await pilot.press("p", "enter", "down", "enter")
        await pilot.pause()
        assert app.bridge.pane_id == "wK:p1"
        assert app.screen.query_one("#app-list", ListView).has_focus


async def test_reject_and_comment_refuse_accepted_edit(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from jobs_tui.edits import load_feedback
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
        await pilot.press("up")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert load_feedback(reviewable.review_feedback)["e1"].status == "accepted"
        await pilot.press("c")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
        assert load_feedback(reviewable.review_feedback)["e1"].status == "accepted"
    assert notices.count("Press u to undo accept first") == 2


async def test_reject_keeps_comment_and_comment_keeps_reject(jobs_dir, reviewable):
    from jobs_tui.edits import load_feedback
    from textual.widgets import TextArea
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "Never used it in prod."
        await pilot.click("#ok")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        d = load_feedback(reviewable.review_feedback)["e1"]
        assert d.status == "rejected" and d.comment == "Never used it in prod."
        await pilot.press("up")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "Changed my reason."
        await pilot.click("#ok")
        await pilot.pause()
        d = load_feedback(reviewable.review_feedback)["e1"]
        assert d.status == "rejected" and d.comment == "Changed my reason."


async def test_list_glyphs_follow_derived_state(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from textual.widgets import Label, ListView, TextArea
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "tighten"
        await pilot.click("#ok")
        await pilot.pause()
        await pilot.press("down", "x")
        await pilot.pause()
        rows = [str(item.query_one(Label).content) for item in app.screen.query_one("#edit-list", ListView).children]
        assert rows[0].startswith("◐") and rows[1].startswith("×")
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "no"
        await pilot.click("#ok")
        await pilot.pause()
        rows = [str(item.query_one(Label).content) for item in app.screen.query_one("#edit-list", ListView).children]
        assert rows[1].startswith("⊗")


async def test_busy_agent_keeps_typed_message(jobs_dir, two_apps, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    pane = bridge_mod.Pane("wK:p1", "codex", "working", "/j", "t", "jobs")
    monkeypatch.setattr(bridge_mod, "in_herdr", lambda: True)
    monkeypatch.setattr(bridge_mod, "list_agent_panes", lambda: [pane])
    monkeypatch.setattr(bridge_mod, "get_pane", lambda pid: pane)
    app = JobsApp(jobs_dir)
    app.bridge.pane_id = "wK:p1"
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Input
        await pilot.press("colon", *"hello", "enter")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        box = app.screen.query_one("#agent-input", Input)
        assert box.value == "hello"
        assert box.has_focus


async def test_brief_prefills_from_saved_request(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import TextArea
        await pilot.press("b")
        await pilot.pause()
        app.screen.query_one("#brief", TextArea).text = "Lead with analytics.\nMention SQL."
        await pilot.click("#save")
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        assert app.screen.query_one("#brief", TextArea).text == "Lead with analytics.\nMention SQL."


async def test_brief_start_opens_review(jobs_dir, two_apps, monkeypatch):
    from jobs_tui import bridge as bridge_mod
    monkeypatch.setattr(bridge_mod, "copy_to_clipboard", lambda t: None)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        await pilot.click("#start")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"


async def test_finalize_from_render_returns_to_list(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    reviewable.resume_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(render, "page_count", lambda pdf: 2)
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "RenderScreen"
        await pilot.press("f")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert reviewable.submitted_pdf.exists()


async def test_edit_yaml_rerenders_and_refreshes(jobs_dir, reviewable, monkeypatch):
    import contextlib
    from jobs_tui import render
    from jobs_tui.screens import applications
    monkeypatch.setenv("EDITOR", "true")
    monkeypatch.setattr(applications.subprocess, "run", lambda args: None)
    rendered = []
    monkeypatch.setattr(render, "render", lambda jobs, p: rendered.append(p) or p.resume_pdf.write_bytes(b"%PDF") or render.RenderResult(p.resume_pdf, 3))
    monkeypatch.setattr(render, "page_count", lambda pdf: 3)
    app = JobsApp(jobs_dir)
    monkeypatch.setattr(app, "suspend", contextlib.nullcontext)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert rendered == [reviewable]
        assert app.pages == 3


async def test_page_count_is_singular_for_one_page(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    reviewable.resume_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(render, "page_count", lambda pdf: 1)
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Static
        state = app.screen.query_one("#agent-state", Static)
        for _ in range(30):
            await pilot.pause(0.05)
            if "page" in str(state.content):
                break
        assert str(state.content) == "1 page"
        await pilot.press("f")
        await pilot.pause()
        info = app.screen.query_one("#finalize-info", Static).render().plain
        assert "1 page." in info and "1 pages" not in info


async def test_delete_dialog_shows_relative_folder(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        target = app.current
        await pilot.press("x")
        await pilot.pause()
        from textual.widgets import Label
        texts = [str(l.content) for l in app.screen.query(Label)]
        rel = f"companies/{target.company_slug}/{target.role_slug}/"
        assert any(rel in t for t in texts)
        assert not any(str(jobs_dir) in t for t in texts)


async def test_review_empty_state_depends_on_brief(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Static
        await pilot.press("enter")
        await pilot.pause()
        detail = app.screen.query_one("#edit-detail", Static)
        assert "b to brief the agent" in detail.render().plain
        await pilot.press("escape")
        await pilot.pause()
        app.current.review_request.write_text("# Resume review request\n\n## User focus\n\nx\n\n## Required output\n\ny\n")
        await pilot.press("enter")
        await pilot.pause()
        detail = app.screen.query_one("#edit-detail", Static)
        assert "Waiting for the agent" in detail.render().plain


async def test_review_shows_next_step_when_all_decided(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Static
        await pilot.press("enter")
        await pilot.pause()
        detail = app.screen.query_one("#edit-detail", Static)
        plain = detail.render().plain
        assert "Status: pending" not in plain and "All decided" not in plain
        await pilot.press("A")
        await pilot.pause(0.3)
        plain = detail.render().plain
        assert "All decided" in plain and "r render" in plain


async def test_render_screen_omits_paths(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2, [p.preview_dir / "page-1.png"], {}))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause(0.3)
        from textual.widgets import Static
        plain = app.screen.query_one("#render-info", Static).render().plain
        assert "Pages" in plain and "Previews" not in plain and str(jobs_dir) not in plain


async def test_tracker_shows_empty_state(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        from textual.widgets import Static
        assert any("No submitted applications" in str(w.content) for w in app.screen.query(Static))


async def test_send_feedback_with_nothing_to_revise_notifies(jobs_dir, reviewable, monkeypatch):
    sent = []
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, **kw: sent.append(text))
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
    assert sent == []
    assert any("rework" in n for n in notices)


async def test_edit_on_remove_edit_notifies(jobs_dir):
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps({"edits": [{"id": "e1", "op": "remove", "path": "acme.b1", "current": "x", "proposed": "", "reason": "cut"}]}))
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
    assert any("reword" in n for n in notices)


async def test_enter_in_company_moves_to_role(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, Static
        app.screen.query_one("#company", Input).focus()
        await pilot.press(*"Acme", "enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "NewApplicationScreen"
        assert app.screen.query_one("#role", Input).has_focus
        assert app.screen.query_one("#new-status", Static).render().plain == ""


async def test_new_application_from_url_only(jobs_dir, monkeypatch):
    from jobs_tui import jd
    j = jd.JD("Pastry Chef", "Northwind Bakery", "Wellington", "https://www.linkedin.com/jobs/view/1", "linkedin", "Bake things.")
    monkeypatch.setattr(jd, "fetch_url", lambda url: (j, "<html>x</html>"))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input
        assert app.screen.query_one("#url", Input).has_focus
        await pilot.press(*"https://www.linkedin.com/jobs/view/1", "enter")
        for _ in range(20):
            await pilot.pause(0.1)
            if app.screen.__class__.__name__ == "BriefScreen":
                break
        assert app.screen.__class__.__name__ == "BriefScreen"
    p = paths.app_paths(jobs_dir, "Northwind Bakery", "Pastry Chef")
    assert p.meta.exists()
    assert application.load(p).company == "Northwind Bakery" and application.load(p).role == "Pastry Chef"
    assert p.jd_md.read_text().startswith("# Pastry Chef\n") and p.jd_html.exists()


async def test_new_application_url_without_company_asks_for_it(jobs_dir, monkeypatch):
    from jobs_tui import jd
    j = jd.JD("Pastry Chef", None, None, "https://careers.example.com/1", "http", "Bake things. " * 20)
    monkeypatch.setattr(jd, "fetch_url", lambda url: (j, "<html>x</html>"))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        from textual.widgets import Input, Static
        await pilot.press(*"https://careers.example.com/1", "enter")
        for _ in range(20):
            await pilot.pause(0.1)
            if app.screen.query_one("#company", Input).has_focus:
                break
        assert app.screen.__class__.__name__ == "NewApplicationScreen"
        assert app.screen.query_one("#role", Input).value == "Pastry Chef"
        assert app.screen.query_one("#company", Input).has_focus
        assert "ompany" in app.screen.query_one("#new-status", Static).render().plain
        await pilot.press(*"Acme", "enter")
        for _ in range(20):
            await pilot.pause(0.1)
            if app.screen.__class__.__name__ == "BriefScreen":
                break
        assert app.screen.__class__.__name__ == "BriefScreen"
    p = paths.app_paths(jobs_dir, "Acme", "Pastry Chef")
    assert p.meta.exists() and "Bake things." in p.jd_md.read_text()


async def test_brief_asks_to_pair_when_unpaired_in_herdr(jobs_dir, two_apps, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from textual.widgets import Label, Select
        await wait_for_options(pilot, app.screen.query_one("#agent-pane", Select), 2)
        await pilot.press("b")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "PairScreen"
        app.screen.query_one("#pair-select", Select).value = "wK:p1"
        await pilot.click("#continue")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "BriefScreen"
        assert app.bridge.pane_id == "wK:p1"
        assert any("Agent pane: codex · jobs · Improve" in str(l.content) for l in app.screen.query(Label))
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.query_one("#agent-pane", Select).value == "wK:p1"


async def test_brief_skips_pair_dialog_when_paired(jobs_dir, two_apps, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    app.bridge.pane_id = "wK:p1"
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "BriefScreen"


async def test_pair_dialog_cancel_returns_to_list(jobs_dir, two_apps, monkeypatch):
    two_panes(monkeypatch, [])
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "PairScreen"
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ApplicationsScreen"
        assert app.bridge.pane_id is None


async def test_brief_request_has_method_and_default_focus(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        await pilot.click("#save")
        await pilot.pause()
    req = app.current.review_request.read_text()
    method = req.split("## Method\n")[1].split("## User focus")[0]
    assert method.count("\n1. ") == 1 and "\n7. " in method
    assert "exact phrase" in method and "Do not add any skill" in method and "wait for a reply" in method
    assert "## User focus\n\nOptimise this resume for the role.\n\n## Required output" in req
    assert "Maximise" not in req


async def test_edit_dialog_shows_live_diff(jobs_dir, reviewable):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        from textual.widgets import Static, TextArea
        assert app.screen.__class__.__name__ == "EditTextScreen"
        diff = app.screen.query_one("#dialog-diff", Static)
        plain = diff.render().plain
        assert "Built" in plain and "deployed" in plain
        box = app.screen.query_one("#edit-text", TextArea)
        box.text = "Built a churn model quickly"
        await pilot.pause()
        plain = diff.render().plain
        assert "quickly" in plain and "deployed" not in plain


async def test_comment_dialog_shows_diff(jobs_dir, reviewable):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        from textual.widgets import Static
        assert app.screen.__class__.__name__ == "CommentScreen"
        plain = app.screen.query_one("#dialog-diff", Static).render().plain
        assert "Built" in plain and "deployed" in plain


async def test_brief_request_has_review_rounds_section(jobs_dir, two_apps):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        await pilot.click("#save")
        await pilot.pause()
    req = app.current.review_request.read_text()
    rounds = req.split("## Review rounds\n")[1]
    assert '"<base>-r<round>"' in rounds and '"revises"' in rounds
    assert "same list position" in rounds
    assert 'Never re-propose an edit whose decision is "rejected"' in rounds
    assert 'Act only on review-feedback.json "request" items' in rounds


async def test_accept_records_before_text(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from jobs_tui.edits import load_feedback
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
    d = load_feedback(reviewable.review_feedback)["e1"]
    assert d.before == "Built a churn model on 2M customer records that cut voluntary churn by 8% in two quarters" and d.applied_id == "acme.b1" and d.final == "Built and deployed a churn model"


async def test_undo_rejected_returns_to_pending_keeping_comment(jobs_dir, reviewable):
    from jobs_tui.edits import load_feedback
    from textual.widgets import TextArea
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "why"
        await pilot.click("#ok")
        await pilot.pause()
        await pilot.press("up", "x")
        await pilot.pause()
        await pilot.press("up", "u")
        await pilot.pause()
    d = load_feedback(reviewable.review_feedback)["e1"]
    assert d.status == "pending" and d.comment == "why"


async def test_undo_accepted_replace_restores_yaml(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from jobs_tui.edits import load_feedback
    from jobs_tui.model import Resume
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
        assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "Built and deployed a churn model"
        await pilot.press("up", "u")
        await pilot.pause(0.3)
    assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "Built a churn model on 2M customer records that cut voluntary churn by 8% in two quarters"
    assert load_feedback(reviewable.review_feedback)["e1"].status == "pending"


async def test_undo_accepted_refuses_when_yaml_changed(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from jobs_tui.edits import load_feedback
    from jobs_tui.model import Resume
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
        r = Resume.load(reviewable.resume_yaml)
        r.set("acme.b1.text", "hand edited")
        r.save(reviewable.resume_yaml)
        await pilot.press("up", "u")
        await pilot.pause(0.3)
    assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "hand edited"
    assert load_feedback(reviewable.review_feedback)["e1"].status == "accepted"
    assert any("changed since accept" in n for n in notices)


async def test_undo_accepted_add_removes_bullet(jobs_dir, monkeypatch):
    from jobs_tui import render
    from jobs_tui.model import Resume
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps({"edits": [
        {"id": "n1", "op": "add", "entry": "acme", "after": "acme.b2", "current": "", "proposed": "Shipped a thing", "reason": "gap"}
    ]}))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
        assert Resume.load(p.resume_yaml).has("acme.b3")
        await pilot.press("u")
        await pilot.pause(0.3)
    assert not Resume.load(p.resume_yaml).has("acme.b3")


async def test_undo_accepted_remove_refuses(jobs_dir, monkeypatch):
    from jobs_tui import render
    from jobs_tui.model import Resume
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    p = application.create(jobs_dir, "Acme", "Analyst", None)
    p.proposed_edits.write_text(json.dumps({"edits": [
        {"id": "d1", "op": "remove", "path": "acme.b2", "current": "Automated weekly reporting", "proposed": "", "reason": "cut"}
    ]}))
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause(0.3)
        assert not Resume.load(p.resume_yaml).has("acme.b2")
        await pilot.press("u")
        await pilot.pause(0.3)
    assert not Resume.load(p.resume_yaml).has("acme.b2")
    assert any("Can't undo a remove" in n for n in notices)


async def test_undo_on_open_edit_says_nothing_to_undo(jobs_dir, reviewable):
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
    assert "Nothing to undo" in notices


async def test_undo_replace_without_recorded_before_refuses(jobs_dir, reviewable):
    from jobs_tui import edits as E
    from jobs_tui.model import Resume
    r = Resume.load(reviewable.resume_yaml)
    r.set("acme.b1.text", "Built and deployed a churn model")
    r.save(reviewable.resume_yaml)
    E.save_feedback(reviewable.review_feedback, {"e1": E.Decision("accepted", final="Built and deployed a churn model")})
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
    assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "Built and deployed a churn model"
    assert E.load_feedback(reviewable.review_feedback)["e1"].status == "accepted"
    assert any("No recorded text" in n for n in notices)


async def test_send_feedback_writes_request_block(jobs_dir, reviewable, monkeypatch):
    from jobs_tui.edits import load_feedback, load_request
    from textual.widgets import TextArea
    sent = []
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, **kw: sent.append(text))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "Keep the 8% figure"
        await pilot.click("#ok")
        await pilot.pause()
        await pilot.press("down", "c")
        await pilot.pause()
        app.screen.query_one("#comment", TextArea).text = "Not true"
        await pilot.click("#ok")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        req = load_request(reviewable.review_feedback)
        assert req["round"] == 1
        assert req["items"] == [
            {"id": "e1", "action": "revise", "comment": "Keep the 8% figure", "proposed": "Built and deployed a churn model"},
            {"id": "e2", "action": "rejected", "comment": "Not true", "proposed": "Automated reporting"},
        ]
        assert load_feedback(reviewable.review_feedback)["e1"].sent_proposed == "Built and deployed a churn model"
        assert load_feedback(reviewable.review_feedback)["e2"].sent_proposed is None
        assert sent and "-r1" in sent[0]
        await pilot.press("s")
        await pilot.pause()
        assert load_request(reviewable.review_feedback)["round"] == 1
        assert len(sent) == 2 and sent[0] == sent[1]


async def comment_and_send(app, pilot, text="Keep the 8% figure"):
    from textual.widgets import TextArea
    await pilot.press("c")
    await pilot.pause()
    app.screen.query_one("#comment", TextArea).text = text
    await pilot.click("#ok")
    await pilot.pause()
    await pilot.press("s")
    await pilot.pause()


async def test_send_feedback_second_press_resends_same_text(jobs_dir, reviewable, monkeypatch):
    from jobs_tui.edits import load_request
    sent = []
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, **kw: sent.append(text))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await comment_and_send(app, pilot)
        await pilot.press("s")
        await pilot.pause()
    assert len(sent) == 2 and sent[0] == sent[1]
    assert load_request(reviewable.review_feedback)["round"] == 1


async def test_sent_edit_refuses_verdicts_until_revision(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from jobs_tui.edits import load_feedback
    from jobs_tui.model import Resume
    from textual.widgets import Label, ListView, Static
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, **kw: None)
    original = Resume.load(reviewable.resume_yaml).get("acme.b1.text")
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await comment_and_send(app, pilot)
        for key in ("a", "x", "e", "c"):
            notices.clear()
            app.screen.query_one("#edit-list", ListView).index = 0
            await pilot.pause()
            await pilot.press(key)
            await pilot.pause(0.2)
            assert app.screen.__class__.__name__ == "ReviewScreen", key
            assert "Sent for rework. Wait for the revision, or press u to withdraw." in notices, key
            d = load_feedback(reviewable.review_feedback)["e1"]
            assert d.status == "pending" and d.comment == "Keep the 8% figure", key
        app.screen.query_one("#edit-list", ListView).index = 0
        await pilot.pause()
        rows = [str(item.query_one(Label).content) for item in app.screen.query_one("#edit-list", ListView).children]
        assert rows[0].startswith("◑")
        plain = app.screen.query_one("#edit-detail", Static).render().plain
        assert "1 sent" in plain.splitlines()[0]
        assert "Sent for rework, waiting for the agent: Keep the 8% figure" in plain
    assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == original


async def test_undo_withdraws_sent_edit(jobs_dir, reviewable, monkeypatch):
    from jobs_tui.edits import load_feedback
    from textual.widgets import Label, ListView
    monkeypatch.setattr(JobsApp, "send_to_agent", lambda self, text, **kw: None)
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await comment_and_send(app, pilot)
        await pilot.press("u")
        await pilot.pause()
        rows = [str(item.query_one(Label).content) for item in app.screen.query_one("#edit-list", ListView).children]
        assert rows[0].startswith("◐")
    d = load_feedback(reviewable.review_feedback)["e1"]
    assert d.sent_proposed is None and d.status == "pending" and d.comment == "Keep the 8% figure"
    assert "Withdrawn. It will not be re-sent unless you press s again." in notices


REVISED_EDITS = {"edits": [
    {"id": "e1-r1", "revises": "e1", "path": "acme.b1.text", "current": "Built a churn model", "proposed": "Built a churn model that cut churn 8%", "reason": "kept figure"},
    {"id": "e2", "path": "acme.b2.text", "current": "Automated weekly reporting", "proposed": "Automated reporting", "reason": "shorter"},
]}


async def test_revised_edit_shows_previous_and_comment(jobs_dir, reviewable):
    from jobs_tui.edits import Decision, save_feedback
    from textual.widgets import Label, ListView, Static
    save_feedback(reviewable.review_feedback,
                  {"e1": Decision("pending", comment="Keep the 8% figure", sent_proposed="Built and deployed a churn model")},
                  request={"round": 1, "items": []})
    reviewable.proposed_edits.write_text(json.dumps(REVISED_EDITS))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        rows = [str(item.query_one(Label).content) for item in app.screen.query_one("#edit-list", ListView).children]
        assert rows[0].startswith("○ acme.b1 r1")
        plain = app.screen.query_one("#edit-detail", Static).render().plain
        assert "PREVIOUS (r0)" in plain and "Built and deployed a churn model" in plain
        assert "YOUR COMMENT" in plain and "Keep the 8% figure" in plain
        assert "· r1" in plain.splitlines()[0]


async def test_v_accepts_previous_wording(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    from jobs_tui.edits import Decision, load_feedback, save_feedback
    from jobs_tui.model import Resume
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    save_feedback(reviewable.review_feedback,
                  {"e1": Decision("pending", comment="Keep the 8% figure", sent_proposed="Built and deployed a churn model")},
                  request={"round": 1, "items": []})
    reviewable.proposed_edits.write_text(json.dumps(REVISED_EDITS))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause(0.3)
    assert Resume.load(reviewable.resume_yaml).get("acme.b1.text") == "Built and deployed a churn model"
    d = load_feedback(reviewable.review_feedback)["e1-r1"]
    assert d.status == "accepted" and d.final == "Built and deployed a churn model"


async def test_v_without_previous_round_notifies(jobs_dir, reviewable):
    app = JobsApp(jobs_dir)
    notices = []
    app.notify = lambda msg, **kw: notices.append(msg)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
    assert "No previous round for this edit" in notices


async def test_previous_label_uses_round_of_revised_id(jobs_dir, reviewable):
    from jobs_tui.edits import Decision, save_feedback
    from textual.widgets import ListView, Static
    save_feedback(reviewable.review_feedback, {
        "e1-r1": Decision("pending", comment="shorter", sent_proposed="Built a churn model r1"),
        "e2": Decision("pending", comment="keep weekly", sent_proposed="Automated reporting"),
    }, request={"round": 2, "items": []})
    reviewable.proposed_edits.write_text(json.dumps({"edits": [
        {"id": "e1-r3", "revises": "e1-r1", "path": "acme.b1.text", "current": "Built a churn model", "proposed": "Built churn model", "reason": "r"},
        {"id": "e2-r3", "revises": "e2", "path": "acme.b2.text", "current": "Automated weekly reporting", "proposed": "Automated weekly reports", "reason": "r"},
    ]}))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        detail = app.screen.query_one("#edit-detail", Static)
        assert "PREVIOUS (r1)" in detail.render().plain
        app.screen.query_one("#edit-list", ListView).index = 1
        await pilot.pause()
        assert "PREVIOUS (r0)" in detail.render().plain
