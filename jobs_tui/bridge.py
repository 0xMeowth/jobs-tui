import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

AGENTS = {"codex", "claude"}
READY = {"idle", "blocked", "done"}


@dataclass
class Pane:
    pane_id: str
    agent: str
    status: str
    cwd: str
    title: str


def _run(args: list[str]) -> str:
    proc = subprocess.run(["herdr", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"herdr {' '.join(args)} failed")
    return proc.stdout


def in_herdr() -> bool:
    return os.environ.get("HERDR_ENV") == "1" and shutil.which("herdr") is not None


def _pane(d: dict) -> Pane:
    return Pane(d["pane_id"], d.get("agent", ""), d.get("agent_status", "unknown"), d.get("cwd", ""), d.get("terminal_title_stripped", ""))


def list_agent_panes() -> list[Pane]:
    panes = json.loads(_run(["pane", "list"]))["result"]["panes"]
    return [_pane(p) for p in panes if p.get("agent") in AGENTS]


def get_pane(pane_id: str) -> Pane | None:
    try:
        return _pane(json.loads(_run(["pane", "get", pane_id]))["result"]["pane"])
    except Exception:
        return None


def run_in_pane(pane_id: str, text: str) -> None:
    _run(["pane", "run", pane_id, text])


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=False)


def start_review_prompt(root: Path) -> str:
    return (
        f"Review the job application in {root}. Read review-request.md, jd.md and resume.yaml there. "
        "Discuss any important uncertainties with me first, then write your suggestions to proposed-edits.json "
        "in that folder. Do not edit resume.yaml."
    )


def feedback_prompt(root: Path) -> str:
    return (
        f"Read review-feedback.json in {root}. Revise the edits whose status is needs_revision using my feedback, "
        "and rewrite proposed-edits.json. Do not edit resume.yaml."
    )


def trim_prompt(root: Path, pages: int) -> str:
    return (
        f"The resume in {root} renders to {pages} pages and must fit 2. Propose trims or merges of bullets in "
        "resume.yaml as edits in proposed-edits.json. Do not edit resume.yaml."
    )


def free_text_prompt(root: Path | None, text: str) -> str:
    return f"Regarding {root}: {text}" if root else text


class Bridge:
    def __init__(self, pane_id: str | None = None):
        self.pane_id = pane_id

    def pane(self) -> Pane | None:
        if not self.pane_id or not in_herdr():
            return None
        return get_pane(self.pane_id)

    def deliver(self, text: str, force: bool = False) -> str:
        pane = self.pane()
        if pane is None:
            copy_to_clipboard(text)
            return "copied"
        if pane.status not in READY and not force:
            return "busy"
        run_in_pane(pane.pane_id, text)
        return "sent"
