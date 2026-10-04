import pytest
from backend.technical.analyzers import (
    check_https,
    check_status_and_redirects,
    check_indexability,
    check_canonical,
    check_performance,
    check_xml_sitemap
)
from backend.technical.scorer import calculate_audit_score

def test_check_https():
    # Test HTTP base
    issues = check_https("http://example.com", "http://example.com")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "NO_HTTPS"
    
    # Test HTTPS base
    issues = check_https("https://example.com", "https://example.com")
    assert len(issues) == 0

def test_check_status_and_redirects():
    # Test 404
    issues = check_status_and_redirects(404, "https://example.com", "https://example.com")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "CLIENT_ERROR_4XX"
    
    # Test 500
    issues = check_status_and_redirects(500, "https://example.com", "https://example.com")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "SERVER_ERROR_5XX"
    
    # Test Redirect
    issues = check_status_and_redirects(200, "https://example.com", "https://example.com/redirected")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "REDIRECT"

def test_check_indexability():
    # Test noindex in meta robots
    issues = check_indexability("noindex, nofollow", "")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "NOINDEX"
    
    # Test noindex in X-Robots-Tag
    issues = check_indexability("", "noindex")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "NOINDEX"
    
    # Test indexable
    issues = check_indexability("index, follow", "")
    assert len(issues) == 0

def test_check_canonical():
    # Missing canonical
    issues = check_canonical("https://example.com", "")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "MISSING_CANONICAL"
    
    # Malformed canonical
    issues = check_canonical("https://example.com", "not_a_url")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "MALFORMED_CANONICAL"
    
    # Cross domain canonical
    issues = check_canonical("https://example.com", "https://other.com")
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "CROSS_DOMAIN_CANONICAL"
    
    # Valid self-referencing canonical
    issues = check_canonical("https://example.com", "https://example.com")
    assert len(issues) == 0

def test_check_performance():
    # Slow response
    issues = check_performance(2.0, 500)
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "SLOW_RESPONSE"
    
    # Large HTML
    issues = check_performance(0.5, 2 * 1024 * 1024)
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "LARGE_HTML"
    
    # Good performance
    issues = check_performance(0.5, 500)
    assert len(issues) == 0

def test_calculate_audit_score():
    issues = [
        {"issue_code": "CLIENT_ERROR_4XX", "severity": "HIGH"},
        {"issue_code": "CLIENT_ERROR_4XX", "severity": "HIGH"}, # Duplicate code, should only count once
        {"issue_code": "SLOW_RESPONSE", "severity": "MEDIUM"},
        {"issue_code": "MISSING_CANONICAL", "severity": "LOW"} # Using LOW instead of MEDIUM for this test
    ]
    
    result = calculate_audit_score(issues, total_pages=10)
    # Expected score: 100 - 10 (HIGH) - 5 (MEDIUM) - 2 (LOW) = 83
    assert result["score"] == 83
    assert result["grade"] == "Good"
    assert result["severity_counts"]["HIGH"] == 2 # 2 total HIGH issues
    assert result["severity_counts"]["MEDIUM"] == 1
    assert result["severity_counts"]["LOW"] == 1

def test_calculate_audit_score_zero_bound():
    issues = [{"issue_code": f"ISSUE_{i}", "severity": "CRITICAL"} for i in range(10)]
    result = calculate_audit_score(issues, total_pages=1)
    assert result["score"] == 0 # Score shouldn't go below 0
    assert result["grade"] == "Needs Improvement"

from unittest.mock import patch, MagicMock

@patch("requests.get")
def test_check_xml_sitemap_found(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    mock_get.return_value = mock_resp
    
    issues = check_xml_sitemap("https://example.com", [])
    assert len(issues) == 0

@patch("requests.get")
def test_check_xml_sitemap_missing(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp
    
    issues = check_xml_sitemap("https://example.com", [])
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "MISSING_SITEMAP"

@patch("requests.get")
def test_check_xml_sitemap_invalid_xml(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'<!DOCTYPE html><html></html>' # Not XML
    mock_get.return_value = mock_resp
    
    issues = check_xml_sitemap("https://example.com", [])
    assert len(issues) == 1
    assert issues[0]["issue_code"] == "MISSING_SITEMAP"
