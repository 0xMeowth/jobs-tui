from pathlib import Path

import pytest

from jobs_tui import cli, doctor


def test_doctor_reports_missing_template(jobs_dir, monkeypatch):
    (jobs_dir / "templates" / "resume.typ").unlink(missing_ok=True)
    monkeypatch.setattr(doctor.shutil, "which", lambda n: "/x/" + n)
    monkeypatch.setattr(doctor, "_typst_fonts", lambda: "Nunito\nArial\n")
    checks = {c.name: c for c in doctor.run(jobs_dir)}
    assert checks["typst"].ok and checks["nunito"].ok
    assert not checks["template"].ok


def test_init_copies_assets(tmp_path, monkeypatch, capsys):
    jobs = tmp_path / "j"
    monkeypatch.setenv("JOBS_DIR", str(jobs))
    assert cli.main(["init"]) == 0
    assert (jobs / "templates" / "resume.typ").exists()
    assert (jobs / "templates" / "resume-master.yaml").exists()
    assert (jobs / "companies").is_dir()
    text = (jobs / "templates" / "resume-master.yaml").read_text()
    assert cli.main(["init"]) == 0
    assert (jobs / "templates" / "resume-master.yaml").read_text() == text


def test_jd_command_prints_markdown(monkeypatch, capsys):
    from jobs_tui import jd
    fix = (Path(__file__).parent / "fixtures" / "linkedin_guest_4000000001.html").read_text()
    monkeypatch.setattr(jd, "fetch_linkedin", lambda job_id, url, timeout=8: (jd.parse_linkedin(fix, url), fix))
    assert cli.main(["jd", "https://www.linkedin.com/jobs/view/4000000001"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Pastry Chef")


def test_main_refuses_without_templates(tmp_path, monkeypatch, capsys):
    from jobs_tui.app import JobsApp
    jobs = tmp_path / "empty"
    jobs.mkdir()
    monkeypatch.setenv("JOBS_DIR", str(jobs))
    monkeypatch.setattr(JobsApp, "run", lambda self: pytest.fail("app launched"))
    assert cli.main([]) == 1
    assert "jobs-tui init" in capsys.readouterr().out


def test_doctor_chrome_optional(jobs_dir, monkeypatch):
    monkeypatch.setattr(doctor, "CHROME", str(jobs_dir / "no-chrome"))
    checks = {c.name: c for c in doctor.run(jobs_dir)}
    assert not checks["chrome"].ok and not checks["chrome"].required


def test_doctor_lists_fonts_once(jobs_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(doctor, "_typst_fonts", lambda: calls.append(1) or "Nunito")
    doctor.run(jobs_dir)
    assert len(calls) == 1


def test_jd_command_falls_back_to_browser(monkeypatch, capsys):
    from jobs_tui import jd
    monkeypatch.setattr(jd, "fetch_http", lambda url: (_ for _ in ()).throw(jd.JDError("HTTP 403")))
    monkeypatch.setattr(jd, "fetch_browser", lambda url: "<html></html>")
    monkeypatch.setattr(jd, "extract_generic", lambda html, url, method: jd.JD("T", None, None, url, method, "body") if method == "browser" else None)
    assert cli.main(["jd", "https://careers.example.com/1"]) == 0
    assert "via browser" in capsys.readouterr().out


def test_jd_command_failure_returns_1(monkeypatch, capsys):
    from jobs_tui import jd
    monkeypatch.setattr(jd, "fetch_http", lambda url: (_ for _ in ()).throw(jd.JDError("HTTP 403")))
    monkeypatch.setattr(jd, "fetch_browser", lambda url: (_ for _ in ()).throw(jd.JDError("Browser fetch failed: no chrome")))
    assert cli.main(["jd", "https://careers.example.com/1"]) == 1
    assert "Browser fetch failed" in capsys.readouterr().err
