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

    def compose(self) -> ComposeResult:
        yield Static("[b]RENDER[/b]  o open PDF · f auto-fit · t ask agent to trim · n finalize · Esc back", classes="help")
        yield Static("Rendering…", id="render-info")
        yield CommandBar()

    def on_mount(self) -> None:
        self.app.current = self.p
        self.run_render(False)

    @work(thread=True, exclusive=True, group="render")
    def run_render(self, fit: bool) -> None:
        try:
            r = render.autofit(self.app.jobs, self.p) if fit else render.render(self.app.jobs, self.p)
        except render.RenderError as err:
            self.app.call_from_thread(self.query_one("#render-info", Static).update, f"[red]Render failed[/red]\n\n{escape(str(err))}")
            self.app.call_from_thread(self.app.set_pages, None)
            return
        self.app.call_from_thread(self.show, r)

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
        pages = self.result.pages if self.result else 3
        self.app.send_to_agent(bridge.trim_prompt(self.p.root, pages))

    def action_finalize(self) -> None:
        self.app.notify("Finalize: built in Task 15")

    def action_back(self) -> None:
        self.app.pop_screen()
