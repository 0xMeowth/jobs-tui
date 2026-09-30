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
    workspace: str = ""


def _run(args: list[str]) -> str:
    try:
        proc = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        raise RuntimeError("herdr timed out")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"herdr {' '.join(args)} failed")
    return proc.stdout


def in_herdr() -> bool:
    return os.environ.get("HERDR_ENV") == "1" and shutil.which("herdr") is not None


def _pane(d: dict) -> Pane:
    return Pane(d["pane_id"], d.get("agent", ""), d.get("agent_status", "unknown"), d.get("cwd", ""), d.get("terminal_title_stripped", ""))


def _workspace_labels() -> dict[str, str]:
    try:
        workspaces = json.loads(_run(["workspace", "list"]))["result"]["workspaces"]
        return {w["workspace_id"]: w.get("label", "") for w in workspaces}
    except Exception:
        return {}


def list_agent_panes() -> list[Pane]:
    try:
        raw = [d for d in json.loads(_run(["pane", "list"]))["result"]["panes"] if d.get("agent") in AGENTS]
        panes = [(_pane(d), d.get("workspace_id", "")) for d in raw]
    except Exception:
        return []
    labels = _workspace_labels()
    for pane, ws in panes:
        pane.workspace = labels.get(ws, "")
    return [pane for pane, _ in panes]


def pane_label(p: Pane) -> str:
    title = p.title if len(p.title) <= 40 else p.title[:39] + "…"
    return " · ".join(x for x in (p.agent, p.workspace, title) if x)


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


def feedback_prompt(root: Path, round: int) -> str:
    return (
        f'Read the "request" block in review-feedback.json in {root}. '
        f'For each item with action "revise", replace that edit in proposed-edits.json with exactly one new edit that '
        f'addresses my comment, with id "<base>-r{round}" (base is the item id without any -rN suffix) and '
        f'"revises": "<item id>", in the same list position. '
        'Leave every edit not listed in "request" exactly as it is. '
        'If a comment cannot be met without adding facts absent from resume.yaml, write the closest honest revision and name the missing fact in its reason. '
        'Do not ask me questions. Do not edit resume.yaml.'
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
        try:
            run_in_pane(pane.pane_id, text)
        except (RuntimeError, OSError):
            copy_to_clipboard(text)
            return "copied"
        return "sent"
