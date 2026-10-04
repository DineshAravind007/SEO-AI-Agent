import pytest
from backend.seo_analyzer.analyzers import run_page_analyzers, analyze_audit_duplicates

def test_run_page_analyzers():
    page_data = {
        "url": "https://example.com/test",
        "title": "Short",
        "title_length": 5,
        "meta_description": "",
        "meta_description_length": 0,
        "h1_count": 0,
        "h1_list": "[]",
        "h2_count": 0,
        "word_count": 350,
        "images_missing_alt": 2,
        "internal_link_count": 0
    }
    
    issues = run_page_analyzers(page_data)
    
    issue_codes = [i["issue_code"] for i in issues]
    
    assert "SHORT_TITLE" in issue_codes
    assert "MISSING_META_DESCRIPTION" in issue_codes
    assert "MISSING_H1" in issue_codes
    assert "MISSING_H2" in issue_codes
    assert "IMAGES_MISSING_ALT" in issue_codes
    assert "NO_INTERNAL_LINKS" in issue_codes
    
    for i in issues:
        assert i["page_url"] == "https://example.com/test"

def test_analyze_audit_duplicates():
    pages = [
        {"url": "https://example.com/1", "title": "Same Title", "meta_description": "Same Desc"},
        {"url": "https://example.com/2", "title": "Same Title", "meta_description": "Same Desc"},
        {"url": "https://example.com/3", "title": "Unique Title", "meta_description": "Unique Desc"}
    ]
    
    issues = analyze_audit_duplicates(pages)
    
    dup_titles = [i for i in issues if i["issue_code"] == "DUPLICATE_TITLE"]
    assert len(dup_titles) == 2
    
    dup_descs = [i for i in issues if i["issue_code"] == "DUPLICATE_META_DESCRIPTION"]
    assert len(dup_descs) == 2
