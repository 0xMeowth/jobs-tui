import difflib
import json
import threading
from functools import partial

import yaml
from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, ListItem, ListView, Static, TextArea

from jobs_tui import bridge, edits as E, render
from jobs_tui.app import CommandBar
from jobs_tui.model import Resume, apply_edit
from jobs_tui.paths import AppPaths
from jobs_tui.watcher import watch_folder

class FolderChanged(Message):
    def __init__(self, names: set[str]) -> None:
        super().__init__()
        self.names = names


def edit_diff(e: "E.Edit", proposed: str | None = None) -> str:
    proposed = e.proposed if proposed is None else proposed
    if e.op == "replace":
        return word_diff(e.current, proposed)
    if e.op == "remove":
        return "[red strike]" + escape(e.current) + "[/]"
    return "[green]" + escape(proposed) + "[/]"


class EditTextScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, edit: "E.Edit") -> None:
        super().__init__()
        self.edit = edit

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]Edit proposal[/b]  Edit the wording, then accept")
            yield TextArea(self.edit.proposed, id="edit-text")
            yield Static(edit_diff(self.edit), id="dialog-diff")
            with Horizontal():
                yield Button("Accept", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self.query_one("#dialog-diff", Static).update(edit_diff(self.edit, event.text_area.text.strip()))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        text = self.query_one("#edit-text", TextArea).text.strip()
        self.dismiss(text if event.button.id == "ok" and text else None)


class CommentScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, edit: "E.Edit", text: str) -> None:
        super().__init__()
        self.edit = edit
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]Comment for the agent[/b]  Pending edits are reworked. Rejected edits carry it as the reason. Empty clears it. s sends all comments.")
            yield TextArea(self.text, id="comment")
            yield Static(edit_diff(self.edit), id="dialog-diff")
            with Horizontal():
                yield Button("Save comment", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(self.query_one("#comment", TextArea).text.strip() if event.button.id == "ok" else None)


def word_diff(a: str, b: str) -> str:
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a.split(), b.split()).get_opcodes():
        if tag == "equal":
            out.append(escape(" ".join(a.split()[i1:i2])))
        if tag in ("delete", "replace"):
            out.append("[red strike]" + escape(" ".join(a.split()[i1:i2])) + "[/]")
        if tag in ("insert", "replace"):
            out.append("[green]" + escape(" ".join(b.split()[j1:j2])) + "[/]")
    return " ".join(out)


class ReviewScreen(Screen):
    BINDINGS = [
        Binding("a", "accept", "Accept"),
        Binding("x", "reject", "Reject"),
        Binding("e", "edit", "Edit"),
        Binding("c", "comment", "Comment"),
        Binding("u", "undo", "Undo"),
        Binding("v", "accept_previous", "Accept previous"),
        Binding("d", "toggle_diff", "Diff"),
        Binding("j", "next", "Next"), Binding("k", "prev", "Prev"),
        Binding("A", "accept_all", "Accept all pending"),
        Binding("s", "send_feedback", "Send feedback"),
        Binding("r", "render", "Render"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p
        self.edits: list[E.Edit] = []
        self.decisions: dict[str, E.Decision] = {}
        self.show_diff = False
        self._stop = threading.Event()

    def compose(self) -> ComposeResult:
        yield Static("[b]PROPOSED EDITS[/b]  a accept · x reject · e edit · c comment · u undo · v accept previous · d diff · A accept all open · s send feedback · r render · p pair · Esc back", classes="help")
        with Horizontal(id="body"):
            yield ListView(id="edit-list")
            yield Static("", id="edit-detail")
        yield CommandBar()

    async def on_mount(self) -> None:
        self.app.current = self.p
        await self.reload()
        self.watch_files()

    def on_unmount(self) -> None:
        self._stop.set()

    @work(thread=True, exclusive=True)
    def watch_files(self) -> None:
        try:
            watch_folder(self.p.root, self._stop, lambda names: self.post_message(FolderChanged(names)))
        except Exception:
            return

    async def on_folder_changed(self, event: FolderChanged) -> None:
        if "proposed-edits.json" in event.names:
            await self.reload()
            self.app.notify("Proposed edits updated")

    # ----- data -----
    async def reload(self, retry: bool = True) -> None:
        try:
            edits = E.load_edits(self.p.proposed_edits)
            decisions = E.load_feedback(self.p.review_feedback)
            labels = [E.label(e) + (f" r{self.round_of(e)}" if e.revises else "") for e in edits]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as err:
            # The agent may be mid-write; keep the last good state and try once more.
            if retry:
                self.set_timer(0.5, partial(self.reload, retry=False))
            elif self.is_mounted:
                msg = escape(f"proposed-edits.json unreadable: {err}")
                self.app.notify(msg, severity="error")
                self.query_one("#edit-detail", Static).update(msg)
            return
        self.edits, self.decisions = edits, decisions
        lv = self.query_one("#edit-list", ListView)
        index = lv.index or 0
        await lv.clear()
        await lv.extend([
            ListItem(Label(f"{E.GLYPH[E.state_of(e.id, self.decisions, e.proposed)]} {escape(text)}"), name=e.id)
            for e, text in zip(self.edits, labels)
        ])
        if self.edits:
            lv.index = min(index, len(self.edits) - 1)
            self.show(self.edits[lv.index])
        else:
            if self.p.review_request.exists():
                msg = "No proposed edits yet. Waiting for the agent to write proposed-edits.json."
            else:
                msg = "No edits yet. Press Esc, then b to brief the agent."
            self.query_one("#edit-detail", Static).update(msg)

    def current(self) -> E.Edit | None:
        lv = self.query_one("#edit-list", ListView)
        return self.edits[lv.index] if self.edits and lv.index is not None else None

    def round_of(self, e: E.Edit) -> int:
        return E.round_of_id(e.id)

    def previous_text(self, e: E.Edit) -> str | None:
        if not e.revises:
            return None
        return self.decisions.get(e.revises, E.Decision()).sent_proposed

    def show(self, e: E.Edit) -> None:
        d = self.decisions.get(e.id, E.Decision())
        c = E.counts(self.edits, self.decisions)
        body = edit_diff(e) if self.show_diff else f"[dim]CURRENT[/dim]\n{escape(e.current)}\n\n[b]PROPOSED[/b]\n{escape(e.proposed)}"
        state = E.state_of(e.id, self.decisions, e.proposed)
        head = (f"[b]{escape(E.label(e))}[/b]  {escape(e.op)}" + (f"  · r{self.round_of(e)}" if e.revises else "")
                + f"  · {c['open']} open, {c['rework']} rework" + (f", {c['sent']} sent" if c['sent'] else "")
                + f", {c['accepted']} accepted, {c['rejected'] + c['rejected_reason']} rejected")
        if c["pending"] == 0:
            head += "\n[b]All decided[/b] · r render · f finalize"
        elif c["rework"]:
            head += f" · s send {c['rework']} rework"
        status = []
        if state == "rework":
            status.append(f"Rework, sent with s: {escape(d.comment)}")
        elif state == "sent":
            status.append(f"Sent for rework, waiting for the agent: {escape(d.comment)}")
        elif state == "rejected_reason":
            status.append(f"Rejected, reason sent with s: {escape(d.comment)}")
        elif state == "rejected":
            status.append("Rejected")
        elif state == "accepted":
            status.append("Accepted" + (f", comment not sent: {escape(d.comment)}" if d.comment else ""))
        if d.final and d.final != e.proposed:
            status.append(f"Final: {escape(d.final)}")
        previous = []
        prev_text = self.previous_text(e)
        if prev_text is not None:
            prev_comment = self.decisions.get(e.revises, E.Decision()).comment
            previous = [f"[dim]PREVIOUS (r{E.round_of_id(e.revises)})[/dim]\n[dim]{escape(prev_text)}[/dim]", "",
                        f"[dim]YOUR COMMENT[/dim]\n{escape(prev_comment)}", ""]
        lines = [
            head, "",
            f"ALIGNMENT  {escape(', '.join(e.jd_alignment)) or '-'}", "",
            body, "",
            f"[dim]REASON[/dim]\n{escape(e.reason)}", "",
            *previous,
            "\n".join(status),
        ]
        self.query_one("#edit-detail", Static).update("\n".join(lines))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        e = self.current()
        if e:
            self.show(e)

    def set_status(self, e: E.Edit, status: str, **fields: object) -> None:
        prev = self.decisions.get(e.id, E.Decision())
        data = {**prev.__dict__, **fields, "status": status}
        self.decisions[e.id] = E.Decision(**data)
        E.save_feedback(self.p.review_feedback, self.decisions)
        self.call_later(self.reload)

    def set_comment(self, e: E.Edit, text: str) -> None:
        prev = self.decisions.get(e.id, E.Decision())
        self.set_status(e, prev.status, comment=text)

    def refuse_if_accepted(self, e: E.Edit) -> bool:
        if E.status_of(e.id, self.decisions) == "accepted":
            self.app.notify("Press u to undo accept first")
            return True
        return False

    def refuse_if_sent(self, e: E.Edit) -> bool:
        if E.state_of(e.id, self.decisions, e.proposed) == "sent":
            self.app.notify("Sent for rework. Wait for the revision, or press u to withdraw.")
            return True
        return False

    def apply(self, e: E.Edit, final: str | None, render: bool = True) -> None:
        if E.status_of(e.id, self.decisions) == "accepted":
            self.app.notify("Already accepted")
            return
        try:
            resume = Resume.load(self.p.resume_yaml)
            before = resume.get(e.path) if e.op == "replace" else None
            applied_id = apply_edit(resume, e.as_dict(), final)
        except (yaml.YAMLError, OSError) as err:
            self.app.notify(escape(f"Cannot read resume.yaml: {err}"), severity="error")
            return
        except (KeyError, ValueError) as err:
            self.app.notify(escape(f"Cannot apply edit: {err}"), severity="error")
            return
        resume.save(self.p.resume_yaml)
        self.set_status(e, "accepted", final=final if final is not None else e.proposed, before=before, applied_id=applied_id)
        if render:
            self.rerender()

    @work(thread=True, exclusive=True, group="render")
    def rerender(self) -> None:
        try:
            r = render.render(self.app.jobs, self.p)
        except render.RenderError as err:
            self.app.call_from_thread(self.app.notify, escape(f"Render failed: {err}"), severity="error")
            self.app.call_from_thread(self.app.set_pages, None)
            return
        self.app.call_from_thread(self.app.set_pages, r.pages)

    # ----- actions -----
    def action_accept(self) -> None:
        e = self.current()
        if not e or self.refuse_if_sent(e):
            return
        self.apply(e, None)
        self.action_next()

    def action_reject(self) -> None:
        e = self.current()
        if not e or self.refuse_if_accepted(e) or self.refuse_if_sent(e):
            return
        if E.status_of(e.id, self.decisions) == "rejected":
            self.app.notify("Already rejected")
            return
        self.set_status(e, "rejected")
        self.action_next()

    def action_edit(self) -> None:
        e = self.current()
        if not e or self.refuse_if_accepted(e) or self.refuse_if_sent(e):
            return
        if e.op == "remove":
            self.app.notify("Remove edits can't be reworded")
            return
        self.app.push_screen(EditTextScreen(e), lambda text: text is not None and self.apply(e, text))

    def action_comment(self) -> None:
        e = self.current()
        if not e or self.refuse_if_accepted(e) or self.refuse_if_sent(e):
            return
        prev = self.decisions.get(e.id, E.Decision()).comment
        self.app.push_screen(CommentScreen(e, prev), lambda text: text is not None and self.set_comment(e, text))

    def action_undo(self) -> None:
        e = self.current()
        if not e:
            return
        d = self.decisions.get(e.id, E.Decision())
        if E.state_of(e.id, self.decisions, e.proposed) == "sent":
            self.set_status(e, "pending", sent_proposed=None)
            self.app.notify("Withdrawn. It will not be re-sent unless you press s again.")
            return
        if d.status == "pending":
            self.app.notify("Nothing to undo")
            return
        if d.status == "rejected":
            self.set_status(e, "pending")
            return
        if e.op == "remove":
            self.app.notify("Can't undo a remove. Press y on the list to edit resume.yaml.")
            return
        if (e.op == "replace" and d.before is None) or (e.op == "add" and not d.applied_id):
            self.app.notify("Nothing recorded to restore for this edit. Press y on the list to edit resume.yaml.")
            return
        try:
            resume = Resume.load(self.p.resume_yaml)
            if e.op == "replace":
                if resume.get(e.path) != d.final:
                    raise KeyError(E.label(e))
                resume.set(e.path, d.before)
            else:
                if not resume.has(d.applied_id) or resume.get(f"{d.applied_id}.text") != d.final:
                    raise KeyError(E.label(e))
                resume.remove(d.applied_id)
        except (yaml.YAMLError, OSError) as err:
            self.app.notify(escape(f"Cannot read resume.yaml: {err}"), severity="error")
            return
        except KeyError:
            self.app.notify(f"resume.yaml changed since accept ({escape(E.label(e))}). Undo the later edit first, or press y on the list.", severity="warning")
            return
        resume.save(self.p.resume_yaml)
        self.set_status(e, "pending", final=None, before=None, applied_id=None)
        self.rerender()

    def action_accept_previous(self) -> None:
        e = self.current()
        if not e or self.refuse_if_accepted(e):
            return
        prev = self.previous_text(e)
        if prev is None:
            self.app.notify("No previous round for this edit")
            return
        self.apply(e, prev)
        self.action_next()

    def action_toggle_diff(self) -> None:
        self.show_diff = not self.show_diff
        if e := self.current():
            self.show(e)

    def action_next(self) -> None:
        lv = self.query_one("#edit-list", ListView)
        if self.edits and lv.index is not None and lv.index < len(self.edits) - 1:
            lv.index += 1

    def action_prev(self) -> None:
        lv = self.query_one("#edit-list", ListView)
        if self.edits and lv.index:
            lv.index -= 1

    def action_accept_all(self) -> None:
        for e in [e for e in self.edits if E.state_of(e.id, self.decisions, e.proposed) == "open"]:
            self.apply(e, None, render=False)
        self.rerender()

    def action_send_feedback(self) -> None:
        states = {e.id: E.state_of(e.id, self.decisions, e.proposed) for e in self.edits}
        stored = E.load_request(self.p.review_feedback)
        if not any(s == "rework" for s in states.values()):
            if any(s == "sent" for s in states.values()) and stored["items"]:
                self.app.send_to_agent(bridge.feedback_prompt(self.p.root, stored["round"]))
                self.app.notify(f"Re-sent round {stored['round']}")
                return
            self.app.notify("No edits to rework. Press c on an edit first.")
            return
        round_no = stored["round"] + 1
        items = []
        for e in self.edits:
            d = self.decisions.get(e.id, E.Decision())
            if states[e.id] == "rework":
                items.append({"id": e.id, "action": "revise", "comment": d.comment, "proposed": e.proposed})
                self.decisions[e.id] = E.Decision(**{**d.__dict__, "sent_proposed": e.proposed})
            elif states[e.id] == "rejected_reason":
                items.append({"id": e.id, "action": "rejected", "comment": d.comment, "proposed": e.proposed})
        E.save_feedback(self.p.review_feedback, self.decisions, request={"round": round_no, "items": items})
        self.app.send_to_agent(bridge.feedback_prompt(self.p.root, round_no))
        self.call_later(self.reload)

    def action_render(self) -> None:
        from jobs_tui.screens.render_screen import RenderScreen
        self.app.push_screen(RenderScreen(self.p))

    def action_back(self) -> None:
        self.app.pop_screen()
