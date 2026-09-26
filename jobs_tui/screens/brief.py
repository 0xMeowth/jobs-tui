from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, TextArea

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
        panes = bridge.list_agent_panes() if bridge.in_herdr() else []
        options = [(f"{x.agent} · {x.pane_id} · {x.status}", x.pane_id) for x in panes]
        current = self.app.bridge.pane_id if self.app.bridge.pane_id in [o[1] for o in options] else (options[0][1] if options else Select.BLANK)
        with Vertical(id="dialog"):
            yield Label("[b]Review brief[/b]  What should the agent focus on?")
            yield TextArea("", id="brief")
            yield Label("Agent pane")
            yield Select(options, value=current, allow_blank=True, id="pane", prompt="none (copy to clipboard)")
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
        pane = self.query_one("#pane", Select).value
        self.app.bridge.pane_id = None if pane is Select.BLANK else str(pane)
        if event.button.id == "start":
            self.app.send_to_agent(bridge.start_review_prompt(self.p.root))
        self.dismiss(None)
