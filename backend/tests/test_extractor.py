import pytest
import json
from backend.crawler.extractor import extract_seo_data

html_fixture = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Test Title</title>
    <meta name="description" content="Test description here.">
    <link rel="canonical" href="https://example.com/test">
    <meta name="robots" content="noindex, nofollow">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta property="og:title" content="OG Test Title">
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "WebPage"}
    </script>
</head>
<body>
    <h1>Heading 1</h1>
    <h1>Heading 2</h1>
    <h2>Subheading 1</h2>
    <p>This is a test paragraph with some words.</p>
    <img src="test.jpg" alt="test image">
    <img src="bad.jpg">
    <a href="/internal">Internal Link</a>
    <a href="https://external.com">External Link</a>
</body>
</html>
"""

def test_extract_seo_data():
    headers = {"X-Robots-Tag": "noindex"}
    data = extract_seo_data(html_fixture, "https://example.com/test", headers)
    
    assert data["title"] == "Test Title"
    assert data["title_length"] == 10
    assert data["meta_description"] == "Test description here."
    assert data["meta_description_length"] == 22
    assert data["h1_count"] == 2
    assert json.loads(data["h1_list"]) == ["Heading 1", "Heading 2"]
    assert data["h2_count"] == 1
    assert data["canonical_url"] == "https://example.com/test"
    assert data["meta_robots"] == "noindex, nofollow"
    assert data["x_robots_tag"] == "noindex"
    assert data["html_language"] == "en"
    assert data["viewport_meta_presence"] is True
    assert data["image_count"] == 2
    assert data["images_missing_alt"] == 1
    assert data["internal_link_count"] == 1
    assert data["external_link_count"] == 1
    assert data["open_graph_presence"] is True
    assert data["structured_data_presence"] is True
    assert data["word_count"] > 10 # approximate based on text
