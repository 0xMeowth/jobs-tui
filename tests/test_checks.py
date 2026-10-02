from jobs_tui import checks


def resume(*texts):
    return {"sections": [{"id": "exp", "title": "Experience", "entries": [
        {"id": "acme", "org": "Acme", "bullets": [{"id": f"acme.b{i}", "text": t} for i, t in enumerate(texts, 1)]},
    ], "bullets": [{"id": "skills.b1", "text": "Data: SQL,Python"}]}]}


def by_id(findings):
    return {f.bullet_id: f for f in findings}


def test_spacing_and_characters():
    f = by_id(checks.local_findings(resume("Built trees,linear baselines  fast", "Led clients’ “workshops” — weekly"), ""))
    assert f["acme.b1"].proposed == "Built trees, linear baselines fast" and f["acme.b1"].rules == ["spacing"]
    assert f["acme.b2"].proposed == "Led clients' \"workshops\", weekly" and f["acme.b2"].rules == ["quotes and dashes"]


def test_numbers_and_en_dash_are_left_alone():
    assert checks.local_findings(resume("Cut query times by 117–1,300 times", "Grew users by 40%"), "") == []


def test_space_before_punctuation():
    assert by_id(checks.local_findings(resume("Built models , then shipped ."), ""))["acme.b1"].proposed == "Built models, then shipped."


def test_skills_lines_are_not_checked():
    assert "skills.b1" not in by_id(checks.local_findings(resume("Built models"), ""))


def test_consistent_spelling_passes_without_posting_signal():
    assert checks.local_findings(resume("Optimized modeling", "Analyzed behavior"), "") == []
    assert checks.local_findings(resume("Optimised modelling", "Analysed behaviour"), "We value teamwork") == []


def test_mixed_spelling_converts_minority_to_majority():
    f = by_id(checks.local_findings(resume("Optimised modelling", "Analysed behavior"), ""))
    assert f["acme.b2"].proposed == "Analysed behaviour" and f["acme.b2"].rules == ["British spelling"]
    assert "acme.b1" not in f


def test_spelling_tie_goes_british():
    f = by_id(checks.local_findings(resume("Optimised", "Optimized"), ""))
    assert list(f) == ["acme.b2"] and f["acme.b2"].proposed == "Optimised"


def test_posting_signal_wins_even_when_resume_is_consistent():
    f = by_id(checks.local_findings(resume("Optimised modelling", "Built SQL"), "Strong modeling and data visualization skills"))
    assert f["acme.b1"].proposed == "Optimized modeling" and f["acme.b1"].rules == ["American spelling"]


def test_posting_with_both_spellings_is_no_signal():
    assert checks.posting_signal("modelling and visualization") is None
    assert checks.posting_signal("organisation, optimise") == "uk"
    assert checks.posting_signal("analyzing, modeling") == "us"
    assert checks.posting_signal("") is None


def test_case_is_preserved():
    f = by_id(checks.local_findings(resume("Modeling at ACME", "MODELING"), "optimise"))
    assert f["acme.b1"].proposed == "Modelling at ACME" and f["acme.b2"].proposed == "MODELLING"


def test_trailing_period_majority_and_tie():
    f = by_id(checks.local_findings(resume("Built a.", "Built b", "Built c"), ""))
    assert list(f) == ["acme.b1"] and f["acme.b1"].proposed == "Built a" and f["acme.b1"].rules == ["trailing period"]
    f = by_id(checks.local_findings(resume("Built a.", "Built b"), ""))
    assert list(f) == ["acme.b1"]
    f = by_id(checks.local_findings(resume("Built a.", "Built b.", "Built c"), ""))
    assert f["acme.b3"].proposed == "Built c."


def test_several_rules_on_one_bullet_make_one_finding():
    one = by_id(checks.local_findings(resume("Optimized a,b", "Optimised", "Optimised"), ""))["acme.b1"]
    assert one.proposed == "Optimised a, b" and one.rules == ["spacing", "British spelling"]
