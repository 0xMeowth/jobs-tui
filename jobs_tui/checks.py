import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_IRREGULAR = [
    ("modelling", "modeling"), ("modelled", "modeled"), ("modeller", "modeler"), ("modellers", "modelers"),
    ("labelled", "labeled"), ("labelling", "labeling"), ("travelled", "traveled"), ("travelling", "traveling"),
    ("cancelled", "canceled"), ("cancelling", "canceling"), ("totalling", "totaling"), ("totalled", "totaled"),
    ("signalling", "signaling"), ("fuelled", "fueled"),
    ("behaviour", "behavior"), ("behaviours", "behaviors"), ("behavioural", "behavioral"),
    ("colour", "color"), ("colours", "colors"), ("favour", "favor"), ("favourite", "favorite"),
    ("labour", "labor"), ("honour", "honor"), ("neighbour", "neighbor"),
    ("centre", "center"), ("centres", "centers"), ("centred", "centered"), ("fibre", "fiber"),
    ("catalogue", "catalog"), ("analogue", "analog"), ("defence", "defense"), ("offence", "offense"),
    ("enrolment", "enrollment"), ("fulfil", "fulfill"), ("fulfilment", "fulfillment"),
    ("instalment", "installment"), ("skilful", "skillful"), ("ageing", "aging"), ("grey", "gray"),
    ("analyse", "analyze"), ("analysed", "analyzed"), ("analysing", "analyzing"), ("analyser", "analyzer"),
    ("catalyse", "catalyze"), ("paralyse", "paralyze"),
]
_ISE_STEMS = [
    "optimi", "prioriti", "organi", "utili", "visuali", "standardi", "recogni", "minimi", "maximi",
    "summari", "customi", "speciali", "finali", "initiali", "normali", "moneti", "characteri", "categori",
    "authori", "capitali", "operationali", "synchroni", "tokeni", "vectori", "parameteri", "containeri",
    "moderni", "centrali", "decentrali", "generali", "personali", "mobili", "emphasi", "critici", "reali",
    "digiti", "industriali", "locali", "globali", "rationali", "productioni", "harmoni", "memori",
]
_ISE_SUFFIXES = ["e", "es", "ed", "ing", "er", "ers", "ation", "ations", "able"]

UK_TO_US: dict[str, str] = dict(_IRREGULAR)
for stem in _ISE_STEMS:
    for suffix in _ISE_SUFFIXES:
        UK_TO_US[f"{stem}s{suffix}"] = f"{stem}z{suffix}"
US_TO_UK = {us: uk for uk, us in UK_TO_US.items()}
_WORD = re.compile(r"[A-Za-z]+")


@dataclass
class Finding:
    bullet_id: str
    current: str
    proposed: str
    rules: list[str] = field(default_factory=list)


def entry_bullets(data: dict) -> list[tuple[str, str]]:
    return [(b["id"], b["text"]) for s in data.get("sections", []) for e in s.get("entries", []) for b in e.get("bullets", [])]


def _counts(text: str) -> tuple[int, int]:
    words = [w.lower() for w in _WORD.findall(text)]
    return sum(w in UK_TO_US for w in words), sum(w in US_TO_UK for w in words)


def posting_signal(jd: str) -> str | None:
    uk, us = _counts(jd)
    if uk and not us:
        return "uk"
    if us and not uk:
        return "us"
    return None


def _match_case(src: str, word: str) -> str:
    if src.isupper():
        return word.upper()
    return word[0].upper() + word[1:] if src[0].isupper() else word


def _respell(text: str, table: dict[str, str]) -> str:
    return _WORD.sub(lambda m: _match_case(m.group(), table[m.group().lower()]) if m.group().lower() in table else m.group(), text)


def _spacing(text: str) -> str:
    text = re.sub(r",(?=[A-Za-z])", ", ", text)
    text = re.sub(r" {2,}", " ", text)
    return re.sub(r" +([,.;:])", r"\1", text)


def _characters(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s*—\s*", ", ", text)


def local_findings(data: dict, jd: str) -> list[Finding]:
    bullets = entry_bullets(data)
    uk = sum(_counts(t)[0] for _, t in bullets)
    us = sum(_counts(t)[1] for _, t in bullets)
    target = posting_signal(jd)
    if target is None and uk and us:
        target = "uk" if uk >= us else "us"
    respell = {"uk": US_TO_UK, "us": UK_TO_US}.get(target or "")
    spell_rule = {"uk": "British spelling", "us": "American spelling"}.get(target or "")
    ends = [t.rstrip().endswith(".") for _, t in bullets]
    period = None if all(ends) or not any(ends) else sum(ends) > len(ends) - sum(ends)

    findings = []
    for bullet_id, text in bullets:
        proposed, rules = text, []
        for rule, fix in (("spacing", _spacing), ("quotes and dashes", _characters)):
            if (fixed := fix(proposed)) != proposed:
                proposed, rules = fixed, rules + [rule]
        if respell and (fixed := _respell(proposed, respell)) != proposed:
            proposed, rules = fixed, rules + [spell_rule]
        if period is not None and proposed.rstrip().endswith(".") != period:
            stripped = proposed.rstrip()
            proposed, rules = (stripped + "." if period else stripped[:-1]), rules + ["trailing period"]
        if rules:
            findings.append(Finding(bullet_id, text, proposed, rules))
    return findings


def load_state(path: Path) -> dict:
    try:
        st = json.loads(path.read_text())
    except (OSError, ValueError):
        st = {}
    if not isinstance(st, dict):
        st = {}
    return {"status": "not checked", "checks": [], "snapshot": {}, "dismissed": [], "applied": [], **st}


def save_state(path: Path, st: dict) -> None:
    path.write_text(json.dumps(st, indent=2) + "\n")


def open_findings(data: dict, jd: str, st: dict) -> list[Finding]:
    dismissed = {(d["bullet_id"], d["current"], d["proposed"]) for d in st["dismissed"]}
    return [f for f in local_findings(data, jd) if (f.bullet_id, f.current, f.proposed) not in dismissed]


def changed_since(data: dict, st: dict) -> int:
    now = dict(entry_bullets(data))
    then = st["snapshot"]
    return sum(now.get(k) != then.get(k) for k in set(now) | set(then))


def mark_checked(st: dict, data: dict, kinds: list[str]) -> None:
    st.update(status="checked", checks=kinds, snapshot=dict(entry_bullets(data)))


def finding_dict(f: Finding) -> dict:
    return asdict(f)
