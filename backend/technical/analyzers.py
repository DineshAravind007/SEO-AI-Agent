from typing import List, Dict, Any
from urllib.parse import urlparse
import requests

def check_https(url: str, final_url: str) -> List[Dict[str, Any]]:
    issues = []
    parsed_url = urlparse(url)
    parsed_final = urlparse(final_url) if final_url else parsed_url
    
    if parsed_url.scheme != "https" and parsed_final.scheme != "https":
        issues.append({
            "category": "technical",
            "severity": "CRITICAL",
            "issue_code": "NO_HTTPS",
            "title": "Insecure HTTP Protocol",
            "description": "The page is served over HTTP instead of HTTPS.",
            "recommendation_summary": "Migrate the page to HTTPS to ensure security.",
            "impact": "Security risk and negative SEO impact."
        })
    return issues

def check_status_and_redirects(status_code: int, url: str, final_url: str) -> List[Dict[str, Any]]:
    issues = []
    if status_code:
        if 400 <= status_code < 500:
            issues.append({
                "category": "technical",
                "severity": "HIGH",
                "issue_code": "CLIENT_ERROR_4XX",
                "title": f"Client Error ({status_code})",
                "description": f"The page returned a {status_code} error.",
                "recommendation_summary": "Fix broken links or restore the page.",
                "impact": "Search engines cannot index the page, leading to lost traffic."
            })
        elif status_code >= 500:
            issues.append({
                "category": "technical",
                "severity": "CRITICAL",
                "issue_code": "SERVER_ERROR_5XX",
                "title": f"Server Error ({status_code})",
                "description": f"The server returned a {status_code} error.",
                "recommendation_summary": "Investigate backend logs to fix the server issue.",
                "impact": "Users and bots cannot access the page."
            })
            
    if final_url and url != final_url:
        # A simple redirect was followed
        issues.append({
            "category": "technical",
            "severity": "LOW",
            "issue_code": "REDIRECT",
            "title": "Page Redirects",
            "description": f"The URL redirects to {final_url}.",
            "recommendation_summary": "Update internal links to point to the final destination.",
            "impact": "Minor performance overhead due to redirect chain."
        })
        
    return issues

def check_indexability(meta_robots: str, x_robots_tag: str) -> List[Dict[str, Any]]:
    issues = []
    noindex_tags = []
    if meta_robots and "noindex" in meta_robots.lower():
        noindex_tags.append("Meta Robots")
    if x_robots_tag and "noindex" in x_robots_tag.lower():
        noindex_tags.append("X-Robots-Tag")
        
    if noindex_tags:
        issues.append({
            "category": "technical",
            "severity": "HIGH",
            "issue_code": "NOINDEX",
            "title": "Page is not indexable (noindex)",
            "description": f"The page has a noindex directive in {', '.join(noindex_tags)}.",
            "recommendation_summary": "Remove the noindex directive if the page should be indexed.",
            "impact": "The page will not appear in search engine results."
        })
        
    return issues

def check_canonical(url: str, canonical_url: str) -> List[Dict[str, Any]]:
    issues = []
    if not canonical_url:
        issues.append({
            "category": "technical",
            "severity": "MEDIUM",
            "issue_code": "MISSING_CANONICAL",
            "title": "Missing Canonical Tag",
            "description": "The page does not specify a canonical URL.",
            "recommendation_summary": "Add a self-referencing canonical tag.",
            "impact": "Potential duplicate content issues."
        })
    else:
        parsed_canon = urlparse(canonical_url)
        if not parsed_canon.scheme or not parsed_canon.netloc:
            issues.append({
                "category": "technical",
                "severity": "HIGH",
                "issue_code": "MALFORMED_CANONICAL",
                "title": "Malformed Canonical URL",
                "description": f"The canonical URL '{canonical_url}' is not a valid absolute URL.",
                "recommendation_summary": "Provide a fully qualified absolute URL in the canonical tag.",
                "impact": "Search engines may ignore the canonical instruction."
            })
        elif parsed_canon.netloc != urlparse(url).netloc:
            issues.append({
                "category": "technical",
                "severity": "LOW",
                "issue_code": "CROSS_DOMAIN_CANONICAL",
                "title": "Cross-Domain Canonical",
                "description": f"The canonical URL points to a different domain: {parsed_canon.netloc}.",
                "recommendation_summary": "Ensure this is intentional (e.g. syndicated content).",
                "impact": "Search equity will be passed to the external domain."
            })
    return issues

def check_performance(duration: float, html_length: int) -> List[Dict[str, Any]]:
    issues = []
    # threshold for slow response e.g., > 1.5 seconds
    if duration and duration > 1.5:
        issues.append({
            "category": "technical",
            "severity": "MEDIUM",
            "issue_code": "SLOW_RESPONSE",
            "title": "Slow Server Response",
            "description": f"The server took {duration:.2f}s to respond.",
            "recommendation_summary": "Optimize backend performance and TTFB.",
            "impact": "Slower load times negatively affect SEO and user experience."
        })
        
    # threshold for large HTML e.g., > 1MB
    if html_length and html_length > 1024 * 1024:
        issues.append({
            "category": "technical",
            "severity": "MEDIUM",
            "issue_code": "LARGE_HTML",
            "title": "Excessively Large HTML",
            "description": f"The HTML document is {html_length / 1024:.0f} KB.",
            "recommendation_summary": "Minify HTML and remove excessive inline scripts/styles.",
            "impact": "Increases parsing time for browsers and search engine bots."
        })
        
    return issues

def run_technical_analyzers(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Runs all page-level technical checks."""
    issues = []
    
    url = page_data.get("url")
    final_url = page_data.get("final_url")
    status_code = page_data.get("status_code")
    duration = page_data.get("duration")
    
    # We use page_data for html length, assuming we have access to it or word_count as proxy?
    # Wait, html length is not in page_data currently unless we put it there.
    # Let's extract it from spider results in audit_service.
    html_length = page_data.get("html_length", 0)
    
    meta_robots = page_data.get("meta_robots")
    x_robots_tag = page_data.get("x_robots_tag")
    canonical_url = page_data.get("canonical_url")
    
    issues.extend(check_https(url, final_url))
    issues.extend(check_status_and_redirects(status_code, url, final_url))
    issues.extend(check_indexability(meta_robots, x_robots_tag))
    issues.extend(check_canonical(url, canonical_url))
    issues.extend(check_performance(duration, html_length))
    
    # ensure page_url is set
    for i in issues:
        i["page_url"] = url
        
    return issues

import xml.etree.ElementTree as ET

def check_xml_sitemap(base_url: str, robots_sitemaps: List[str]) -> List[Dict[str, Any]]:
    issues = []
    
    # Identify possible sitemap URLs
    possible_sitemaps = list(set(robots_sitemaps)) if robots_sitemaps else []
    if not possible_sitemaps:
        possible_sitemaps.append(base_url.rstrip("/") + "/sitemap.xml")
        
    valid_sitemap_found = False
    
    for sm_url in possible_sitemaps:
        try:
            resp = requests.get(sm_url, timeout=10)
            if resp.status_code == 200:
                try:
                    root = ET.fromstring(resp.content)
                    # The root tag should be urlset or sitemapindex (ignoring namespace)
                    if "urlset" in root.tag.lower() or "sitemapindex" in root.tag.lower():
                        valid_sitemap_found = True
                        break
                except ET.ParseError:
                    pass
        except Exception:
            pass
            
    if not valid_sitemap_found:
        issues.append({
            "category": "technical",
            "severity": "HIGH",
            "issue_code": "MISSING_SITEMAP",
            "title": "XML Sitemap Not Found",
            "description": "No valid XML sitemap was found at standard locations or in robots.txt.",
            "recommendation_summary": "Generate and submit an XML sitemap to search engines.",
            "impact": "Search engines may struggle to discover all pages on the site."
        })
        
    # associate audit-level issues with the base url
    for i in issues:
        i["page_url"] = base_url
        
    return issues
