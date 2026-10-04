import requests
import time
import logging
from urllib.parse import urlparse, urljoin, parse_qsl, urlencode, urlunparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from backend.crawler.queue import URLQueue
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

USER_AGENT = "SEO-AI-Agent/1.0"
REQUEST_TIMEOUT = 10
POLITENESS_DELAY = 1.0

IGNORED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".avi",
    ".css", ".js", ".zip", ".rar", ".exe", ".ttf", ".woff", ".woff2",
    ".svg", ".mp3", ".wav"
}

IGNORED_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}

def clean_url(url: str) -> str:
    parsed = urlparse(url)
    
    # Check extension
    if any(parsed.path.lower().endswith(ext) for ext in IGNORED_EXTENSIONS):
        return ""
        
    # Remove ignored params
    if parsed.query:
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_params = [(k, v) for k, v in query_params if k.lower() not in IGNORED_PARAMS]
        new_query = urlencode(filtered_params)
        parsed = parsed._replace(query=new_query)
        
    # Remove fragment
    parsed = parsed._replace(fragment="")
    
    return urlunparse(parsed)


class Crawler:
    def __init__(self, base_url: str, max_pages: int = 10, max_depth: int = 2):
        self.base_url = base_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.queue = URLQueue(base_url)
        self.parsed_domain = urlparse(base_url).netloc
        self.rp = RobotFileParser()
        self.robots_loaded = False
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.results: List[Dict[str, Any]] = []
        
    def load_robots(self):
        robots_url = urljoin(self.base_url, "/robots.txt")
        self.rp.set_url(robots_url)
        try:
            response = self.session.get(robots_url, timeout=REQUEST_TIMEOUT)
            content_type = response.headers.get("Content-Type", "")
            if response.status_code == 200 and "text/plain" in content_type:
                # Only parse a genuine robots.txt (status 200, text/plain).
                # An HTML 404 page fed to the parser would block all paths.
                self.rp.parse(response.text.splitlines())
                logger.info("Loaded robots.txt from %s", robots_url)
            else:
                # No usable robots.txt — allow everything
                self.rp.allow_all = True
                logger.info(
                    "robots.txt not usable (status=%s, ct=%s) — allowing all",
                    response.status_code, content_type,
                )
        except Exception as exc:
            # Network error — allow everything rather than blocking the crawl
            self.rp.allow_all = True
            logger.warning("Could not fetch robots.txt (%s) — allowing all", exc)
        self.robots_loaded = True

    def is_internal(self, url: str) -> bool:
        return urlparse(url).netloc == self.parsed_domain
        
    def can_fetch(self, url: str) -> bool:
        if not self.robots_loaded:
            self.load_robots()
        return self.rp.can_fetch(USER_AGENT, url)

    def extract_links(self, html: str, current_url: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(current_url, href)
            cleaned = clean_url(full_url)
            if cleaned and self.is_internal(cleaned):
                links.append(cleaned)
        return list(set(links))

    def run(self):
        """Crawl pages starting from base_url up to max_pages/max_depth."""
        logger.info("Crawler starting: base=%s max_pages=%s max_depth=%s",
                    self.base_url, self.max_pages, self.max_depth)

        # Respect robots.txt for the start URL
        if not self.can_fetch(self.base_url):
            logger.warning("robots.txt disallows fetching base URL %s", self.base_url)
            return

        pages_crawled = 0
        
        while not self.queue.is_empty() and pages_crawled < self.max_pages:
            url, depth = self.queue.pop()
            
            if depth > self.max_depth:
                logger.debug("Skipping %s — depth %s exceeds max_depth %s", url, depth, self.max_depth)
                continue
                
            if not self.can_fetch(url):
                logger.info("robots.txt disallows %s — skipping", url)
                continue
                
            try:
                logger.info("Fetching [depth=%s] %s", depth, url)
                start_time = time.time()
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                duration = time.time() - start_time
                
                content_type = response.headers.get("Content-Type", "")
                # Capture response headers as a plain dict for downstream use
                response_headers = dict(response.headers)
                
                result: Dict[str, Any] = {
                    "url": url,
                    "final_url": str(response.url),
                    "depth": depth,
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "headers": response_headers,
                    "duration": duration,
                    "html": response.text if "text/html" in content_type else "",
                    "error": None
                }
                
                if "text/html" in content_type and response.status_code == 200:
                    # Enqueue new links found on valid HTML pages
                    if depth < self.max_depth:
                        links = self.extract_links(response.text, str(response.url))
                        logger.info("Found %s internal links on %s", len(links), url)
                        for link in links:
                            self.queue.add(link, depth + 1)
                            
                self.results.append(result)
                pages_crawled += 1
                logger.info("Crawled %s/%s pages", pages_crawled, self.max_pages)
                
                # Politeness delay between requests
                if not self.queue.is_empty() and pages_crawled < self.max_pages:
                    time.sleep(POLITENESS_DELAY)
                    
            except Exception as exc:
                logger.error("Error fetching %s: %s", url, exc)
                self.results.append({
                    "url": url,
                    "final_url": None,
                    "depth": depth,
                    "status_code": None,
                    "content_type": None,
                    "headers": {},
                    "duration": None,
                    "html": "",
                    "error": str(exc)
                })

        logger.info("Crawler finished. Total results: %s", len(self.results))
