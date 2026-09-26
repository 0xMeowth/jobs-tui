import argparse
import shutil
import sys
from datetime import date
from importlib.resources import files
from pathlib import Path

from jobs_tui import doctor, jd
from jobs_tui.paths import jobs_dir, master_yaml, template_typ


def cmd_init(jobs: Path) -> int:
    assets = files("jobs_tui") / "assets"
    (jobs / "templates").mkdir(parents=True, exist_ok=True)
    (jobs / "companies").mkdir(exist_ok=True)
    for src, dst in [("resume.typ", template_typ(jobs)), ("resume-example.yaml", master_yaml(jobs))]:
        if not dst.exists():
            shutil.copy(str(assets / src), dst)
            print(f"created {dst}")
    return 0


def cmd_doctor(jobs: Path) -> int:
    checks = doctor.run(jobs)
    for c in checks:
        mark = "ok " if c.ok else ("!! " if c.required else "-- ")
        print(f"{mark}{c.name:10s} {c.detail}")
    return 0 if all(c.ok or not c.required for c in checks) else 1


def cmd_jd(url: str) -> int:
    job_id = jd.linkedin_job_id(url)
    if job_id:
        j, _ = jd.fetch_linkedin(job_id, url)
    else:
        html = jd.fetch_http(url)
        j = jd.extract_generic(html, url, "http") or jd.extract_generic(jd.fetch_browser(url), url, "browser")
        if j is None:
            print("Could not extract a job description.", file=sys.stderr)
            return 1
    print(jd.to_markdown(j, date.today()), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobs-tui")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="create templates in JOBS_DIR")
    sub.add_parser("doctor", help="check dependencies")
    p_jd = sub.add_parser("jd", help="fetch a job description to stdout")
    p_jd.add_argument("url")
    args = parser.parse_args(argv)
    jobs = jobs_dir()
    if args.cmd == "init":
        return cmd_init(jobs)
    if args.cmd == "doctor":
        return cmd_doctor(jobs)
    if args.cmd == "jd":
        return cmd_jd(args.url)
    from jobs_tui.app import JobsApp
    JobsApp(jobs).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
