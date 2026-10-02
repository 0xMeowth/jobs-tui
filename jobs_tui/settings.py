import json
from dataclasses import asdict, dataclass
from pathlib import Path

from jobs_tui.paths import settings_json


@dataclass
class Settings:
    local_checks: bool = True
    agent_checks: bool = False


def load(jobs: Path) -> Settings:
    try:
        raw = json.loads(settings_json(jobs).read_text())
    except (OSError, ValueError):
        return Settings()
    if not isinstance(raw, dict):
        return Settings()
    return Settings(**{k: v for k, v in raw.items() if k in Settings.__dataclass_fields__ and isinstance(v, bool)})


def save(jobs: Path, s: Settings) -> None:
    settings_json(jobs).write_text(json.dumps(asdict(s), indent=2) + "\n")
