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


@needs_typst
def test_starter_template_handles_projects_and_contact(jobs_dir, app):
    import yaml
    data = yaml.safe_load(app.resume_yaml.read_text())
    data["contact"]["location"] = "Wellington"
    data["sections"].append({"id": "projects", "title": "Projects", "entries": [
        {"id": "bot", "org": "Recipe Bot", "url": "github.com/ada/recipe-bot", "bullets": [{"id": "bot.b1", "text": "Built a recipe bot"}]},
    ]})
    app.resume_yaml.write_text(yaml.safe_dump(data, allow_unicode=True))
    r = render.render(jobs_dir, app)
    text = subprocess.run(["pdftotext", str(r.pdf), "-"], capture_output=True, text=True, check=True).stdout
    assert text.splitlines()[0] == "Ada Example"
    assert "Wellington | (65) 0000 0000 | ada@example.com" in text
    assert "github.com/ada/recipe-bot" in text
