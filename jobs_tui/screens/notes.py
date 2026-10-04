from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea

from jobs_tui.app import WordTextArea
from jobs_tui.paths import AppPaths


class NotesScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        text = self.p.notes_md.read_text() if self.p.notes_md.exists() else ""
        with Vertical(id="dialog"):
            yield Label("[b]Notes[/b]  Answers you wrote for this application, such as portal questions. Saved as notes.md.")
            yield WordTextArea(text, id="notes-text")
            with Horizontal():
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#notes-text", TextArea).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "save":
            self.dismiss(False)
            return
        text = self.query_one("#notes-text", TextArea).text
        if text.strip():
            self.p.notes_md.write_text(text.rstrip("\n") + "\n")
        else:
            self.p.notes_md.unlink(missing_ok=True)
        self.dismiss(True)
