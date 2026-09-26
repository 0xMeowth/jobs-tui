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
