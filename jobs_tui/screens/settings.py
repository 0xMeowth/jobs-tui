from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label

from jobs_tui import settings


class SettingsScreen(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        s = settings.load(self.app.jobs)
        with Vertical(id="dialog"):
            yield Label("[b]Settings[/b]  Final check before saving a PDF")
            yield Checkbox("Local checks: spelling consistency, spacing, quotes and dashes, trailing periods", s.local_checks, id="local-checks")
            with Horizontal():
                yield Button("Close", id="close")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        settings.save(self.app.jobs, settings.Settings(local_checks=self.query_one("#local-checks", Checkbox).value))

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
