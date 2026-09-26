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
            if app.screen.__class__.__name__ == "ApplicationsScreen":
                break
        await pilot.pause(0.1)
        p = paths.app_paths(jobs_dir, "Acme", "Analyst")
        assert app.current is not None and app.current.root == p.root
    assert p.meta.exists()
    assert "We need an analyst" in p.jd_md.read_text()


async def test_new_application_url_import_error_keeps_dialog(jobs_dir, monkeypatch):
    from jobs_tui import jd
    monkeypatch.setattr(jd, "import_url", lambda url, p: (_ for _ in ()).throw(jd.JDError("blocked")))
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
    assert paths.app_paths(jobs_dir, "Acme", "PM").meta.exists()


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
    monkeypatch.setattr(jd, "import_url", lambda url, p: release.wait(2))
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
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        from textual.widgets import Label, TextArea
        assert any("Agent pane:" in str(l.content) for l in app.screen.query(Label))
        assert not app.screen.query("#pane")
        app.screen.query_one("#brief", TextArea).text = "Focus on analytics leadership."
        await pilot.click("#start")
        await pilot.pause()
        await app.workers.wait_for_complete()
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
        await pilot.press("r")
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
        assert d.status == "needs_revision" and d.feedback == "Overstates deployment."
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
        await pilot.press("f")
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
        await pilot.press("f")
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
        assert app.screen.__class__.__name__ == "ReviewScreen"
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
        assert app.screen.__class__.__name__ == "ReviewScreen"
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
            if app.screen.__class__.__name__ == "ApplicationsScreen":
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


async def test_render_screen_b_goes_back(jobs_dir, reviewable, monkeypatch):
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
        assert app.screen.__class__.__name__ == "ApplicationsScreen"


async def test_edit_yaml_splits_editor_command(jobs_dir, reviewable, monkeypatch):
    import contextlib
    from jobs_tui.screens import applications
    calls = []
    monkeypatch.setenv("EDITOR", "code --wait")
    monkeypatch.setattr(applications.subprocess, "run", lambda args: calls.append(args))
    app = JobsApp(jobs_dir)
    monkeypatch.setattr(app, "suspend", contextlib.nullcontext)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert calls == [["code", "--wait", str(reviewable.resume_yaml)]]


async def test_review_p_still_renders(jobs_dir, reviewable, monkeypatch):
    from jobs_tui import render
    monkeypatch.setattr(render, "render", lambda jobs, p: render.RenderResult(p.resume_pdf, 2))
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ReviewScreen"
        await pilot.press("p")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "RenderScreen"
