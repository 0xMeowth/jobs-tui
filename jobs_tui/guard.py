import shutil

from jobs_tui.paths import AppPaths

OUTSIDE_CHANGE = ("resume.yaml changed outside the app. Press y on the list to adopt it, "
                  "or copy preview/resume.snapshot.yaml back over it.")


def snapshot(p: AppPaths) -> None:
    """Record resume.yaml as the app last wrote (or adopted) it."""
    p.preview_dir.mkdir(exist_ok=True)
    p.resume_snapshot.unlink(missing_ok=True)
    shutil.copy(p.resume_yaml, p.resume_snapshot)


def outside_change(p: AppPaths) -> bool:
    if not p.resume_snapshot.exists() or not p.resume_yaml.exists():
        return False
    return p.resume_yaml.read_bytes() != p.resume_snapshot.read_bytes()


def lock(p: AppPaths) -> None:
    p.resume_yaml.chmod(0o444)


def unlock(p: AppPaths) -> None:
    if p.resume_yaml.exists():
        p.resume_yaml.chmod(0o644)
