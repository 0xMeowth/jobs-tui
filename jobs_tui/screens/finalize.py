import shutil
from contextlib import suppress
from datetime import date

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from jobs_tui import application, render, tracker
from jobs_tui.app import pages_text
from jobs_tui.paths import AppPaths, tracker_md


class FinalizeScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        ok, message = self.check()
        with Vertical(id="dialog"):
            yield Label("[b]Finalize application[/b]")
            yield Static(message, id="finalize-info")
            yield Label("Have you submitted this application?")
            with Horizontal():
                yield Button("Yes, record it", variant="primary", id="yes", disabled=not ok)
                yield Button("Not yet", id="no")

    def check(self) -> tuple[bool, str]:
        if not self.p.resume_pdf.exists():
            return False, "No rendered PDF. Press r to render first."
        try:
            pages = render.page_count(self.p.resume_pdf)
        except Exception as err:
            return False, f"Could not read the PDF: {escape(str(err))}"
        if pages > 2:
            return False, f"Resume has {pages_text(pages)}. It must fit 2 before finalizing."
        if self.p.submitted_pdf.exists():
            return False, "This application was already finalized."
        return True, f"Resume has {pages_text(pages)}. Finalizing copies it to resume-submitted.pdf and adds a tracker row."

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self.is_current:
            return
        if event.button.id != "yes":
            self.dismiss(False)
            return
        yes, no = self.query_one("#yes", Button), self.query_one("#no", Button)
        yes.disabled = no.disabled = True
        if self.p.submitted_pdf.exists():
            self.app.notify("This application was already finalized.")
            self.dismiss(False)
            return
        copied = False
        meta = None
        try:
            meta = application.load(self.p)
            previous = meta.submitted_date
            shutil.copy(self.p.resume_pdf, self.p.submitted_pdf)
            copied = True
            meta.submitted_date = date.today().isoformat()
            application.save(self.p, meta)
            folder = str(self.p.root.relative_to(self.app.jobs)) + "/"
            tracker.insert(tracker_md(self.app.jobs), tracker.Row(meta.submitted_date, meta.company, meta.role, folder, meta.url or "", ""))
        except Exception as err:
            if copied:
                self.p.submitted_pdf.unlink(missing_ok=True)
                meta.submitted_date = previous
                with suppress(Exception):
                    application.save(self.p, meta)
            message = escape(f"Finalize failed: {err}")
            self.query_one("#finalize-info", Static).update(message)
            self.app.notify(message, severity="error")
            yes.disabled = no.disabled = False
            return
        self.app.notify("Recorded in tracker.md")
        self.dismiss(True)
