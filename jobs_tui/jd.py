import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urlparse

import trafilatura
from lxml import html as LH
from markdownify import markdownify

from jobs_tui.paths import AppPaths

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MIN_CHARS = 500
MIN_RATIO = 0.3


class JDError(Exception):
    pass


@dataclass
class JD:
    title: str
    company: str | None
    location: str | None
    url: str
    method: str
    text: str


def linkedin_job_id(url: str) -> str | None:
    u = urlparse(url)
    if "linkedin.com" not in u.netloc:
        return None
    q = parse_qs(u.query)
    if "currentJobId" in q:
        return q["currentJobId"][0]
    m = re.search(r"/jobs/view/(?:[^/]*?-)?(\d+)", u.path)
    return m.group(1) if m else None


def _first_text(doc, selector: str) -> str | None:
    nodes = doc.cssselect(selector)
    return nodes[0].text_content().strip() if nodes else None


def parse_linkedin(html: str, url: str) -> JD:
    doc = LH.fromstring(html)
    nodes = doc.cssselect("div.show-more-less-html__markup, div.description__text")
    if not nodes:
        raise JDError("LinkedIn page has no description container")
    text = markdownify(LH.tostring(nodes[0], encoding="unicode"), heading_style="ATX", bullets="-", strip=["a", "button"])
    text = text.replace("  \n", "\n")
    text = re.sub(r"\s*Show more\s*Show less\s*$", "", text.strip())
    text = re.sub(r"(\*\*[^*\n]+\*\*)(?=\S)", r"\1\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return JD(
        title=_first_text(doc, "h2.top-card-layout__title, h1") or "Job description",
        company=_first_text(doc, "a.topcard__org-name-link, .topcard__flavor"),
        location=_first_text(doc, ".topcard__flavor--bullet"),
        url=url, method="linkedin", text=text,
    )


def fetch_http(url: str, timeout: float = 8) -> str:
    from curl_cffi import requests
    try:
        r = requests.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
    except Exception as e:
        raise JDError(f"HTTP fetch failed: {e}") from e
    return r.text


def fetch_linkedin(job_id: str, url: str, timeout: float = 8) -> tuple[JD, str]:
    html = fetch_http(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}", timeout)
    return parse_linkedin(html, url), html


def fetch_browser(url: str, timeout: float = 15) -> str:
    from patchright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True, timeout=timeout * 1000)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=max(1000, (timeout - 5) * 1000))
            page.wait_for_timeout(2500)
            html = page.content()
            browser.close()
    except Exception as e:
        raise JDError(f"Browser fetch failed: {e}") from e
    return html


def extract_generic(html: str, url: str, method: str) -> JD | None:
    text = trafilatura.extract(html, url=url, include_links=False, favor_precision=True, output_format="markdown") or ""
    text = text.strip()
    try:
        visible = len(LH.fromstring(html).text_content())
    except Exception:
        visible = len(text)
    if len(text) < MIN_CHARS or len(text) < MIN_RATIO * max(visible, 1):
        return None
    title = None
    try:
        meta = trafilatura.extract_metadata(html)
        title = meta.title if meta else None
    except Exception:
        title = None
    return JD(title=title or "Job description", company=None, location=None, url=url, method=method, text=text)


def to_markdown(j: JD, fetched: date) -> str:
    lines = [f"# {j.title}", ""]
    if j.company:
        lines.append(f"- Company: {j.company}")
    if j.location:
        lines.append(f"- Location: {j.location}")
    lines += [f"- Source: {j.url}", f"- Fetched: {fetched.isoformat()} via {j.method}", "", j.text.rstrip() + "\n"]
    return "\n".join(lines)


def import_url(url: str, p: AppPaths) -> JD:
    job_id = linkedin_job_id(url)
    if job_id:
        j, html = fetch_linkedin(job_id, url)
    else:
        html = fetch_http(url)
        j = extract_generic(html, url, "http")
        if j is None:
            html = fetch_browser(url)
            j = extract_generic(html, url, "browser")
        if j is None:
            raise JDError("Could not extract a job description from that page. Paste it instead.")
    p.jd_html.write_text(html)
    p.jd_md.write_text(to_markdown(j, date.today()))
    return j


def import_text(text: str, p: AppPaths) -> None:
    j = JD(title="Job description", company=None, location=None, url="pasted", method="paste", text=text)
    p.jd_md.write_text(to_markdown(j, date.today()))
