import subprocess

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from jobs_tui import bridge, render
from jobs_tui.app import CommandBar
from jobs_tui.paths import AppPaths


class RenderScreen(Screen):
    AUTO_FOCUS = ""
    BINDINGS = [
        Binding("o", "open_pdf", "Open PDF"),
        Binding("f", "autofit", "Auto-fit"),
        Binding("t", "trim", "Ask agent to trim"),
        Binding("n", "finalize", "Finalize"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, p: AppPaths) -> None:
        super().__init__()
        self.p = p
        self.result: render.RenderResult | None = None
        self._gen = 0

    def compose(self) -> ComposeResult:
        yield Static("[b]RENDER[/b]  o open PDF · f auto-fit · t ask agent to trim · n finalize · Esc back", classes="help")
        yield Static("Rendering…", id="render-info")
        yield CommandBar()

    def on_mount(self) -> None:
        self.app.current = self.p
        self.run_render(False)

    def run_render(self, fit: bool) -> None:
        self._gen += 1
        self._render_worker(fit, self._gen)

    @work(thread=True, exclusive=True, group="render")
    def _render_worker(self, fit: bool, gen: int) -> None:
        try:
            r = render.autofit(self.app.jobs, self.p) if fit else render.render(self.app.jobs, self.p)
        except render.RenderError as err:
            self.app.call_from_thread(self._render_done, gen, None, str(err))
            return
        self.app.call_from_thread(self._render_done, gen, r, None)

    def _render_done(self, gen: int, r: render.RenderResult | None, error: str | None) -> None:
        if not self.is_current or gen != self._gen:
            return
        if r is None:
            self.query_one("#render-info", Static).update(f"[red]Render failed[/red]\n\n{escape(error or '')}")
            self.app.set_pages(None)
            return
        self.show(r)

    def show(self, r: render.RenderResult) -> None:
        self.result = r
        self.app.set_pages(r.pages)
        over = r.pages - 2
        knobs = ", ".join(f"{k}={v}" for k, v in r.knobs.items()) or "defaults"
        lines = [
            f"Pages       {r.pages}  (limit 2)" + ("  [red]over by " + str(over) + "[/red]" if over > 0 else "  [green]ok[/green]"),
            f"Previews    {escape(', '.join(p.name for p in r.previews)) or '-'}",
            f"Fit knobs   {knobs}",
            f"PDF         {escape(str(r.pdf))}",
        ]
        if over > 0:
            lines += ["", "Press f to tighten spacing, or t to ask the agent to trim content."]
        self.query_one("#render-info", Static).update("\n".join(lines))

    def action_open_pdf(self) -> None:
        if self.p.resume_pdf.exists():
            subprocess.Popen(["open", str(self.p.resume_pdf)])

    def action_autofit(self) -> None:
        self.query_one("#render-info", Static).update("Auto-fitting…")
        self.run_render(True)

    def action_trim(self) -> None:
        if self.result is None:
            self.app.notify("Render has not finished yet")
            return
        self.app.send_to_agent(bridge.trim_prompt(self.p.root, self.result.pages))

    def action_finalize(self) -> None:
        from jobs_tui.screens.finalize import FinalizeScreen
        self.app.push_screen(FinalizeScreen(self.p))

    def action_back(self) -> None:
        self.app.pop_screen()
