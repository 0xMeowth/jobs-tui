from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select


class PairScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        options = self.app.pane_options
        with Vertical(id="dialog"):
            yield Label("[b]Pair an agent pane[/b]  The review prompt goes to this pane.")
            if options:
                yield Select(options, allow_blank=True, prompt="No agent pane: prompts copy to clipboard", id="pair-select")
            else:
                yield Label("No agent panes found. Start codex or claude in a herdr pane, then press p on the list.")
            with Horizontal():
                yield Button("Continue", variant="primary", id="continue")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "continue":
            self.dismiss(False)
            return
        selects = self.query("#pair-select")
        if selects:
            value = selects.first(Select).value
            self.app.bridge.pane_id = None if value is Select.NULL else str(value)
        self.dismiss(True)
