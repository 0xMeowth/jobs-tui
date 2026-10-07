from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Markdown, Static

from jobs_tui import application
from jobs_tui.app import CommandBar
from jobs_tui.paths import AppPaths

NO_JD = "No JD imported for this application."


def open_jd(app: App, p: AppPaths | None) -> None:
    if p is None:
        return
    if not p.jd_md.exists():
        app.notify(NO_JD)
        return
    app.push_screen(JdScreen(p))


class JdScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        yield Static("[b]JOB DESCRIPTION[/b]  ↑↓ PgUp PgDn scroll · p pair (in list: c clears context) · , settings · Esc back", classes="help")
        try:
            meta = application.load(self.p)
            yield Static(f"[b]{escape(meta.company)} · {escape(meta.role)}[/b]", id="jd-title")
        except (OSError, ValueError, TypeError):
            pass
        with VerticalScroll(id="jd-scroll"):
            yield Markdown(self.p.jd_md.read_text(), id="jd-text")
        yield CommandBar()

    def on_mount(self) -> None:
        self.query_one("#jd-scroll", VerticalScroll).focus()

    def action_back(self) -> None:
        self.app.pop_screen()
