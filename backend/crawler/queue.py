from collections import deque
from urllib.parse import urlparse, urlunparse

def normalize_for_queue(url: str) -> str:
    """Normalize URL by removing fragments, trailing slashes, and forcing lowercase host."""
    parsed = urlparse(url)
    
    # Force lowercase hostname
    netloc = parsed.netloc.lower()
    
    # Remove fragment
    fragment = ""
    
    # Normalize path
    path = parsed.path
    if not path:
        path = "/"
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
        
    # Rebuild URL
    normalized = urlunparse((parsed.scheme, netloc, path, parsed.params, parsed.query, fragment))
    return normalized

class URLQueue:
    def __init__(self, base_url: str):
        self.queue = deque()
        self.visited = set()
        self.add(base_url, 0)
        
    def add(self, url: str, depth: int):
        norm_url = normalize_for_queue(url)
        if norm_url not in self.visited:
            self.visited.add(norm_url)
            self.queue.append((norm_url, depth))
            
    def pop(self):
        if self.queue:
            return self.queue.popleft()
        return None
        
    def is_empty(self) -> bool:
        return len(self.queue) == 0
