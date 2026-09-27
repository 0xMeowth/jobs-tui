from datetime import date
from pathlib import Path

import pytest

from jobs_tui import jd
from jobs_tui.paths import AppPaths

FIX = Path(__file__).parent / "fixtures" / "linkedin_guest_4000000001.html"
SEARCH_URL = "https://www.linkedin.com/jobs/search-results/?currentJobId=4000000001&keywords=x"


def test_linkedin_job_id_forms():
    assert jd.linkedin_job_id(SEARCH_URL) == "4000000001"
    assert jd.linkedin_job_id("https://www.linkedin.com/jobs/view/4000000001") == "4000000001"
    assert jd.linkedin_job_id("https://www.linkedin.com/jobs/view/pastry-chef-at-northwind-bakery-4000000001/") == "4000000001"
    assert jd.linkedin_job_id("https://sg.linkedin.com/jobs/view/4000000001/?refId=x") == "4000000001"
    assert jd.linkedin_job_id("https://careers.example.com/job/12") is None
    assert jd.linkedin_job_id(
        "https://www.linkedin.com/jobs/view/analyst-12-month-contract-at-foo-4000000001/"
    ) == "4000000001"


def test_parse_linkedin_fixture():
    j = jd.parse_linkedin(FIX.read_text(), SEARCH_URL)
    assert j.title == "Pastry Chef"
    assert j.company == "Northwind Bakery"
    assert j.location == "Wellington, New Zealand"
    assert j.method == "linkedin"
    assert j.text.startswith("**Who We Are**\n")
    assert "Show more" not in j.text and "Show less" not in j.text
    assert "- Partner with key stakeholders" in j.text
    assert "  \n" not in j.text


def test_parse_linkedin_empty_body_raises_jderror():
    with pytest.raises(jd.JDError):
        jd.parse_linkedin("", SEARCH_URL)


def test_to_markdown_header():
    j = jd.JD("T", "C", "L", "https://u", "linkedin", "body")
    md = jd.to_markdown(j, date(2026, 9, 26))
    assert md == (
        "# T\n\n- Company: C\n- Location: L\n- Source: https://u\n"
        "- Fetched: 2026-09-26 via linkedin\n\nbody\n"
    )


def test_extract_generic_accepts_real_article():
    body = "<p>" + ("Responsibilities include building dashboards and models. " * 40) + "</p>"
    html = f"<html><head><title>Data Analyst - Acme</title></head><body><nav>Home</nav><main><h1>Data Analyst</h1>{body}</main></body></html>"
    j = jd.extract_generic(html, "https://acme.example/jobs/1", "http")
    assert j is not None and j.method == "http"
    assert "building dashboards" in j.text
    assert j.title


def test_extract_generic_rejects_thin_page():
    html = (
        "<html><body><nav><a href='/'>Home</a> <a href='/jobs'>Jobs</a> <a href='/about'>About</a></nav>"
        "<main><h1>Analyst</h1><p>Apply now via the portal.</p></main>"
        "<footer>© Example Corp</footer></body></html>"
    )
    assert jd.extract_generic(html, "https://x", "http") is None


def test_extract_generic_ignores_script_in_ratio():
    body = "<p>" + ("Real job content describing the role and duties in detail. " * 12) + "</p>"
    script = "<script>" + ('{"a": 1, "b": 2}, ' * 300) + "</script>"
    html = f"<html><head><title>Role</title>{script}</head><body><main><h1>Role</h1>{body}</main></body></html>"
    j = jd.extract_generic(html, "https://x", "http")
    assert j is not None
    assert "Real job content" in j.text


def test_fetch_http_status_error(monkeypatch):
    from curl_cffi import requests

    class Resp:
        status_code = 403
        text = "blocked"

    monkeypatch.setattr(requests, "get", lambda *a, **kw: Resp())
    with pytest.raises(jd.JDError):
        jd.fetch_http("https://x")


def test_import_url_linkedin_writes_files(tmp_path, monkeypatch):
    p = AppPaths(tmp_path / "app"); p.root.mkdir()
    monkeypatch.setattr(jd, "fetch_linkedin", lambda job_id, url, timeout=8: (jd.parse_linkedin(FIX.read_text(), url), FIX.read_text()))
    j = jd.import_url(SEARCH_URL, p)
    assert j.company == "Northwind Bakery"
    assert p.jd_md.read_text().startswith("# Pastry Chef\n")
    assert p.jd_html.exists()


def test_import_url_falls_back_to_browser(tmp_path, monkeypatch):
    p = AppPaths(tmp_path / "app"); p.root.mkdir()
    good = "<html><head><title>Role</title></head><body><main><p>" + "Real job text here. " * 60 + "</p></main></body></html>"
    monkeypatch.setattr(jd, "fetch_http", lambda url, timeout=8: "<html><body>blocked</body></html>")
    calls = []
    monkeypatch.setattr(jd, "fetch_browser", lambda url, timeout=15: calls.append(url) or good)
    j = jd.import_url("https://careers.example.com/job/1", p)
    assert calls == ["https://careers.example.com/job/1"]
    assert j.method == "browser"


def test_import_url_http_error_falls_back_to_browser(tmp_path, monkeypatch):
    p = AppPaths(tmp_path / "app"); p.root.mkdir()
    good = "<html><head><title>Role</title></head><body><main><p>" + "Real job text here. " * 60 + "</p></main></body></html>"

    def raise_http(url, timeout=8):
        raise jd.JDError("HTTP 403")

    monkeypatch.setattr(jd, "fetch_http", raise_http)
    monkeypatch.setattr(jd, "fetch_browser", lambda url, timeout=15: good)
    j = jd.import_url("https://careers.example.com/job/1", p)
    assert j.method == "browser"


def test_import_url_raises_when_both_tiers_fail(tmp_path, monkeypatch):
    p = AppPaths(tmp_path / "app"); p.root.mkdir()
    monkeypatch.setattr(jd, "fetch_http", lambda url, timeout=8: "<html><body>x</body></html>")
    monkeypatch.setattr(jd, "fetch_browser", lambda url, timeout=15: "<html><body>y</body></html>")
    with pytest.raises(jd.JDError):
        jd.import_url("https://careers.example.com/job/1", p)


def test_import_text(tmp_path):
    p = AppPaths(tmp_path / "app"); p.root.mkdir()
    jd.import_text("We need an analyst.\n", p)
    text = p.jd_md.read_text()
    assert text.startswith("# Job description\n\n- Source: pasted\n- Fetched: ")
    assert text.endswith("\n\nWe need an analyst.\n")
