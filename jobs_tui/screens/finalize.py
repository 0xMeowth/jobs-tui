import shutil
from contextlib import suppress
from datetime import date

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from jobs_tui import application, render, tracker
from jobs_tui.app import pages_text
from jobs_tui.paths import AppPaths, tracker_md


def check_pdf(p: AppPaths) -> tuple[bool, str]:
    if not p.resume_pdf.exists():
        return False, "No rendered PDF. Press r to render first."
    try:
        pages = render.page_count(p.resume_pdf)
    except Exception as err:
        return False, f"Could not read the PDF: {escape(str(err))}"
    if pages > 2:
        return False, f"Resume has {pages_text(pages)}. It must fit 2 before saving."
    return True, f"Resume has {pages_text(pages)}. Saves a copy of resume.pdf in this application's folder."


class SaveScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p
        self.confirm: str | None = None

    def compose(self) -> ComposeResult:
        ok, message = check_pdf(self.p)
        with Vertical(id="dialog"):
            yield Label("[b]Save PDF[/b]")
            yield Static(message, id="save-info")
            yield Input(f"{self.p.company_slug}-{self.p.role_slug}.pdf", id="save-name", disabled=not ok)
            with Horizontal():
                yield Button("Save", variant="primary", id="save", disabled=not ok)
                yield Button("Cancel", id="cancel")

    def target(self) -> str | None:
        name = self.query_one("#save-name", Input).value.strip()
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        if "/" in name or name.startswith("."):
            return None
        return name

    def on_input_changed(self, event: Input.Changed) -> None:

        self.confirm = None
        self.query_one("#save", Button).label = "Save"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.save()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.save()
        else:
            self.dismiss(False)

    def save(self) -> None:
        if not self.is_current or self.query_one("#save", Button).disabled:
            return
        info = self.query_one("#save-info", Static)
        name = self.target()
        if name is None:
            info.update("Enter a file name, not a path.")
            return
        if name == self.p.resume_pdf.name:
            info.update("resume.pdf is the render output. Pick another name.")
            return
        dest = self.p.root / name
        if dest.exists() and self.confirm != name:
            self.confirm = name
            info.update(f"{escape(name)} exists. Press Overwrite to replace it.")
            self.query_one("#save", Button).label = "Overwrite"
            return
        try:
            shutil.copy(self.p.resume_pdf, dest)
        except OSError as err:
            message = escape(f"Save failed: {err}")
            info.update(message)
            self.app.notify(message, severity="error")
            return
        self.app.notify(escape(f"Saved {name}"))
        self.dismiss(True)


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
        if application.load(self.p).submitted_date:
            return False, "This application was already finalized."
        return True, "Finalizing records today as the submission date and adds a row to tracker.md."

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
        dated = False
        meta = None
        try:
            meta = application.load(self.p)
            if meta.submitted_date:
                self.app.notify("This application was already finalized.")
                self.dismiss(False)
                return
            meta.submitted_date = date.today().isoformat()
            application.save(self.p, meta)
            dated = True
            folder = str(self.p.root.relative_to(self.app.jobs)) + "/"
            tracker.insert(tracker_md(self.app.jobs), tracker.Row(meta.submitted_date, meta.company, meta.role, folder, meta.url or "", ""))
        except Exception as err:
            if dated:
                meta.submitted_date = None
                with suppress(Exception):
                    application.save(self.p, meta)
            message = escape(f"Finalize failed: {err}")
            self.query_one("#finalize-info", Static).update(message)
            self.app.notify(message, severity="error")
            yes.disabled = no.disabled = False
            return
        self.app.notify("Recorded in tracker.md")
        self.dismiss(True)
