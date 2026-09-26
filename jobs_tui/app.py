from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Input, Static

from jobs_tui.bridge import Bridge, free_text_prompt
from jobs_tui.paths import AppPaths


class CommandBar(Widget):
    def compose(self) -> ComposeResult:
        yield Static("", id="agent-status")
        yield Input(placeholder=": message to agent", id="agent-input")

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(5, self.refresh_status)

    def refresh_status(self) -> None:
        app: JobsApp = self.app  # type: ignore[assignment]
        pane = app.bridge.pane()
        agent = f"{pane.agent} {pane.pane_id} {pane.status}" if pane else "no agent pane (copies to clipboard)"
        pages = f" · {app.pages} pages" if app.pages is not None else ""
        self.query_one("#agent-status", Static).update(agent + pages)

    def on_key(self, event: Key) -> None:
        if event.key == "escape" and self.query_one("#agent-input", Input).has_focus:
            event.stop()
            self.screen.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app: JobsApp = self.app  # type: ignore[assignment]
        text = event.value.strip()
        event.input.value = ""
        if text:
            app.send_to_agent(free_text_prompt(app.current.root if app.current else None, text))
        app.screen.set_focus(None)


class JobsApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [Binding("colon", "focus_bar", "Agent", key_display=":")]

    def __init__(self, jobs: Path):
        super().__init__()
        self.jobs = jobs
        self.bridge = Bridge()
        self.current: AppPaths | None = None
        self.pages: int | None = None

    def on_mount(self) -> None:
        from jobs_tui.screens.applications import ApplicationsScreen
        self.push_screen(ApplicationsScreen())

    def action_focus_bar(self) -> None:
        try:
            self.screen.query("#agent-input").first().focus()
        except NoMatches:
            return

    def send_to_agent(self, text: str, force: bool = False) -> str:
        outcome = self.bridge.deliver(text, force=force)
        messages = {
            "sent": "Sent to agent pane",
            "busy": "Agent pane is working. Press again to force, or wait.",
            "copied": "No agent pane. Prompt copied to clipboard.",
        }
        self.notify(messages[outcome], severity="warning" if outcome != "sent" else "information")
        return outcome

    def set_pages(self, n: int | None) -> None:
        self.pages = n
        for bar in self.screen.query(CommandBar):
            bar.refresh_status()
