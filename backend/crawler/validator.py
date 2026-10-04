import ipaddress
import socket
from urllib.parse import urlparse

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Try to resolve to IP
        try:
            ip_str = socket.gethostbyname(hostname)
        except socket.gaierror:
            # If we can't resolve it, it's either an invalid domain or an internal one not exposed.
            # To be safe and compliant with the requirements, if it's not resolvable, we might fail it,
            # but maybe we should just check if it parses as an IP first.
            ip_str = hostname

        try:
            ip = ipaddress.ip_address(ip_str)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
            # Block metadata-service addresses (e.g., 169.254.169.254 is link-local, so covered)
        except ValueError:
            # Not an IP address, and we couldn't resolve it. Let's assume it's a domain.
            pass
            
        # Hardcode some localhost strings just in case
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        return True
    except Exception:
        return False

def normalize_url(url: str) -> str:
    # If no scheme, add https://
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url
