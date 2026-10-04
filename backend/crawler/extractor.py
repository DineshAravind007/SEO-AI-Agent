import json
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from urllib.parse import urlparse

def extract_seo_data(html: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    
    # Title
    title_tag = soup.find("title")
    title = title_tag.text.strip() if title_tag and title_tag.text else None
    title_length = len(title) if title else 0
    
    # Meta Description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None
    meta_desc_length = len(meta_desc) if meta_desc else 0
    
    # Headings
    h1_tags = soup.find_all("h1")
    h1_list = [h.text.strip() for h in h1_tags]
    h1_count = len(h1_list)
    
    h2_tags = soup.find_all("h2")
    h2_list = [h.text.strip() for h in h2_tags]
    h2_count = len(h2_list)
    
    # Canonical
    canonical_tag = soup.find("link", rel="canonical")
    canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else None
    
    # Meta Robots
    meta_robots_tag = soup.find("meta", attrs={"name": "robots"})
    meta_robots = meta_robots_tag.get("content", "").strip() if meta_robots_tag else None
    
    # X-Robots-Tag
    x_robots_tag = headers.get("X-Robots-Tag") or headers.get("x-robots-tag")
    
    # Language
    html_tag = soup.find("html")
    html_language = html_tag.get("lang", "").strip() if html_tag else None
    
    # Viewport
    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    viewport_meta_presence = bool(viewport_tag)
    
    # Word count (basic)
    text = soup.get_text(separator=" ")
    word_count = len(text.split())
    
    # Images
    images = soup.find_all("img")
    image_count = len(images)
    images_missing_alt = sum(1 for img in images if not img.get("alt") or not img.get("alt").strip())
    
    # Links
    links = soup.find_all("a", href=True)
    parsed_domain = urlparse(url).netloc
    internal_link_count = 0
    external_link_count = 0
    
    for a in links:
        href = a["href"]
        if href.startswith(("http://", "https://")):
            if urlparse(href).netloc == parsed_domain:
                internal_link_count += 1
            else:
                external_link_count += 1
        elif href.startswith(("/", "#", "?")):
            internal_link_count += 1
            
    # Open Graph
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    open_graph_presence = bool(og_title or og_desc)
    
    # Structured Data (JSON-LD)
    json_ld_tags = soup.find_all("script", type="application/ld+json")
    structured_data_presence = bool(json_ld_tags)
    
    return {
        "title": title,
        "title_length": title_length,
        "meta_description": meta_desc,
        "meta_description_length": meta_desc_length,
        "h1_list": json.dumps(h1_list),
        "h1_count": h1_count,
        "h2_list": json.dumps(h2_list),
        "h2_count": h2_count,
        "canonical_url": canonical_url,
        "meta_robots": meta_robots,
        "x_robots_tag": x_robots_tag,
        "html_language": html_language,
        "viewport_meta_presence": viewport_meta_presence,
        "word_count": word_count,
        "image_count": image_count,
        "images_missing_alt": images_missing_alt,
        "internal_link_count": internal_link_count,
        "external_link_count": external_link_count,
        "open_graph_presence": open_graph_presence,
        "structured_data_presence": structured_data_presence
    }
