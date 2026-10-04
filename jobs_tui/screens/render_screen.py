import subprocess
from pathlib import Path

import yaml
from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from jobs_tui import checks, edits as E, guard, render, settings
from jobs_tui.app import CommandBar
from jobs_tui.model import Resume
from jobs_tui.paths import AppPaths

HELP = "[b]RENDER[/b]  o open PDF · s save PDF · S save without check · w notes · f finalize · p pair (in list: c clears context) · , settings · Esc back"
CHECK_HELP = "[b]RENDER[/b]  a fix · x dismiss · e edit · u undo · o open PDF · s save PDF · S save without check · w notes · f finalize · p pair (in list: c clears context) · , settings · Esc back"
GLYPH = {"open": "○", "fixed": "●", "dismissed": "×"}


def open_pdf(path: Path) -> None:
    subprocess.Popen(["open", str(path)])


class SkipCheckScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[b]Save without the final check?[/b]  Bullets are not checked for spelling, spacing, quotes or trailing periods.")
            with Horizontal():
                yield Button("Save unchecked", variant="error", id="yes")
                yield Button("Cancel", id="no")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class RenderScreen(Screen):
    AUTO_FOCUS = ""
    BINDINGS = [
        Binding("o", "open_pdf", "Open PDF"),
        Binding("s", "save", "Save PDF"),
        Binding("S", "skip_check", "Save without check"),
        Binding("a", "fix", "Fix"),
        Binding("x", "dismiss_finding", "Dismiss"),
        Binding("e", "edit_finding", "Edit"),
        Binding("u", "undo_finding", "Undo"),
        Binding("w", "notes", "Notes"),
        Binding("f", "finalize", "Finalize"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p
        self.rows: list[tuple[str, dict]] = []
        self._save_after_render = False

    def compose(self) -> ComposeResult:
        yield Static(HELP, classes="help", id="render-help")
        yield Static("Rendering…", id="render-info")
        with Vertical(id="check-panel"):
            yield Static("", id="check-head")
            with Horizontal(id="check-body"):
                yield ListView(id="check-list")
                yield Static("", id="check-detail")
        yield CommandBar()

    def on_mount(self) -> None:
        self.app.current = self.p
        self.query_one("#check-panel").display = False
        self._render_worker()
        if checks.load_state(self.p.final_check)["status"] == "findings":
            self.show_findings()

    @work(thread=True, exclusive=True, group="render")
    def _render_worker(self) -> None:
        try:
            r = render.render(self.app.jobs, self.p)
        except render.RenderError as err:
            self.app.call_from_thread(self._render_done, None, str(err))
            return
        self.app.call_from_thread(self._render_done, r, None)

    def _render_done(self, r: render.RenderResult | None, error: str | None) -> None:
        if not self.is_current:
            return
        if r is None:
            self._save_after_render = False
            self.query_one("#render-info", Static).update(f"[red]Render failed[/red]\n\n{escape(error or '')}")
            self.app.set_pages(None)
            return
        self.show(r)
        if self._save_after_render:
            self._save_after_render = False
            self.open_save()

    def show(self, r: render.RenderResult) -> None:
        self.app.set_pages(r.pages)
        over = r.pages - 2
        self.query_one("#render-info", Static).update(
            f"Pages       {r.pages}  (limit 2)" + ("  [red]over by " + str(over) + "[/red]" if over > 0 else "  [green]ok[/green]"))
        self.action_open_pdf()

    def action_open_pdf(self) -> None:
        if self.p.resume_pdf.exists():
            open_pdf(self.p.resume_pdf)

    # ----- final check -----
    def resume_data(self) -> dict:
        return yaml.safe_load(self.p.resume_yaml.read_text())

    def jd(self) -> str:
        return self.p.jd_md.read_text() if self.p.jd_md.exists() else ""

    def open_save(self, note: str = "") -> None:
        from jobs_tui.screens.finalize import SaveScreen
        self.app.push_screen(SaveScreen(self.p, note))

    def action_save(self) -> None:
        from jobs_tui.screens.finalize import check_pdf
        if guard.outside_change(self.p):
            self.app.notify(guard.OUTSIDE_CHANGE, severity="warning")
        if not check_pdf(self.p)[0] or not settings.load(self.app.jobs).local_checks:
            self.open_save()
            return
        st = checks.load_state(self.p.final_check)
        data = self.resume_data()
        if st["status"] == "checked":
            n = checks.changed_since(data, st)
            self.open_save(f"{n} bullet{'s' if n != 1 else ''} changed since the final check and were not re-checked." if n else "")
            return
        if not checks.open_findings(data, self.jd(), st):
            self.finish(st, data, render_first=False)
            return
        st["status"] = "findings"
        checks.save_state(self.p.final_check, st)
        self.show_findings()
        self.app.notify("Final check found issues. Fix (a) or dismiss (x) each one.")

    def action_skip_check(self) -> None:
        if not settings.load(self.app.jobs).local_checks:
            self.open_save()
            return

        def skipped(ok: bool) -> None:
            if ok:
                st = checks.load_state(self.p.final_check)
                st["status"] = "skipped"
                checks.save_state(self.p.final_check, st)
                self.hide_findings()
                self.open_save()

        self.app.push_screen(SkipCheckScreen(), skipped)

    def finish(self, st: dict, data: dict, render_first: bool) -> None:
        checks.mark_checked(st, data, ["local"])
        checks.save_state(self.p.final_check, st)
        self.hide_findings()
        if render_first:
            self._save_after_render = True
            self.query_one("#render-info", Static).update("Rendering…")
            self._render_worker()
        else:
            self.open_save()

    def hide_findings(self) -> None:
        self.query_one("#check-panel").display = False
        self.query_one("#render-help", Static).update(HELP)
        self.refresh_bindings()

    def show_findings(self) -> None:
        st = checks.load_state(self.p.final_check)
        open_ = checks.open_findings(self.resume_data(), self.jd(), st)
        self.rows = [("open", checks.finding_dict(f)) for f in open_]
        self.rows += [("fixed", a) for a in st["applied"]] + [("dismissed", d) for d in st["dismissed"]]
        lv = self.query_one("#check-list", ListView)
        index = lv.index or 0
        lv.clear()
        lv.extend([ListItem(Label(f"{GLYPH[kind]} {escape(item['bullet_id'])}")) for kind, item in self.rows])
        self.query_one("#check-panel").display = True
        self.query_one("#render-help", Static).update(CHECK_HELP)
        self.query_one("#check-head", Static).update(
            f"[b]Final check[/b]  {len(open_)} to fix · {len(st['applied'])} fixed · {len(st['dismissed'])} dismissed")
        if self.rows:
            lv.index = min(index, len(self.rows) - 1)
            self.show_row()
        lv.focus()
        self.refresh_bindings()

    def current_row(self) -> tuple[str, dict] | None:
        if not self.query_one("#check-panel").display:
            return None
        lv = self.query_one("#check-list", ListView)
        return self.rows[lv.index] if self.rows and lv.index is not None and lv.index < len(self.rows) else None

    def show_row(self) -> None:
        from jobs_tui.screens.review import word_diff
        row = self.current_row()
        if not row:
            return
        kind, item = row
        if kind == "fixed":
            body = f"[b]Fixed[/b]  u restores the previous text\n\n{word_diff(item['before'], item['after'])}"
        else:
            title = "Dismissed" if kind == "dismissed" else "Local check"
            body = f"[b]{title}:[/b] {escape(', '.join(item['rules']))}\n\n{word_diff(item['current'], item['proposed'])}"
        self.query_one("#check-detail", Static).update(body)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "check-list":
            self.show_row()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("fix", "dismiss_finding", "edit_finding", "undo_finding"):
            return self.is_mounted and bool(self.query_one("#check-panel").display)
        return True

    def after_change(self) -> None:
        st = checks.load_state(self.p.final_check)
        data = self.resume_data()
        if not checks.open_findings(data, self.jd(), st):
            self.finish(st, data, render_first=True)
        else:
            self.show_findings()

    def apply_text(self, item: dict, text: str) -> None:
        path = f"{item['bullet_id']}.text"
        resume = Resume.load(self.p.resume_yaml)
        if resume.get(path) != item["current"]:
            self.app.notify("This bullet changed since the check. Edit it by hand (y on the list) or dismiss it (x).", severity="warning")
            return
        resume.set(path, text)
        resume.save(self.p.resume_yaml)
        guard.snapshot(self.p)
        st = checks.load_state(self.p.final_check)
        st["applied"].append({"bullet_id": item["bullet_id"], "before": item["current"], "after": text, "rules": item["rules"]})
        checks.save_state(self.p.final_check, st)
        self.after_change()

    def action_fix(self) -> None:
        row = self.current_row()
        if row and row[0] == "open":
            self.apply_text(row[1], row[1]["proposed"])

    def action_dismiss_finding(self) -> None:
        row = self.current_row()
        if row and row[0] == "open":
            st = checks.load_state(self.p.final_check)
            st["dismissed"].append(row[1])
            checks.save_state(self.p.final_check, st)
            self.after_change()

    def action_edit_finding(self) -> None:
        from jobs_tui.screens.review import EditTextScreen
        row = self.current_row()
        if not row or row[0] != "open":
            return
        item = row[1]
        edit = E.Edit(id=item["bullet_id"], path=f"{item['bullet_id']}.text", current=item["current"], proposed=item["proposed"])
        self.app.push_screen(EditTextScreen(edit), lambda text: text is not None and self.apply_text(item, text))

    def action_undo_finding(self) -> None:
        row = self.current_row()
        if not row or row[0] == "open":
            return
        kind, item = row
        st = checks.load_state(self.p.final_check)
        if kind == "dismissed":
            st["dismissed"].remove(item)
        else:
            path = f"{item['bullet_id']}.text"
            resume = Resume.load(self.p.resume_yaml)
            if resume.get(path) != item["after"]:
                self.app.notify("This bullet changed after the fix. Edit it by hand (y on the list).", severity="warning")
                return
            resume.set(path, item["before"])
            resume.save(self.p.resume_yaml)
            guard.snapshot(self.p)
            st["applied"].remove(item)
        checks.save_state(self.p.final_check, st)
        self.show_findings()

    def action_notes(self) -> None:
        self.app.open_notes(self.p)

    def action_finalize(self) -> None:
        from jobs_tui.screens.finalize import FinalizeScreen
        self.app.push_screen(FinalizeScreen(self.p), lambda ok: ok and self.app.pop_to_list())

    def action_back(self) -> None:
        self.app.pop_screen()
