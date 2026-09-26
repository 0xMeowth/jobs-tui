from jobs_tui.tracker import Row, insert, read

HEADER = "| Submitted | Company | Role | Files | URL | Notes |\n|---|---|---|---|---|---|\n"


def test_insert_creates_file_with_header(tmp_path):
    p = tmp_path / "tracker.md"
    insert(p, Row("2026-09-26", "Northwind", "AI Analyst", "companies/northwind/ai-analyst/", "https://x/1", ""))
    text = p.read_text()
    assert text.startswith(HEADER)
    assert "| 2026-09-26 | Northwind | AI Analyst | [open](<companies/northwind/ai-analyst/>) | [posting](<https://x/1>) |  |" in text


def test_insert_newest_first_and_roundtrip(tmp_path):
    p = tmp_path / "tracker.md"
    insert(p, Row("2026-09-01", "A", "r1", "companies/a/r1/", "", "first"))
    insert(p, Row("2026-09-02", "B", "r2", "companies/b/r2/", "https://b", "has | pipe"))
    rows = read(p)
    assert [r.company for r in rows] == ["B", "A"]
    assert rows[0].notes == "has | pipe"
    assert rows[0].url == "https://b"
    assert rows[1].url == "" and rows[1].folder == "companies/a/r1/"


def test_read_missing(tmp_path):
    assert read(tmp_path / "none.md") == []


def test_pipe_in_url_roundtrips(tmp_path):
    p = tmp_path / "tracker.md"
    insert(p, Row("2026-09-26", "Northwind", "AI Analyst", "companies/northwind/ai-analyst/", "https://x?a=1|2", ""))
    rows = read(p)
    assert rows[0].url == "https://x?a=1|2"


def test_off_shape_row_is_skipped(tmp_path):
    p = tmp_path / "tracker.md"
    insert(p, Row("2026-09-01", "A", "r1", "companies/a/r1/", "", "first"))
    p.write_text(p.read_text() + "| bad | row | only five |\n")
    insert(p, Row("2026-09-02", "B", "r2", "companies/b/r2/", "https://b", "second"))
    rows = read(p)
    assert [r.company for r in rows] == ["B", "A"]


def test_padded_separator_no_duplicate_header(tmp_path):
    p = tmp_path / "tracker.md"
    p.write_text(
        "| Submitted | Company | Role | Files | URL | Notes |\n"
        "| --------- | --------- | --------- | --------- | --------- | --------- |\n"
        "| 2026-09-01 | A | r1 | [open](<companies/a/r1/>) |  | first |\n"
    )
    insert(p, Row("2026-09-02", "B", "r2", "companies/b/r2/", "https://b", "second"))
    text = p.read_text()
    assert text.count("Submitted") == 1
    rows = read(p)
    assert [r.company for r in rows] == ["B", "A"]


def test_url_with_parens_reads_whole(tmp_path):
    p = tmp_path / "tracker.md"
    insert(p, Row("2026-09-26", "Northwind", "AI Analyst", "companies/northwind/ai-analyst/", "https://x/(bar)", ""))
    rows = read(p)
    assert rows[0].url == "https://x/(bar)"
