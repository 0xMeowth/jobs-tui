from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import Button, Input, Label, Static, TextArea

from jobs_tui import application, jd
from jobs_tui.paths import AppPaths, slug


class NewApplicationScreen(ModalScreen[AppPaths | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self) -> None:
        super().__init__()
        self.created: AppPaths | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]New application[/b]")
            yield Input(placeholder="Company", id="company", suggester=SuggestFromList(application.company_names(self.app.jobs), case_sensitive=False))
            yield Input(placeholder="Role", id="role")
            yield Input(placeholder="Job posting URL (leave empty to paste)", id="url")
            yield Label("Or paste the job description:")
            yield TextArea(id="paste")
            yield Static("", id="new-status")
            with Horizontal():
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "create":
            self.create()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if not self.query_one("#create", Button).disabled:
            self.create()

    def action_cancel(self) -> None:
        self.workers.cancel_group(self, "fetch")
        self.dismiss(None)

    def create(self) -> None:
        company = self.query_one("#company", Input).value.strip()
        role = self.query_one("#role", Input).value.strip()
        url = self.query_one("#url", Input).value.strip() or None
        pasted = self.query_one("#paste", TextArea).text.strip()
        status = self.query_one("#new-status", Static)
        if not company or not role:
            status.update("Company and role are required.")
            return
        if not slug(company) or not slug(role):
            status.update("Company and role need at least one ASCII letter or digit for the folder name.")
            return
        if self.created is None:
            known = application.existing_company(self.app.jobs, company)
            if known and known != company:
                company = known
                self.app.notify(f"Using existing company {known}")
            try:
                self.created = application.create(self.app.jobs, company, role, url)
            except FileExistsError:
                status.update("That company/role folder already exists.")
                return
            except OSError as err:
                status.update(escape(f"Cannot create application: {err}"))
                return
        if pasted:
            jd.import_text(pasted, self.created)
            self.dismiss(self.created)
            return
        if not url:
            status.update("Give a URL or paste the description.")
            return
        status.update("Fetching job description…")
        self.query_one("#create", Button).disabled = True
        self.fetch(url, self.created)

    @work(thread=True, exclusive=True, group="fetch")
    def fetch(self, url: str, p: AppPaths) -> None:
        app = self.app
        try:
            jd.import_url(url, p)
        except jd.JDError as e:
            app.call_from_thread(self._fetch_done, None, str(e))
            return
        app.call_from_thread(self._fetch_done, p, None)

    def _fetch_done(self, result: AppPaths | None, error: str | None) -> None:
        if not self.is_current:
            return
        if result is not None:
            self.dismiss(result)
            return
        self.query_one("#new-status", Static).update(escape(f"{error} Paste the description below and press Create."))
        self.query_one("#create", Button).disabled = False
        self.query_one("#paste", TextArea).focus()
