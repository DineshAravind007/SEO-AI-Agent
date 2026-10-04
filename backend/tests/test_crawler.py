import pytest
from backend.crawler.spider import Crawler, clean_url

def test_clean_url():
    # Remove fragments
    assert clean_url("https://example.com/page#section") == "https://example.com/page"
    # Ignore tracking params
    assert clean_url("https://example.com/?utm_source=test&q=1") == "https://example.com/?q=1"
    # Return empty for ignored extensions
    assert clean_url("https://example.com/image.jpg") == ""
    assert clean_url("https://example.com/doc.pdf") == ""

def test_crawler_loop(mocker):
    # Mock requests.Session.get
    mock_get = mocker.patch("requests.Session.get")
    
    class MockResponse:
        def __init__(self, text, status_code, url, headers):
            self.text = text
            self.status_code = status_code
            self.url = url
            self.headers = headers
            
    def side_effect(url, **kwargs):
        if url.endswith("robots.txt"):
            return MockResponse("User-agent: *\nDisallow: /private", 200, url, {"Content-Type": "text/plain"})
        if url == "https://example.com" or url == "https://example.com/":
            html = '<a href="/about">About</a><a href="/private/">Private</a>'
            return MockResponse(html, 200, url, {"Content-Type": "text/html"})
        if "about" in url:
            html = '<a href="/">Home</a>'
            return MockResponse(html, 200, url, {"Content-Type": "text/html"})
        if "private" in url:
            return MockResponse("", 403, url, {"Content-Type": "text/html"})
            
        return MockResponse("", 404, url, {"Content-Type": "text/html"})

    mock_get.side_effect = side_effect
    
    # Mock time.sleep to avoid waiting during tests
    mocker.patch("time.sleep")
    
    crawler = Crawler("https://example.com", max_pages=5, max_depth=2)
    crawler.run()
    
    # Should crawl home, about. Private is blocked by robots.txt.
    crawled_urls = [r["url"] for r in crawler.results]
    assert "https://example.com/" in crawled_urls
    assert "https://example.com/about" in crawled_urls
    assert "https://example.com/private" not in crawled_urls
    
    assert len(crawled_urls) == 2
