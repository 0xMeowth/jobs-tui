from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea

from jobs_tui import application, bridge
from jobs_tui.paths import AppPaths

REQUEST = """# Resume review request

Company: {company}
Role: {role}

## Files

- Job description: jd.md
- Working resume: resume.yaml (edit only through proposed-edits.json)

## User focus

{brief}

## Required output

Write proposed edits to proposed-edits.json in this folder as
{{"edits": [{{"id": "...", "op": "replace|add|remove", "path": "<unit id>.text", "current": "...", "proposed": "...", "reason": "...", "jd_alignment": ["..."]}}]}}.
For op add use "entry" and "after" instead of "path". Keep the resume to two pages. Do not edit resume.yaml.
"""


class BriefScreen(ModalScreen[None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        pane_id = self.app.bridge.pane_id
        pane = {v: label for label, v in self.app.pane_options}.get(pane_id, escape(pane_id)) if pane_id else None
        with Vertical(id="dialog"):
            yield Label("[b]Review brief[/b]  What should the agent focus on?")
            yield TextArea("", id="brief")
            yield Label(f"Agent pane: {pane if pane else 'none. Close this dialog and press p to pair'}")
            with Horizontal():
                yield Button("Start review", variant="primary", id="start")
                yield Button("Save only", id="save")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        meta = application.load(self.p)
        brief = self.query_one("#brief", TextArea).text.strip() or "Optimise the resume for this role."
        self.p.review_request.write_text(REQUEST.format(company=meta.company, role=meta.role, brief=brief))
        if event.button.id == "start":
            self.app.send_to_agent(bridge.start_review_prompt(self.p.root))
        self.dismiss(None)
