import re

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

## Method

1. Read jd.md before resume.yaml. List the skills, tools, domain terms and exact phrases the posting uses, ranked by how often and how prominently the posting states them.
2. For each term, find every bullet in resume.yaml that already demonstrates it. Rewrite that bullet to use the posting's exact phrase. Use a synonym only when the exact phrase would misstate what was done.
3. Do not add any skill, tool, metric, date, title, employer, credential or outcome that is not already in resume.yaml. When a bullet would be stronger with a number that resume.yaml does not contain, rewrite it without the number and name the missing number in that edit's reason field.
4. Write every rewritten bullet as one sentence: strong verb, what was done, scale or context, result.
5. Reorder bullets within an entry so the ones matching this posting come first. Do not reorder entries. Do not change dates, titles or employer names.
6. Do not remove bullets.
7. Before writing proposed-edits.json, send one chat message listing the posting requirements that no bullet in resume.yaml can honestly support, and wait for a reply. Then write proposed-edits.json.

## User focus

{brief}

## Required output

Write proposed edits to proposed-edits.json in this folder as
{{"edits": [{{"id": "...", "op": "replace|add|remove", "path": "<unit id>.text", "current": "...", "proposed": "...", "reason": "...", "jd_alignment": ["..."]}}]}}.
For op add use "entry" and "after" instead of "path". Keep the resume to two pages. Do not edit resume.yaml.

## Review rounds

- Ids are unique across all rounds. A revision's id is "<base>-r<round>" and it carries "revises": "<id it replaces>".
- A revision replaces the edit it revises in place, in the same list position. Never delete or reorder other edits.
- Before proposing any edit, read review-feedback.json if it exists. Never re-propose an edit whose decision is "rejected", or any edit with the same path and the same proposed meaning.
- When a message tells you to read the "request" block, act only on its items. Otherwise ignore review-feedback.json except for the rule above.
"""


def saved_brief(p: AppPaths) -> str:
    try:
        text = p.review_request.read_text()
    except OSError:
        return ""
    m = re.search(r"## User focus\n\n(.*?)\n\n## Required output", text, re.S)
    return m.group(1).strip() if m else ""


class BriefScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        pane_id = self.app.bridge.pane_id
        pane = {v: label for label, v in self.app.pane_options}.get(pane_id, escape(pane_id)) if pane_id else None
        with Vertical(id="dialog"):
            yield Label("[b]Review brief[/b]  What should the agent focus on?")
            yield TextArea(saved_brief(self.p), id="brief")
            yield Label(f"Agent pane: {pane if pane else 'none (prompt will be copied to clipboard)'}")
            with Horizontal():
                yield Button("Start review", variant="primary", id="start")
                yield Button("Save without sending", id="save")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        meta = application.load(self.p)
        brief = self.query_one("#brief", TextArea).text.strip() or "Optimise this resume for the role."
        self.p.review_request.write_text(REQUEST.format(company=meta.company, role=meta.role, brief=brief))
        if event.button.id == "start":
            self.app.send_to_agent(bridge.start_review_prompt(self.p.root))
        self.dismiss(event.button.id)
