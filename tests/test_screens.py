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


async def test_new_application_creates_and_imports_pasted_jd(jobs_dir):
    app = JobsApp(jobs_dir)
    async with app.run_test(size=(120, 40)) as pilot:
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
    p = paths.app_paths(jobs_dir, "Acme", "Analyst")
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
        await pilot.press("colon")
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
