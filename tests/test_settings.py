import json

from jobs_tui import settings


def test_defaults_when_missing(tmp_path):
    s = settings.load(tmp_path)
    assert s.local_checks is True and s.agent_checks is False


def test_save_load_roundtrip(tmp_path):
    settings.save(tmp_path, settings.Settings(local_checks=False, agent_checks=True))
    assert settings.load(tmp_path) == settings.Settings(local_checks=False, agent_checks=True)


def test_bad_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "settings.json").write_text("{not json")
    assert settings.load(tmp_path) == settings.Settings()
    (tmp_path / "settings.json").write_text(json.dumps({"local_checks": "yes", "agent_checks": True, "old": 1}))
    assert settings.load(tmp_path) == settings.Settings(local_checks=True, agent_checks=True)
