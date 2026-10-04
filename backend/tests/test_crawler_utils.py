from backend.crawler.validator import is_safe_url, normalize_url
from backend.crawler.queue import URLQueue, normalize_for_queue
import pytest

def test_normalize_url():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("http://example.com") == "http://example.com"

def test_is_safe_url_valid():
    assert is_safe_url("https://www.google.com") is True
    assert is_safe_url("http://example.com") is True

def test_is_safe_url_invalid():
    assert is_safe_url("ftp://example.com") is False
    assert is_safe_url("localhost") is False
    assert is_safe_url("http://127.0.0.1") is False
    assert is_safe_url("http://192.168.1.1") is False
    assert is_safe_url("http://169.254.169.254") is False

def test_url_queue():
    q = URLQueue("https://example.com")
    q.add("https://example.com/about/", 1)
    q.add("https://example.com/about#team", 1) # Should be deduplicated
    
    url1, depth1 = q.pop()
    assert url1 == "https://example.com/"
    assert depth1 == 0
    
    url2, depth2 = q.pop()
    assert url2 == "https://example.com/about" # Normalized
    assert depth2 == 1
    
    assert q.is_empty() is True
