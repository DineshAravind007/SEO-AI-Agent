"""
Performance analyzer - SERVER-SIDE MEASUREMENTS ONLY.

IMPORTANT: This module ONLY measures what can be observed via standard HTTP requests.
Browser-based metrics (LCP, INP, CLS, FCP in the web sense) are NOT measured here.
They are clearly marked as UNAVAILABLE.

What IS measured:
  - Server response time (time to receive complete HTML response)
  - HTML document size (in bytes)
  - HTTP compression (via Content-Encoding header)
  - HTTP caching headers (Cache-Control)
  - HTTPS usage
  - Viewport meta tag presence
  - Image count and missing dimension attributes
  - TTFB approximation (response time is an upper bound for TTFB)

What is NOT measured (marked UNAVAILABLE):
  - LCP (Largest Contentful Paint) - requires real browser
  - INP (Interaction to Next Paint) - requires real browser + user interaction
  - CLS (Cumulative Layout Shift) - requires real browser rendering
  - FCP (First Contentful Paint) - requires real browser rendering
  - JavaScript bundle sizes - requires fetching JS assets separately
  - Image file sizes - requires fetching each image separately
"""

from bs4 import BeautifulSoup
from typing import Dict, Any, List

# ── Scoring Rules ─────────────────────────────────────────────────────────────
# These thresholds are documented here, not scattered throughout code.

PERF_RULES = {
    # Response time thresholds (ms)
    "response_time": {
        "good": 200,          # <= 200ms: no penalty
        "needs_improvement": 500,  # 200-500ms: moderate penalty
        "poor": 1000,         # > 1000ms: severe penalty
        "max_penalty": 30,
    },
    # HTML size thresholds (bytes)
    "html_size": {
        "good": 100 * 1024,        # <= 100KB: no penalty
        "warn": 300 * 1024,        # 300KB+: moderate issue
        "poor": 500 * 1024,        # 500KB+: severe issue
        "max_penalty": 25,
    },
    # Compression: fixed penalty when missing
    "compression_penalty": 15,
    # Cache-Control: fixed penalty when missing
    "cache_penalty": 10,
    # Missing image dimensions: per-image penalty
    "missing_dimensions_per_image": 2,
    "missing_dimensions_max_penalty": 20,
    # Viewport meta: penalty when missing
    "viewport_penalty": 5,
    # HTTPS: penalty when not used
    "https_penalty": 10,
}

CWV_UNAVAILABLE_NOTE = (
    "Core Web Vitals require a real browser environment to measure accurately. "
    "This tool uses server-side HTTP requests and cannot report LCP, INP, or CLS. "
    "Use Google Search Console, PageSpeed Insights, or Lighthouse for real CWV data."
)


def _classify_response_time(ms: int) -> str:
    """Classify response time into GOOD / NEEDS_IMPROVEMENT / POOR."""
    if ms <= PERF_RULES["response_time"]["good"]:
        return "GOOD"
    if ms <= PERF_RULES["response_time"]["needs_improvement"]:
        return "NEEDS_IMPROVEMENT"
    return "POOR"


def analyze_performance(page_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze performance of a single page from crawler data.

    Args:
        page_data: dict from crawler.spider.Crawler.results containing
                   url, duration (float seconds), html (str), headers (dict),
                   status_code (int), final_url (str).

    Returns:
        {
            "metrics": { ... measurable values ... },
            "issues": [ ... structured issue dicts ... ],
            "cwv_note": str  # Explanation of unavailable CWV
        }
    """
    url = page_data.get("url", "")
    html = page_data.get("html", "") or ""
    duration_sec = page_data.get("duration") or 0.0
    headers = page_data.get("headers", {}) or {}
    final_url = page_data.get("final_url") or url

    # ── Basic measurements ─────────────────────────────────────────────────
    response_time_ms = int(duration_sec * 1000)
    html_size_bytes = len(html.encode("utf-8"))

    # Headers are case-insensitive in HTTP; lowercase for reliable lookup
    h = {k.lower(): v for k, v in headers.items()}

    content_encoding = h.get("content-encoding", "")
    is_compressed = any(enc in content_encoding.lower()
                        for enc in ("gzip", "br", "deflate", "zstd"))

    cache_control = h.get("cache-control", "")
    has_cache_control = (
        "max-age" in cache_control
        or "s-maxage" in cache_control
        or "immutable" in cache_control
    )

    # HTTPS detection
    is_https = final_url.startswith("https://")

    # ── HTML parsing ───────────────────────────────────────────────────────
    image_count = 0
    missing_dimensions_count = 0
    has_viewport_meta = False

    if html:
        soup = BeautifulSoup(html, "lxml")

        # Viewport meta
        viewport = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "viewport"})
        has_viewport_meta = viewport is not None

        # Images
        images = soup.find_all("img")
        image_count = len(images)
        for img in images:
            has_w = img.get("width")
            has_h = img.get("height")
            if not has_w or not has_h:
                missing_dimensions_count += 1

    # ── Scoring ────────────────────────────────────────────────────────────
    score = 100
    issues: List[Dict[str, Any]] = []

    # Rule 1: Server response time
    rt_rule = PERF_RULES["response_time"]
    if response_time_ms > rt_rule["good"]:
        if response_time_ms <= rt_rule["needs_improvement"]:
            penalty = 10
            severity = "LOW"
        elif response_time_ms <= rt_rule["poor"]:
            penalty = 20
            severity = "MEDIUM"
        else:
            penalty = rt_rule["max_penalty"]
            severity = "HIGH"

        score -= penalty
        issues.append({
            "issue_code": "SLOW_SERVER_RESPONSE",
            "category": "Performance",
            "severity": severity,
            "title": "Slow Server Response Time",
            "description": (
                f"Server responded in {response_time_ms}ms. "
                f"Target is under {rt_rule['good']}ms. "
                f"Slow responses delay all subsequent rendering."
            ),
            "recommendation_summary": (
                "Optimize server-side logic, enable caching (Redis/Memcached), "
                "use a CDN, or reduce database query count."
            ),
            "impact": f"Performance score reduced by {penalty} points.",
        })

    # Rule 2: HTML document size
    size_rule = PERF_RULES["html_size"]
    if html_size_bytes > size_rule["good"]:
        over_bytes = html_size_bytes - size_rule["good"]
        if html_size_bytes >= size_rule["poor"]:
            penalty = size_rule["max_penalty"]
            severity = "HIGH"
        elif html_size_bytes >= size_rule["warn"]:
            penalty = 15
            severity = "MEDIUM"
        else:
            penalty = 5
            severity = "LOW"

        score -= penalty
        size_kb = round(html_size_bytes / 1024, 1)
        issues.append({
            "issue_code": "LARGE_HTML_DOCUMENT",
            "category": "Performance",
            "severity": severity,
            "title": "Large HTML Document",
            "description": (
                f"HTML document is {size_kb}KB. "
                f"Documents over {size_rule['good'] // 1024}KB increase parse time and "
                f"delay Time to First Byte of content."
            ),
            "recommendation_summary": (
                "Minify HTML, remove unnecessary comments and whitespace, "
                "move large inline scripts to external files, avoid server-side template bloat."
            ),
            "impact": f"Performance score reduced by {penalty} points.",
        })

    # Rule 3: Missing image dimensions (causes CLS-like layout shifts)
    if missing_dimensions_count > 0:
        per_img = PERF_RULES["missing_dimensions_per_image"]
        penalty = min(
            PERF_RULES["missing_dimensions_max_penalty"],
            missing_dimensions_count * per_img,
        )
        score -= penalty
        severity = "HIGH" if missing_dimensions_count >= 5 else "MEDIUM"
        issues.append({
            "issue_code": "MISSING_IMAGE_DIMENSIONS",
            "category": "Performance",
            "severity": severity,
            "title": "Images Missing Explicit Dimensions",
            "description": (
                f"{missing_dimensions_count} of {image_count} image(s) lack "
                f"explicit width and height attributes. This causes layout shifts "
                f"as images load, degrading visual stability."
            ),
            "recommendation_summary": (
                "Add width and height HTML attributes to every <img> tag. "
                "The browser uses these to reserve layout space before the image downloads."
            ),
            "impact": f"Performance score reduced by {penalty} points. May worsen CLS.",
        })

    # Rule 4: Text compression
    if not is_compressed and html_size_bytes > 1024:
        penalty = PERF_RULES["compression_penalty"]
        score -= penalty
        issues.append({
            "issue_code": "MISSING_COMPRESSION",
            "category": "Performance",
            "severity": "HIGH",
            "title": "Text Compression Not Enabled",
            "description": (
                "The server returned the HTML response without compression "
                "(no Content-Encoding: gzip/br header). "
                f"Uncompressed size: {round(html_size_bytes / 1024, 1)}KB."
            ),
            "recommendation_summary": (
                "Enable GZIP or Brotli compression on your web server (nginx, Apache, CDN). "
                "This typically reduces HTML transfer size by 60-80%."
            ),
            "impact": f"Performance score reduced by {penalty} points.",
        })

    # Rule 5: Cache-Control
    if not has_cache_control:
        penalty = PERF_RULES["cache_penalty"]
        score -= penalty
        issues.append({
            "issue_code": "MISSING_CACHE_CONTROL",
            "category": "Performance",
            "severity": "MEDIUM",
            "title": "No Cache-Control Policy",
            "description": (
                "The server response does not include a Cache-Control header with "
                "max-age or s-maxage. Browsers and CDNs will not cache this resource "
                "predictably."
            ),
            "recommendation_summary": (
                "Set Cache-Control headers appropriate to content type: "
                "'max-age=3600' for HTML pages, 'max-age=31536000, immutable' "
                "for versioned static assets."
            ),
            "impact": f"Performance score reduced by {penalty} points.",
        })

    # Rule 6: HTTPS
    if not is_https:
        penalty = PERF_RULES["https_penalty"]
        score -= penalty
        issues.append({
            "issue_code": "NOT_HTTPS",
            "category": "Performance",
            "severity": "HIGH",
            "title": "Page Not Served Over HTTPS",
            "description": (
                f"The page was served over HTTP ({final_url}), not HTTPS. "
                "HTTP/2 (which greatly improves performance) requires HTTPS, "
                "and Google uses HTTPS as a ranking signal."
            ),
            "recommendation_summary": (
                "Obtain and install an SSL/TLS certificate (e.g., free from Let's Encrypt) "
                "and configure permanent 301 redirects from HTTP to HTTPS."
            ),
            "impact": f"Performance score reduced by {penalty} points.",
        })

    # Rule 7: Viewport meta (mobile usability / performance perception)
    if html and not has_viewport_meta:
        penalty = PERF_RULES["viewport_penalty"]
        score -= penalty
        issues.append({
            "issue_code": "MISSING_VIEWPORT_META",
            "category": "Performance",
            "severity": "MEDIUM",
            "title": "Missing Viewport Meta Tag",
            "description": (
                "No <meta name='viewport'> tag was found. Without it, mobile browsers "
                "render the page at desktop width then scale it down, hurting perceived "
                "performance and Core Web Vitals."
            ),
            "recommendation_summary": (
                "Add <meta name='viewport' content='width=device-width, initial-scale=1'> "
                "to the <head> of every page."
            ),
            "impact": f"Performance score reduced by {penalty} points.",
        })

    score = max(0, score)
    response_time_rating = _classify_response_time(response_time_ms)

    return {
        "metrics": {
            # Server-measured
            "response_time_ms": response_time_ms,
            "response_time_rating": response_time_rating,
            "html_size_bytes": html_size_bytes,
            "is_compressed": is_compressed,
            "is_https": is_https,
            "has_cache_control": has_cache_control,
            "has_viewport_meta": has_viewport_meta,
            "image_count": image_count,
            "missing_dimensions_count": missing_dimensions_count,
            # TTFB approximation: our response time includes TCP+TLS+server processing.
            # It is an upper bound approximation, not a browser-measured TTFB.
            "ttfb_ms_approx": response_time_ms,
            # Performance score (0-100, deterministic, explained in PERF_RULES)
            "performance_score": score,
            # CWV — not measured
            "lcp_status": "UNAVAILABLE",
            "inp_status": "UNAVAILABLE",
            "cls_status": "UNAVAILABLE",
            "fcp_ms": None,
        },
        "issues": issues,
        "cwv_note": CWV_UNAVAILABLE_NOTE,
    }
