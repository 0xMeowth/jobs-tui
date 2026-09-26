import shutil
import subprocess
from pathlib import Path

import pytest

from jobs_tui import application, paths, render

HAS_TYPST = shutil.which("typst") is not None and shutil.which("pdfinfo") is not None
needs_typst = pytest.mark.skipif(not HAS_TYPST, reason="typst and poppler required")


@pytest.fixture
def app(jobs_dir):
    return application.create(jobs_dir, "Acme", "Analyst", None)


@needs_typst
def test_render_produces_pdf_and_previews(jobs_dir, app):
    r = render.render(jobs_dir, app)
    assert r.pdf == app.resume_pdf and r.pdf.exists()
    assert r.pages == 1
    assert [p.name for p in r.previews] == ["page-1.png"]
    assert r.knobs == {}


@needs_typst
def test_render_error_surfaces_typst_message(jobs_dir, app):
    app.resume_yaml.write_text("name: X\n")  # no contact block -> typst error
    with pytest.raises(render.RenderError) as e:
        render.render(jobs_dir, app)
    assert "contact" in str(e.value) or "error" in str(e.value)


def test_autofit_walks_ladder_and_saves_knobs(jobs_dir, app, monkeypatch):
    pages_by_call = iter([3, 3, 2])
    def fake_compile(jobs, p, knobs):
        p.resume_pdf.write_bytes(b"%PDF")
        return p.resume_pdf
    monkeypatch.setattr(render, "compile", fake_compile)
    monkeypatch.setattr(render, "page_count", lambda pdf: next(pages_by_call))
    monkeypatch.setattr(render, "previews", lambda pdf, out: [])
    r = render.autofit(jobs_dir, app)
    assert r.pages == 2
    assert r.knobs == render.LADDER[2]
    assert application.load(app).fit == render.LADDER[2]


def test_autofit_reports_failure_when_nothing_fits(jobs_dir, app, monkeypatch):
    monkeypatch.setattr(render, "compile", lambda jobs, p, knobs: p.resume_pdf)
    monkeypatch.setattr(render, "page_count", lambda pdf: 3)
    monkeypatch.setattr(render, "previews", lambda pdf, out: [])
    r = render.autofit(jobs_dir, app)
    assert r.pages == 3
    assert r.knobs == render.LADDER[-1]
    assert application.load(app).fit == render.LADDER[-1]
