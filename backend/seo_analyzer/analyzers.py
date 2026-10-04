from typing import List, Dict, Any
from backend.database.models import SEOIssue
import json

def analyze_title(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    title = page_data.get("title")
    title_length = page_data.get("title_length", 0)
    
    if not title:
        issues.append({
            "category": "on_page",
            "severity": "HIGH",
            "issue_code": "MISSING_TITLE",
            "title": "Missing Title",
            "description": "The page is missing a <title> tag.",
            "recommendation_summary": "Add a descriptive title to the page.",
            "impact": "Critical for search rankings and CTR."
        })
    elif title_length < 30:
        issues.append({
            "category": "on_page",
            "severity": "MEDIUM",
            "issue_code": "SHORT_TITLE",
            "title": "Short Title",
            "description": f"The title is too short ({title_length} characters).",
            "recommendation_summary": "Make the title between 50 and 60 characters.",
            "impact": "Missed opportunity to include relevant keywords."
        })
    elif title_length > 60:
        issues.append({
            "category": "on_page",
            "severity": "MEDIUM",
            "issue_code": "LONG_TITLE",
            "title": "Long Title",
            "description": f"The title is too long ({title_length} characters).",
            "recommendation_summary": "Keep the title under 60 characters.",
            "impact": "The title may be truncated in search results."
        })
    return issues

def analyze_meta_description(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    meta_desc = page_data.get("meta_description")
    meta_desc_length = page_data.get("meta_description_length", 0)
    
    if not meta_desc:
        issues.append({
            "category": "on_page",
            "severity": "HIGH",
            "issue_code": "MISSING_META_DESCRIPTION",
            "title": "Missing Meta Description",
            "description": "The page is missing a meta description.",
            "recommendation_summary": "Add a compelling meta description.",
            "impact": "Search engines may generate a poor snippet, lowering CTR."
        })
    elif meta_desc_length < 70:
        issues.append({
            "category": "on_page",
            "severity": "LOW",
            "issue_code": "SHORT_META_DESCRIPTION",
            "title": "Short Meta Description",
            "description": f"The meta description is too short ({meta_desc_length} chars).",
            "recommendation_summary": "Expand the description to 150-160 characters.",
            "impact": "Missed opportunity to pitch the page content."
        })
    elif meta_desc_length > 160:
        issues.append({
            "category": "on_page",
            "severity": "LOW",
            "issue_code": "LONG_META_DESCRIPTION",
            "title": "Long Meta Description",
            "description": f"The meta description is too long ({meta_desc_length} chars).",
            "recommendation_summary": "Keep the description under 160 characters.",
            "impact": "The description may be truncated in search results."
        })
    return issues

def analyze_headings(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    h1_count = page_data.get("h1_count", 0)
    h1_list = json.loads(page_data.get("h1_list", "[]"))
    h2_count = page_data.get("h2_count", 0)
    word_count = page_data.get("word_count", 0)
    
    if h1_count == 0:
        issues.append({
            "category": "on_page",
            "severity": "HIGH",
            "issue_code": "MISSING_H1",
            "title": "Missing H1",
            "description": "The page does not have an H1 tag.",
            "recommendation_summary": "Add a single, descriptive H1 tag.",
            "impact": "Helps search engines understand the main topic."
        })
    elif h1_count > 1:
        issues.append({
            "category": "on_page",
            "severity": "LOW",
            "issue_code": "MULTIPLE_H1",
            "title": "Multiple H1s",
            "description": f"The page has {h1_count} H1 tags.",
            "recommendation_summary": "It is best practice to have only one H1 tag.",
            "impact": "Can dilute the main topic signal."
        })
    elif h1_count == 1 and not h1_list[0]:
        issues.append({
            "category": "on_page",
            "severity": "HIGH",
            "issue_code": "EMPTY_H1",
            "title": "Empty H1",
            "description": "The H1 tag is empty.",
            "recommendation_summary": "Add descriptive text to the H1 tag.",
            "impact": "An empty H1 provides no value to users or search engines."
        })
        
    if word_count > 300 and h2_count == 0:
        issues.append({
            "category": "on_page",
            "severity": "LOW",
            "issue_code": "MISSING_H2",
            "title": "Missing H2 on Substantial Content",
            "description": "The page has over 300 words but no H2 tags.",
            "recommendation_summary": "Use H2 tags to break up the content.",
            "impact": "Improves readability and structure."
        })
        
    return issues

def analyze_images(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    missing_alt = page_data.get("images_missing_alt", 0)
    if missing_alt > 0:
        issues.append({
            "category": "on_page",
            "severity": "MEDIUM",
            "issue_code": "IMAGES_MISSING_ALT",
            "title": "Images Missing Alt Text",
            "description": f"Found {missing_alt} image(s) missing alt text.",
            "recommendation_summary": "Add descriptive alt text to all informative images.",
            "impact": "Accessibility issue and missed image search traffic."
        })
    return issues

def analyze_links(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    internal_links = page_data.get("internal_link_count", 0)
    if internal_links == 0:
        issues.append({
            "category": "on_page",
            "severity": "HIGH",
            "issue_code": "NO_INTERNAL_LINKS",
            "title": "No Internal Links",
            "description": "The page has no internal links.",
            "recommendation_summary": "Add links to other relevant pages on your site.",
            "impact": "Poor site structure and PageRank flow."
        })
    return issues

def run_page_analyzers(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    issues.extend(analyze_title(page_data))
    issues.extend(analyze_meta_description(page_data))
    issues.extend(analyze_headings(page_data))
    issues.extend(analyze_images(page_data))
    issues.extend(analyze_links(page_data))
    
    # Add page_url to all issues
    url = page_data.get("url")
    for issue in issues:
        issue["page_url"] = url
        
    return issues

# Audit level analyzers
def analyze_audit_duplicates(pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues = []
    
    title_map = {}
    desc_map = {}
    
    for page in pages_data:
        t = page.get("title")
        d = page.get("meta_description")
        
        if t:
            title_map.setdefault(t, []).append(page["url"])
        if d:
            desc_map.setdefault(d, []).append(page["url"])
            
    for title, urls in title_map.items():
        if len(urls) > 1:
            for url in urls:
                issues.append({
                    "page_url": url,
                    "category": "on_page",
                    "severity": "MEDIUM",
                    "issue_code": "DUPLICATE_TITLE",
                    "title": "Duplicate Title",
                    "description": "This title is used on multiple pages.",
                    "recommendation_summary": "Write a unique title for each page.",
                    "impact": "Search engines may struggle to differentiate pages."
                })
                
    for desc, urls in desc_map.items():
        if len(urls) > 1:
            for url in urls:
                issues.append({
                    "page_url": url,
                    "category": "on_page",
                    "severity": "MEDIUM",
                    "issue_code": "DUPLICATE_META_DESCRIPTION",
                    "title": "Duplicate Meta Description",
                    "description": "This meta description is used on multiple pages.",
                    "recommendation_summary": "Write a unique meta description for each page.",
                    "impact": "Search engines may struggle to differentiate pages."
                })
                
    return issues
