import re
from pathlib import Path

import yaml


def split_path(path: str) -> tuple[str, str]:
    node_id, _, field = path.rpartition(".")
    if not node_id:
        raise ValueError(f"path needs an id and a field: {path!r}")
    return node_id, field


class Resume:
    def __init__(self, data: dict):
        self.data = data
        self._reindex()

    @classmethod
    def load(cls, path: Path) -> "Resume":
        return cls(yaml.safe_load(path.read_text()))

    def save(self, path: Path) -> None:
        path.write_text(yaml.safe_dump(self.data, allow_unicode=True, sort_keys=False, width=1000))

    def _reindex(self) -> None:
        self._index: dict[str, dict] = {}
        self._parent: dict[str, list] = {}
        for section in self.data.get("sections", []):
            self._index[section["id"]] = section
            for b in section.get("bullets", []):
                self._index[b["id"]] = b
                self._parent[b["id"]] = section["bullets"]
            for entry in section.get("entries", []):
                self._index[entry["id"]] = entry
                self._parent[entry["id"]] = section["entries"]
                for b in entry.get("bullets", []):
                    self._index[b["id"]] = b
                    self._parent[b["id"]] = entry["bullets"]

    def node(self, node_id: str) -> dict:
        try:
            return self._index[node_id]
        except KeyError:
            raise KeyError(f"no unit with id {node_id!r}") from None

    def has(self, node_id: str) -> bool:
        return node_id in self._index

    def parent_list(self, node_id: str) -> list:
        return self._parent[node_id]

    def get(self, path: str) -> str:
        node_id, field = split_path(path)
        return self.node(node_id)[field]

    def set(self, path: str, value: str) -> None:
        node_id, field = split_path(path)
        node = self.node(node_id)
        if field not in node:
            raise KeyError(f"{node_id!r} has no field {field!r}")
        node[field] = value

    def add_bullet(self, entry_id: str, text: str, after: str | None) -> str:
        entry = self.node(entry_id)
        bullets = entry.setdefault("bullets", [])
        used = [int(m.group(1)) for b in bullets if (m := re.fullmatch(rf"{re.escape(entry_id)}\.b(\d+)", b["id"]))]
        new_id = f"{entry_id}.b{max(used, default=0) + 1}"
        bullet = {"id": new_id, "text": text}
        if after is None:
            bullets.append(bullet)
        else:
            try:
                pos = next(i for i, b in enumerate(bullets) if b["id"] == after) + 1
            except StopIteration:
                raise KeyError(f"no bullet {after!r} in entry {entry_id!r}") from None
            bullets.insert(pos, bullet)
        self._reindex()
        return new_id

    def remove(self, node_id: str) -> None:
        node = self.node(node_id)
        self.parent_list(node_id).remove(node)
        self._reindex()

    def units(self) -> list[tuple[str, str]]:
        out = []
        for section in self.data.get("sections", []):
            for b in section.get("bullets", []):
                out.append((b["id"], b["text"]))
            for entry in section.get("entries", []):
                out.append((entry["id"], f'{entry.get("title", "")} — {entry.get("org", "")}'))
                for b in entry.get("bullets", []):
                    out.append((b["id"], b["text"]))
        return out


def apply_edit(resume: Resume, edit: dict, final: str | None) -> str | None:
    op = edit.get("op", "replace")
    text = final if final is not None else edit.get("proposed", "")
    if op == "replace":
        resume.set(edit["path"], text)
        return split_path(edit["path"])[0]
    if op == "add":
        return resume.add_bullet(edit["entry"], text, edit.get("after"))
    if op == "remove":
        node_id = edit["path"] if resume.has(edit["path"]) else split_path(edit["path"])[0]
        resume.remove(node_id)
        return node_id
    raise ValueError(f"unknown op {op!r}")
