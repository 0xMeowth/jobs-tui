import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from jobs_tui.model import split_path

STATUSES = ("pending", "accepted", "rejected")
STATES = ("open", "rework", "sent", "rejected", "rejected_reason", "accepted")
GLYPH = {"open": "○", "rework": "◐", "sent": "◑", "rejected": "×", "rejected_reason": "⊗", "accepted": "●"}


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
    revises: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    status: str = "pending"
    final: str | None = None
    comment: str = ""
    before: str | None = None
    applied_id: str | None = None
    sent_proposed: str | None = None


def base_id(edit_id: str) -> str:
    return re.sub(r"-r\d+$", "", edit_id)


def round_of_id(edit_id: str) -> int:
    m = re.search(r"-r(\d+)$", edit_id)
    return int(m.group(1)) if m else 0


def load_edits(path: Path) -> list[Edit]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text()).get("edits", [])
    known = Edit.__dataclass_fields__.keys()
    return [Edit(**{k: v for k, v in item.items() if k in known}) for item in raw]


def _migrate(raw: dict) -> Decision:
    raw = dict(raw)
    if "feedback" in raw:
        raw["comment"] = raw.pop("feedback")
    if raw.get("status") == "needs_revision":
        raw["status"] = "pending"
    known = Decision.__dataclass_fields__.keys()
    return Decision(**{k: v for k, v in raw.items() if k in known})


def _read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_feedback(path: Path) -> dict[str, Decision]:
    return {k: _migrate(v) for k, v in _read(path).get("decisions", {}).items()}


def load_request(path: Path) -> dict:
    return _read(path).get("request") or {"round": 0, "items": []}


def save_feedback(path: Path, decisions: dict[str, Decision], request: dict | None = None) -> None:
    if request is None:
        request = load_request(path)
    data = {"decisions": {k: asdict(v) for k, v in decisions.items()}, "request": request}
    path.write_text(json.dumps(data, indent=2) + "\n")


def status_of(edit_id: str, decisions: dict[str, Decision]) -> str:
    return decisions[edit_id].status if edit_id in decisions else "pending"


def state_of(edit_id: str, decisions: dict[str, Decision], proposed: str | None = None) -> str:
    d = decisions.get(edit_id, Decision())
    if d.status == "accepted":
        return "accepted"
    if d.status == "rejected":
        return "rejected_reason" if d.comment else "rejected"
    if d.comment and proposed is not None and d.sent_proposed == proposed:
        return "sent"
    return "rework" if d.comment else "open"


def counts(edits: list[Edit], decisions: dict[str, Decision]) -> dict[str, int]:
    out = {s: 0 for s in STATES}
    for e in edits:
        out[state_of(e.id, decisions, e.proposed)] += 1
    out["pending"] = out["open"] + out["rework"] + out["sent"]
    return out


def label(edit: Edit) -> str:
    if edit.op == "add":
        return f"+ {edit.entry}"
    node_id = split_path(edit.path)[0]
    return f"- {node_id}" if edit.op == "remove" else node_id
