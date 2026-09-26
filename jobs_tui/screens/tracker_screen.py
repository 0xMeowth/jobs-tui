from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from jobs_tui import tracker
from jobs_tui.app import CommandBar
from jobs_tui.paths import AppPaths, tracker_md


class TrackerScreen(Screen):
    AUTO_FOCUS = ""
    BINDINGS = [Binding("escape", "back", "Back")]

    def compose(self) -> ComposeResult:
        yield Static("[b]TRACKER[/b]  submitted applications · Enter open · Esc back", classes="help")
        yield DataTable(id="tracker-table", cursor_type="row")
        yield CommandBar()

    def on_mount(self) -> None:
        table = self.query_one("#tracker-table", DataTable)
        table.add_columns("Submitted", "Company", "Role", "Folder", "URL", "Notes")
        self.rows = tracker.read(tracker_md(self.app.jobs))
        for i, r in enumerate(self.rows):
            table.add_row(
                escape(r.submitted),
                escape(r.company),
                escape(r.role),
                escape(r.folder),
                escape(r.url),
                escape(r.notes),
                key=str(i),
            )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        folder = self.rows[int(event.row_key.value)].folder.rstrip("/")
        from jobs_tui.screens.review import ReviewScreen
        self.app.push_screen(ReviewScreen(AppPaths(self.app.jobs / folder)))

    def action_back(self) -> None:
        self.app.pop_screen()
