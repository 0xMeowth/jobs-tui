import os
import shlex
import subprocess
from pathlib import Path

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from textual import work

from jobs_tui import application, bridge, render
from jobs_tui.app import CommandBar
from jobs_tui.paths import AppPaths, list_applications


class ApplicationsScreen(Screen):
    BINDINGS = [
        Binding("n", "new_app", "New"),
        Binding("enter", "open_app", "Open", priority=True),
        Binding("b", "brief", "Brief"),
        Binding("r", "render", "Render"),
        Binding("f", "finalize", "Finalize"),
        Binding("t", "tracker", "Tracker"),
        Binding("y", "edit_yaml", "Edit YAML"),
        Binding("x", "delete_app", "Delete"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[b]JOB APPLICATIONS[/b]  n new · Enter review · b brief · r render · f finalize · y yaml · x delete · t tracker · p pair · : agent · q quit", classes="help")
        with Horizontal(id="body"):
            yield ListView(id="app-list")
            yield Static("No applications yet. Press n.", id="app-detail")
        yield CommandBar()

    async def on_mount(self) -> None:
        await self.refresh_list()

    async def on_screen_resume(self) -> None:
        await self.refresh_list()

    async def refresh_list(self, select: Path | None = None) -> None:
        lv = self.query_one("#app-list", ListView)
        keep = lv.index or 0
        await lv.clear()
        self.apps = []
        items = []
        bad = []
        for p in list_applications(self.app.jobs):
            try:
                meta = application.load(p)
                application.summary(p)
            except (OSError, ValueError, TypeError):
                bad.append(f"{p.company_slug}/{p.role_slug}")
                continue
            self.apps.append(p)
            mark = "✓ " if meta.submitted_date else "  "
            items.append(ListItem(Label(f"{mark}{meta.company}\n  {meta.role}"), name=str(p.root)))
        if bad:
            self.app.notify(f"Skipped unreadable application.json: {', '.join(bad)}", severity="warning")
        await lv.extend(items)
        if self.apps:
            roots = [p.root for p in self.apps]
            lv.index = roots.index(select) if select in roots else min(keep, len(self.apps) - 1)
            self.show_detail(self.apps[lv.index])
        else:
            self.app.current = None
            self.app.set_pages(None)
            self.query_one("#app-detail", Static).update("No applications yet. Press n.")

    def show_detail(self, p: AppPaths) -> None:
        self.app.current = p
        meta = application.load(p)
        s = application.summary(p)
        self.app.set_pages(s["pages"])
        lines = [
            f"[b]{escape(meta.company)}[/b] — {escape(meta.role)}", "",
            f"Created     {meta.created}",
            f"Submitted   {meta.submitted_date or 'no'}",
            f"URL         {escape(meta.url or '-')}", "",
            f"JD          {'imported' if s['jd'] else 'missing'}",
            f"Edits       {s['edits_pending']} pending of {s['edits_total']}",
            f"Pages       {s['pages'] if s['pages'] is not None else 'not rendered'}",
        ]
        self.query_one("#app-detail", Static).update("\n".join(lines))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None and event.item.name:
            self.show_detail(AppPaths(Path(event.item.name)))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "open_app" and self.focused is not None and any(isinstance(w, CommandBar) for w in self.focused.ancestors_with_self):
            return False
        return True

    def action_new_app(self) -> None:
        from jobs_tui.screens.new_application import NewApplicationScreen

        def done(p: AppPaths | None) -> None:
            self.call_later(self.refresh_list, p.root if p else None)
            if p is not None:
                self.app.current = p
                self.app.notify(f"Created {p.company_slug}/{p.role_slug}")
                self.brief(p)

        self.app.push_screen(NewApplicationScreen(), done)

    def action_open_app(self) -> None:
        if self.app.current:
            self.open_review(self.app.current)

    def open_review(self, p: AppPaths) -> None:
        from jobs_tui.screens.review import ReviewScreen
        self.app.push_screen(ReviewScreen(p))

    def action_brief(self) -> None:
        if self.app.current:
            self.brief(self.app.current)

    def brief(self, p: AppPaths) -> None:
        from jobs_tui.screens.brief import BriefScreen
        from jobs_tui.screens.pair import PairScreen

        def done(result: str | None) -> None:
            self.call_later(self.refresh_list)
            if result == "start":
                self.open_review(p)

        def paired(ok: bool) -> None:
            for bar in self.query(CommandBar):
                bar.refresh_panes()
            if ok:
                self.app.push_screen(BriefScreen(p), done)

        if self.app.bridge.pane_id is None and bridge.in_herdr():
            self.app.push_screen(PairScreen(), paired)
        else:
            self.app.push_screen(BriefScreen(p), done)

    def action_render(self) -> None:
        if self.app.current:
            from jobs_tui.screens.render_screen import RenderScreen
            self.app.push_screen(RenderScreen(self.app.current))

    def action_finalize(self) -> None:
        if self.app.current:
            from jobs_tui.screens.finalize import FinalizeScreen
            self.app.push_screen(FinalizeScreen(self.app.current), lambda _: self.call_later(self.refresh_list))

    def action_delete_app(self) -> None:
        p = self.app.current
        if not p:
            return
        if application.load(p).submitted_date:
            self.app.notify("Cannot delete a submitted application.", severity="warning")
            return
        from jobs_tui.screens.delete import DeleteScreen

        def done(deleted: bool | None) -> None:
            if deleted:
                self.app.notify(f"Deleted {p.company_slug}/{p.role_slug}")
            self.call_later(self.refresh_list)

        self.app.push_screen(DeleteScreen(p), done)

    def action_tracker(self) -> None:
        from jobs_tui.screens.tracker_screen import TrackerScreen
        self.app.push_screen(TrackerScreen(), lambda root: self.call_later(self.refresh_list, root))

    def action_edit_yaml(self) -> None:
        if not self.app.current:
            return
        editor = os.environ.get("EDITOR", "vi")
        p = self.app.current
        try:
            with self.app.suspend():
                subprocess.run(shlex.split(editor) + [str(p.resume_yaml)])
        except OSError as err:
            self.app.notify(escape(f"Cannot run editor {editor!r}: {err}"), severity="error")
            return
        self.rerender(p)

    @work(thread=True, exclusive=True, group="render")
    def rerender(self, p: AppPaths) -> None:
        try:
            render.render(self.app.jobs, p)
        except render.RenderError as err:
            self.app.call_from_thread(self.app.notify, escape(f"Render failed: {err}"), severity="error")
        self.app.call_from_thread(self.refresh_list, p.root)
