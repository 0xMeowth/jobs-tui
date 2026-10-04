from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static

from jobs_tui import bridge

NO_PANES = "No agent panes found. Start codex or claude in a herdr pane, then press p."


class PairScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel"), Binding("c", "pair_clear", "Pair and clear context", priority=True)]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]Pair an agent pane[/b]  Enter pairs the pane · c pairs it and clears its context. Review prompts go to this pane.")
            yield Static("Looking for agent panes…", id="pair-status")
            yield Select(self.app.pane_options, allow_blank=True, prompt="Pick an agent pane", type_to_search=False, id="pair-select")
            with Horizontal():
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self.app.pane_options:
            self.show_options(self.app.pane_options)
        else:
            self.query_one("#pair-select", Select).display = False
        self.run_worker(self._fetch, thread=True, exclusive=True)

    def _fetch(self) -> None:
        panes = bridge.list_agent_panes() if bridge.in_herdr() else []
        self.app.call_from_thread(self.show_options, [(escape(bridge.pane_label(p, bridge.pane_context(p.pane_id))), p.pane_id) for p in panes])

    def show_options(self, options: list[tuple[str, str]]) -> None:
        if not self.is_mounted:
            return
        select = self.query_one("#pair-select", Select)
        status = self.query_one("#pair-status", Static)
        if not options:
            if not select.display:
                status.update(NO_PANES)
            return
        self.app.pane_options = options
        status.display = False
        if select.display and select._options[1:] == options:
            if not select.has_focus_within:
                select.focus()
                select.action_show_overlay()
            return
        select.set_options(options)
        select.display = True
        select.focus()
        select.action_show_overlay()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "pair_clear":
            return self.query_one("#pair-select", Select).expanded
        return True

    def action_pair_clear(self) -> None:
        from jobs_tui.app import highlighted_value
        value = highlighted_value(self.query_one("#pair-select", Select))
        if value is not None:
            self.app.pair_and_clear(value)
            self.dismiss(True)

    def on_key(self, event: Key) -> None:
        if event.key == "escape" and self.query_one("#pair-select", Select).has_focus_within:
            event.stop()
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is not Select.NULL and self.is_current:
            self.app.bridge.pane_id = str(event.value)
            self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)
