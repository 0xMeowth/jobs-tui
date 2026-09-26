import difflib
import json
import threading
from functools import partial

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

GLYPH = {"pending": "○", "accepted": "●", "rejected": "×", "needs_revision": "◐"}


class FolderChanged(Message):
    def __init__(self, names: set[str]) -> None:
        super().__init__()
        self.names = names


class EditTextScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]Edit proposal[/b]  Saved as accepted with your wording")
            yield TextArea(self.text, id="edit-text")
            with Horizontal():
                yield Button("Save as accepted", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        text = self.query_one("#edit-text", TextArea).text.strip()
        self.dismiss(text if event.button.id == "ok" and text else None)


class CommentScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]Feedback for the agent[/b]  Marks this edit needs revision")
            yield TextArea(self.text, id="comment")
            with Horizontal():
                yield Button("Save", variant="primary", id="ok")
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
        Binding("r", "reject", "Reject"),
        Binding("e", "edit", "Edit"),
        Binding("c", "comment", "Comment"),
        Binding("d", "toggle_diff", "Diff"),
        Binding("j", "next", "Next"), Binding("k", "prev", "Prev"),
        Binding("A", "accept_all", "Accept all pending"),
        Binding("s", "send_feedback", "Send feedback"),
        Binding("p", "render", "Render"),
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
        yield Static("[b]PROPOSED EDITS[/b]  a accept · r reject · e edit · c comment · d diff · j/k move · A accept all · s send feedback · p render · Esc back", classes="help")
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
            labels = [E.label(e) for e in edits]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError):
            # The agent may be mid-write; keep the last good state and try once more.
            if retry:
                self.set_timer(0.5, partial(self.reload, retry=False))
            return
        self.edits, self.decisions = edits, decisions
        lv = self.query_one("#edit-list", ListView)
        index = lv.index or 0
        await lv.clear()
        await lv.extend([
            ListItem(Label(f"{GLYPH[E.status_of(e.id, self.decisions)]} {escape(text)}"), name=e.id)
            for e, text in zip(self.edits, labels)
        ])
        if self.edits:
            lv.index = min(index, len(self.edits) - 1)
            self.show(self.edits[lv.index])
        else:
            self.query_one("#edit-detail", Static).update("No proposed edits yet. Waiting for the agent to write proposed-edits.json.")

    def current(self) -> E.Edit | None:
        lv = self.query_one("#edit-list", ListView)
        return self.edits[lv.index] if self.edits and lv.index is not None else None

    def show(self, e: E.Edit) -> None:
        d = self.decisions.get(e.id, E.Decision())
        c = E.counts(self.edits, self.decisions)
        body = word_diff(e.current, e.proposed) if self.show_diff and e.op == "replace" else f"[dim]CURRENT[/dim]\n{escape(e.current)}\n\n[b]PROPOSED[/b]\n{escape(e.proposed)}"
        lines = [
            f"[b]{escape(E.label(e))}[/b]  {escape(e.op)}  · {c['pending']} pending, {c['accepted']} accepted, {c['rejected']} rejected, {c['needs_revision']} need revision", "",
            f"ALIGNMENT  {escape(', '.join(e.jd_alignment)) or '-'}", "",
            body, "",
            f"[dim]REASON[/dim]\n{escape(e.reason)}", "",
            f"Status: {d.status}" + (f"\nFeedback: {escape(d.feedback)}" if d.feedback else "") + (f"\nFinal: {escape(d.final)}" if d.final and d.final != e.proposed else ""),
        ]
        self.query_one("#edit-detail", Static).update("\n".join(lines))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        e = self.current()
        if e:
            self.show(e)

    def decide(self, e: E.Edit, status: str, final: str | None = None, feedback: str | None = None) -> None:
        prev = self.decisions.get(e.id, E.Decision())
        self.decisions[e.id] = E.Decision(status, final if final is not None else prev.final, feedback if feedback is not None else prev.feedback)
        E.save_feedback(self.p.review_feedback, self.decisions)
        self.call_later(self.reload)

    def apply(self, e: E.Edit, final: str | None, render: bool = True) -> None:
        if E.status_of(e.id, self.decisions) == "accepted":
            self.app.notify("Already accepted")
            return
        resume = Resume.load(self.p.resume_yaml)
        try:
            apply_edit(resume, e.as_dict(), final)
        except (KeyError, ValueError) as err:
            self.app.notify(f"Cannot apply edit: {err}", severity="error")
            return
        resume.save(self.p.resume_yaml)
        self.decide(e, "accepted", final=final if final is not None else e.proposed)
        if render:
            self.rerender()

    @work(thread=True, exclusive=True, group="render")
    def rerender(self) -> None:
        try:
            r = render.render(self.app.jobs, self.p)
        except render.RenderError as err:
            self.app.call_from_thread(self.app.notify, f"Render failed: {err}", severity="error")
            self.app.call_from_thread(self.app.set_pages, None)
            return
        self.app.call_from_thread(self.app.set_pages, r.pages)

    # ----- actions -----
    def action_accept(self) -> None:
        if e := self.current():
            self.apply(e, None)
            self.action_next()

    def action_reject(self) -> None:
        if e := self.current():
            self.decide(e, "rejected")
            self.action_next()

    def action_edit(self) -> None:
        e = self.current()
        if not e or e.op == "remove":
            return
        if E.status_of(e.id, self.decisions) == "accepted":
            self.app.notify("Already accepted")
            return
        self.app.push_screen(EditTextScreen(e.proposed), lambda text: text is not None and self.apply(e, text))

    def action_comment(self) -> None:
        if e := self.current():
            prev = self.decisions.get(e.id, E.Decision()).feedback
            self.app.push_screen(CommentScreen(prev), lambda text: text is not None and self.decide(e, "needs_revision", feedback=text))

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
        for e in [e for e in self.edits if E.status_of(e.id, self.decisions) == "pending"]:
            self.apply(e, None, render=False)
        self.rerender()

    def action_send_feedback(self) -> None:
        self.app.send_to_agent(bridge.feedback_prompt(self.p.root))

    def action_render(self) -> None:
        from jobs_tui.screens.render_screen import RenderScreen
        self.app.push_screen(RenderScreen(self.p))

    def action_back(self) -> None:
        self.app.pop_screen()
