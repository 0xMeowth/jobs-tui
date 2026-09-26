from pathlib import Path

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
