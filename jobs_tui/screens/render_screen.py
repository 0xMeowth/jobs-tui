import subprocess

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from jobs_tui import render
from jobs_tui.app import CommandBar
from jobs_tui.paths import AppPaths


class RenderScreen(Screen):
    AUTO_FOCUS = ""
    BINDINGS = [
        Binding("o", "open_pdf", "Open PDF"),
        Binding("s", "save", "Save PDF"),
        Binding("f", "finalize", "Finalize"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p

    def compose(self) -> ComposeResult:
        yield Static("[b]RENDER[/b]  o open PDF · s save PDF · f finalize · p pair · Esc back", classes="help")
        yield Static("Rendering…", id="render-info")
        yield CommandBar()

    def on_mount(self) -> None:
        self.app.current = self.p
        self._render_worker()

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
            self.query_one("#render-info", Static).update(f"[red]Render failed[/red]\n\n{escape(error or '')}")
            self.app.set_pages(None)
            return
        self.show(r)

    def show(self, r: render.RenderResult) -> None:
        self.app.set_pages(r.pages)
        over = r.pages - 2
        self.query_one("#render-info", Static).update(
            f"Pages       {r.pages}  (limit 2)" + ("  [red]over by " + str(over) + "[/red]" if over > 0 else "  [green]ok[/green]"))

    def action_open_pdf(self) -> None:
        if self.p.resume_pdf.exists():
            subprocess.Popen(["open", str(self.p.resume_pdf)])

    def action_save(self) -> None:
        from jobs_tui.screens.finalize import SaveScreen
        self.app.push_screen(SaveScreen(self.p))

    def action_finalize(self) -> None:
        from jobs_tui.screens.finalize import FinalizeScreen
        self.app.push_screen(FinalizeScreen(self.p), lambda ok: ok and self.app.pop_to_list())

    def action_back(self) -> None:
        self.app.pop_screen()
