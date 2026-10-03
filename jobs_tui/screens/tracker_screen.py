from pathlib import Path

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from jobs_tui import tracker
from jobs_tui.app import CommandBar
from jobs_tui.paths import tracker_md


class TrackerScreen(Screen[Path | None]):
    AUTO_FOCUS = ""
    BINDINGS = [Binding("escape", "back", "Back")]

    def compose(self) -> ComposeResult:
        yield Static("[b]TRACKER[/b]  submitted applications · Enter select · p pair · , settings · Esc back", classes="help")
        yield Static("No submitted applications yet. Finalize one with f.", id="tracker-empty")
        yield DataTable(id="tracker-table", cursor_type="row")
        yield CommandBar()

    def on_mount(self) -> None:
        table = self.query_one("#tracker-table", DataTable)
        table.add_columns("Submitted", "Company", "Role", "Folder", "Notes")
        self.rows = tracker.read(tracker_md(self.app.jobs))
        self.query_one("#tracker-empty", Static).display = not self.rows
        table.display = bool(self.rows)
        for i, r in enumerate(self.rows):
            table.add_row(
                escape(r.submitted),
                escape(r.company),
                escape(r.role),
                escape(r.folder),
                "✓" if (self.app.jobs / r.folder / "notes.md").exists() else "",
                key=str(i),
            )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        folder = self.rows[int(event.row_key.value)].folder.rstrip("/")
        self.dismiss(self.app.jobs / folder)

    def action_back(self) -> None:
        self.dismiss(None)
