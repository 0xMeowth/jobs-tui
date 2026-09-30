import shutil
import subprocess

import pytest

from jobs_tui import application, render

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


@needs_typst
def test_render_error_surfaces_typst_message(jobs_dir, app):
    app.resume_yaml.write_text("name: X\n")  # no contact block -> typst error
    with pytest.raises(render.RenderError) as e:
        render.render(jobs_dir, app)
    assert "contact" in str(e.value)


def test_missing_tool_raises_render_error(jobs_dir, app, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("No such file or directory: 'typst'")
    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(render.RenderError, match="typst"):
        render.render(jobs_dir, app)
