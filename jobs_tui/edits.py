import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from jobs_tui.model import split_path

STATUSES = ("pending", "accepted", "rejected", "needs_revision")


@dataclass
class Edit:
    id: str
    op: str = "replace"
    path: str | None = None
    entry: str | None = None
    after: str | None = None
    current: str = ""
    proposed: str = ""
    reason: str = ""
    jd_alignment: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    status: str = "pending"
    final: str | None = None
    feedback: str = ""


def load_edits(path: Path) -> list[Edit]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text()).get("edits", [])
    known = Edit.__dataclass_fields__.keys()
    return [Edit(**{k: v for k, v in item.items() if k in known}) for item in raw]


def load_feedback(path: Path) -> dict[str, Decision]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text()).get("decisions", {})
    return {k: Decision(**v) for k, v in raw.items()}


def save_feedback(path: Path, decisions: dict[str, Decision]) -> None:
    path.write_text(json.dumps({"decisions": {k: asdict(v) for k, v in decisions.items()}}, indent=2) + "\n")


def status_of(edit_id: str, decisions: dict[str, Decision]) -> str:
    return decisions[edit_id].status if edit_id in decisions else "pending"


def counts(edits: list[Edit], decisions: dict[str, Decision]) -> dict[str, int]:
    out = {s: 0 for s in STATUSES}
    for e in edits:
        out[status_of(e.id, decisions)] += 1
    return out


def label(edit: Edit) -> str:
    if edit.op == "add":
        return f"+ {edit.entry}"
    node_id = split_path(edit.path)[0]
    return f"- {node_id}" if edit.op == "remove" else node_id
