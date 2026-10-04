from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import Button, Input, Label, Static, TextArea

from jobs_tui.app import WordTextArea
from jobs_tui import application, jd
from jobs_tui.paths import AppPaths, slug


class NewApplicationScreen(ModalScreen[AppPaths | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self) -> None:
        super().__init__()
        self.fetched: tuple[jd.JD, str] | None = None
        self.fetched_url: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]New application[/b]  Paste the posting URL. Company and role fill in from the page.")
            yield Input(placeholder="Job posting URL", id="url")
            yield Input(placeholder="Company", id="company", suggester=SuggestFromList(application.company_names(self.app.jobs), case_sensitive=False))
            yield Input(placeholder="Role", id="role")
            yield Label("No URL? Paste the job description:")
            yield WordTextArea(id="paste")
            yield Static("", id="new-status")
            with Horizontal():
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "create":
            self.submit(announce=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.submit()

    def action_cancel(self) -> None:
        self.workers.cancel_group(self, "fetch")
        self.dismiss(None)

    def field(self, name: str) -> str:
        return self.query_one(f"#{name}", Input).value.strip()

    def submit(self, announce: bool = False) -> None:
        if self.query_one("#create", Button).disabled:
            return
        url = self.field("url")
        pasted = self.query_one("#paste", TextArea).text.strip()
        status = self.query_one("#new-status", Static)
        if url and not pasted and self.fetched_url != url:
            status.update("Fetching job description…")
            self.query_one("#create", Button).disabled = True
            self.fetch(url)
            return
        for name in ("company", "role"):
            if not self.field(name):
                if announce:
                    status.update("Company and role are required.")
                self.query_one(f"#{name}", Input).focus()
                return
        if not url and not pasted:
            status.update("Give a URL or paste the description.")
            return
        self.create(url or None, pasted)

    def create(self, url: str | None, pasted: str) -> None:
        company, role = self.field("company"), self.field("role")
        status = self.query_one("#new-status", Static)
        if not slug(company) or not slug(role):
            status.update("Company and role need at least one ASCII letter or digit for the folder name.")
            return
        known = application.existing_company(self.app.jobs, company)
        if known and known != company:
            company = known
            self.app.notify(f"Using existing company {known}")
        try:
            p = application.create(self.app.jobs, company, role, url)
        except FileExistsError:
            status.update("That company/role folder already exists.")
            return
        except OSError as err:
            status.update(escape(f"Cannot create application: {err}"))
            return
        if pasted:
            jd.import_text(pasted, p)
        elif self.fetched is not None:
            jd.write_jd(self.fetched[0], self.fetched[1], p)
        self.dismiss(p)

    @work(thread=True, exclusive=True, group="fetch")
    def fetch(self, url: str) -> None:
        app = self.app
        try:
            result = jd.fetch_url(url)
        except jd.JDError as e:
            app.call_from_thread(self._fetch_done, url, None, str(e))
            return
        app.call_from_thread(self._fetch_done, url, result, None)

    def _fetch_done(self, url: str, result: tuple[jd.JD, str] | None, error: str | None) -> None:
        if not self.is_current:
            return
        self.query_one("#create", Button).disabled = False
        status = self.query_one("#new-status", Static)
        if result is None:
            status.update(escape(f"{error} Paste the description below and press Create."))
            self.query_one("#paste", TextArea).focus()
            return
        self.fetched, self.fetched_url = result, url
        j = result[0]
        company, role = self.query_one("#company", Input), self.query_one("#role", Input)
        if not company.value.strip() and j.company:
            company.value = j.company
        if not role.value.strip() and j.title and j.title != "Job description":
            role.value = j.title
        for box, what in ((company, "Company"), (role, "Role")):
            if not box.value.strip():
                status.update(f"{what} not found on the page. Fill it in and press Enter.")
                box.focus()
                return
        status.update("")
        self.submit()
