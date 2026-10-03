import json

from jobs_tui import settings


def test_defaults_when_missing(tmp_path):
    assert settings.load(tmp_path).local_checks is True


def test_save_load_roundtrip(tmp_path):
    settings.save(tmp_path, settings.Settings(local_checks=False))
    assert settings.load(tmp_path) == settings.Settings(local_checks=False)


def test_bad_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "settings.json").write_text("{not json")
    assert settings.load(tmp_path) == settings.Settings()
    (tmp_path / "settings.json").write_text(json.dumps({"local_checks": "yes", "agent_checks": True}))
    assert settings.load(tmp_path) == settings.Settings(local_checks=True)
