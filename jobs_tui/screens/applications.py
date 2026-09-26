import os
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, Static

from jobs_tui import application
from jobs_tui.app import CommandBar
from jobs_tui.paths import AppPaths, list_applications


class ApplicationsScreen(Screen):
    BINDINGS = [
        Binding("n", "new_app", "New"),
        Binding("enter", "open_app", "Open", priority=True),
        Binding("t", "tracker", "Tracker"),
        Binding("y", "edit_yaml", "Edit YAML"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[b]JOB APPLICATIONS[/b]  n new · Enter open · t tracker · y edit yaml · : agent · q quit", classes="help")
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
            f"[b]{meta.company}[/b] — {meta.role}", "",
            f"Created     {meta.created}",
            f"Submitted   {meta.submitted_date or 'no'}",
            f"URL         {meta.url or '-'}", "",
            f"JD          {'imported' if s['jd'] else 'missing'}",
            f"Edits       {s['edits_pending']} pending of {s['edits_total']}",
            f"Pages       {s['pages'] if s['pages'] is not None else 'not rendered'}", "",
            "[b]Enter[/b] review · [b]b[/b] brief · [b]r[/b] render · [b]f[/b] finalize",
        ]
        self.query_one("#app-detail", Static).update("\n".join(lines))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None and event.item.name:
            self.show_detail(AppPaths(Path(event.item.name)))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "open_app" and isinstance(self.focused, Input):
            return False
        return True

    def action_new_app(self) -> None:
        from jobs_tui.screens.new_application import NewApplicationScreen

        def done(p: AppPaths | None) -> None:
            self.call_later(self.refresh_list, p.root if p else None)
            if p is not None:
                self.app.current = p
                self.app.notify(f"Created {p.company_slug}/{p.role_slug}")

        self.app.push_screen(NewApplicationScreen(), done)

    def action_open_app(self) -> None:
        if self.app.current:
            self.app.notify("Review: built in Task 13")

    def action_tracker(self) -> None:
        self.app.notify("Tracker: built in Task 16")

    def action_edit_yaml(self) -> None:
        if not self.app.current:
            return
        editor = os.environ.get("EDITOR", "vi")
        with self.app.suspend():
            subprocess.run([editor, str(self.app.current.resume_yaml)])
