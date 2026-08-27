import re
from urllib.parse import urlparse


def is_http_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def youtube_embed(url: str) -> str | None:
    if not url or not is_http_url(url):
        return None
    patterns = [
        r"(?:www\.)?youtube\.com/watch\?(?:[^#]*&)?v=([A-Za-z0-9_-]{6,})",
        r"(?:www\.)?youtu\.be/([A-Za-z0-9_-]{6,})",
        r"(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{6,})",
        r"(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{6,})",
    ]
    host = (urlparse(url).hostname or "").lower()
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        return None
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return f"https://www.youtube.com/embed/{match.group(1)}?enablejsapi=1&playsinline=1"
    return None


def timestamped_video_url(url: str, second: float) -> str:
    """Return a safe study link pointing as close as possible to a timestamp.

    For YouTube this uses the documented URL timestamp convention. Other remote
    sources are left untouched because their timestamp semantics differ.
    """
    if not is_http_url(url):
        return ""
    seconds = max(0, int(float(second)))
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        separator = "&" if parsed.query else "?"
        return f"{url}{separator}t={seconds}s"
    if host == "youtu.be":
        separator = "&" if parsed.query else "?"
        return f"{url}{separator}t={seconds}s"
    return url
