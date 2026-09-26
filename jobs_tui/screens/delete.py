from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from jobs_tui import application
from jobs_tui.paths import AppPaths


class DeleteScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        meta = application.load(self.p)
        with Vertical(id="dialog"):
            yield Label(f"[b]Delete application?[/b]  {escape(meta.company)} — {escape(meta.role)}")
            yield Label(f"This removes the folder {escape(str(self.p.root))} and everything in it.")
            with Horizontal():
                yield Button("Delete", variant="error", id="yes")
                yield Button("Keep", id="no")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "yes":
            self.dismiss(False)
            return
        try:
            application.delete(self.p)
        except OSError as err:
            self.app.notify(f"Delete failed: {err}", severity="error")
            self.dismiss(False)
            return
        self.dismiss(True)
