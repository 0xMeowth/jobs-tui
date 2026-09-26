from functools import partial
from pathlib import Path

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Input, Select, Static

from jobs_tui import bridge
from jobs_tui.bridge import Bridge, Pane, free_text_prompt, pane_label
from jobs_tui.paths import AppPaths


class CommandBar(Widget):
    def compose(self) -> ComposeResult:
        app: JobsApp = self.app  # type: ignore[assignment]
        options = app.pane_options
        value = app.bridge.pane_id if app.bridge.pane_id in [v for _, v in options] else Select.NULL
        yield Select(options, value=value, allow_blank=True, prompt="no agent pane (copy to clipboard)", id="agent-pane")
        yield Static("", id="agent-state")
        yield Input(placeholder=": message to agent", id="agent-input")

    def on_mount(self) -> None:
        self.refresh_panes()
        self.refresh_status()
        self.app.screen_change_signal.subscribe(self, self._on_screen_change)
        self.set_interval(15, self.refresh_panes)
        self.set_interval(5, self.refresh_status)

    def _on_screen_change(self, screen: object) -> None:
        if screen is self.screen:
            self.refresh_panes()

    def refresh_panes(self) -> None:
        self.run_worker(self._fetch_panes, thread=True, exclusive=True, group="panes")

    def _fetch_panes(self) -> None:
        app: JobsApp = self.app  # type: ignore[assignment]
        herdr = bridge.in_herdr()
        panes = bridge.list_agent_panes() if herdr else []
        options: list[tuple[str, str]] | None = [(escape(pane_label(p)), p.pane_id) for p in panes]
        paired = app.bridge.pane_id
        gone = None
        if paired and paired not in [p.pane_id for p in panes]:
            alive = bridge.get_pane(paired) if herdr else None
            if alive is None:
                gone = paired
            elif panes:
                options.append((escape(pane_label(alive)), paired))
            else:
                return  # list call failed; keep pairing and old options
        if not panes:
            options = None  # keep previous options
        app.call_from_thread(self._show_panes, options, gone)

    def _show_panes(self, options: list[tuple[str, str]] | None, gone: str | None = None) -> None:
        if not self.is_mounted:
            return
        app: JobsApp = self.app  # type: ignore[assignment]
        if options is None:
            options = [o for o in app.pane_options if o[1] != gone]
        if app.bridge.pane_id not in [v for _, v in options]:
            if app.bridge.pane_id != gone:
                return  # pairing changed while the worker ran; wait for the next refresh
            app.bridge.pane_id = None
        app.pane_options = options
        select = self.query_one("#agent-pane", Select)
        if options != select._options[1:] or select.value != (app.bridge.pane_id or Select.NULL):
            with select.prevent(Select.Changed):
                select.set_options(options)
                select.value = app.bridge.pane_id or Select.NULL
        self.refresh_status()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "agent-pane":
            return
        app: JobsApp = self.app  # type: ignore[assignment]
        app.bridge.pane_id = None if event.value is Select.NULL else str(event.value)
        self.refresh_status()
        app.leave_bar()

    def refresh_status(self) -> None:
        self.run_worker(self._fetch_status, thread=True, exclusive=True, group="status")

    def _fetch_status(self) -> None:
        app: JobsApp = self.app  # type: ignore[assignment]
        pane = app.bridge.pane()
        app.call_from_thread(self._show_status, pane)

    def _show_status(self, pane: Pane | None) -> None:
        if not self.is_mounted:
            return
        app: JobsApp = self.app  # type: ignore[assignment]
        parts = [escape(pane.status) if pane else "", f"{app.pages} pages" if app.pages is not None else ""]
        self.query_one("#agent-state", Static).update(" · ".join(x for x in parts if x))

    def on_key(self, event: Key) -> None:
        if event.key == "escape" and (self.query_one("#agent-input", Input).has_focus or self.query_one("#agent-pane", Select).has_focus):
            event.stop()
            self.app.leave_bar()  # type: ignore[attr-defined]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app: JobsApp = self.app  # type: ignore[assignment]
        text = event.value.strip()
        event.input.value = ""
        if text:
            app.send_to_agent(free_text_prompt(app.current.root if app.current else None, text))
        app.leave_bar()


class JobsApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [Binding("colon", "focus_bar", "Agent", key_display=":"), Binding("p", "focus_pair", "Pair")]

    def __init__(self, jobs: Path):
        super().__init__()
        self.jobs = jobs
        self.bridge = Bridge()
        self.pane_options: list[tuple[str, str]] = []
        self.current: AppPaths | None = None
        self.pages: int | None = None
        self._busy_text: str | None = None
        self._before_bar: Widget | None = None

    def on_mount(self) -> None:
        from jobs_tui.screens.applications import ApplicationsScreen
        self.push_screen(ApplicationsScreen())

    def _enter_bar(self, selector: str) -> None:
        try:
            target = self.screen.query(selector).first()
        except NoMatches:
            return
        focused = self.screen.focused
        if focused is not None and not any(isinstance(w, CommandBar) for w in focused.ancestors_with_self):
            self._before_bar = focused
        target.focus()

    def leave_bar(self) -> None:
        before, self._before_bar = self._before_bar, None
        if before is not None and before.is_mounted and before.screen is self.screen:
            before.focus()
        else:
            self.screen.set_focus(None)

    def action_focus_bar(self) -> None:
        self._enter_bar("#agent-input")

    def action_focus_pair(self) -> None:
        self._enter_bar("#agent-pane")

    def send_to_agent(self, text: str, force: bool = False) -> None:
        force = force or (text == self._busy_text)
        self.run_worker(partial(self._deliver, text, force), thread=True, group="deliver")

    def _deliver(self, text: str, force: bool) -> None:
        outcome = self.bridge.deliver(text, force=force)
        self.call_from_thread(self._notify_outcome, outcome, text)

    def _notify_outcome(self, outcome: str, text: str) -> None:
        self._busy_text = text if outcome == "busy" else None
        messages = {
            "sent": "Sent to agent pane",
            "busy": "Agent pane is working. Press again to force, or wait.",
            "copied": "No agent pane. Prompt copied to clipboard. Press p to pair a pane.",
        }
        self.notify(messages[outcome], severity="warning" if outcome != "sent" else "information")

    def set_pages(self, n: int | None) -> None:
        self.pages = n
        for bar in self.screen.query(CommandBar):
            bar.refresh_status()
