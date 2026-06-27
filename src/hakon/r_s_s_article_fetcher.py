import time
import urllib.robotparser
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

RSS_URL = "https://feeds.bbci.co.uk/news/rss.xml"
USER_AGENT = "DemoCrawler/1.0 (+https://example.com; contact@example.com)"
TIMEOUT = 15


def can_fetch(url: str, user_agent: str = USER_AGENT) -> bool:
    """
    Minimal robots.txt check for the specific URL.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # If robots can't be fetched, default to safer behavior: don't fetch.
        return False

    return rp.can_fetch(user_agent, url)


def fetch(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _local_name(tag: str) -> str:
    """
    Convert '{namespace}tag' -> 'tag' for ElementTree nodes.
    """
    if not tag:
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _child_text(item_elem: ET.Element, wanted: str) -> str:
    """
    Get text of a direct child element by local-name (namespace-agnostic).
    """
    for child in list(item_elem):
        if _local_name(child.tag) == wanted:
            return (child.text or "").strip()
    return ""


def parse_rss_items(rss_xml: str, limit: int = 10):
    """
    Parse RSS items from an RSS XML string without external XML parsers.
    Uses Python's stdlib ElementTree to avoid BeautifulSoup's 'xml' dependency.
    """
    try:
        root = ET.fromstring(rss_xml)
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse RSS XML: {e}") from e

    items = []
    # Find all elements named 'item' regardless of namespace
    for elem in root.iter():
        if _local_name(elem.tag) == "item":
            items.append(elem)
            if len(items) >= limit:
                break

    for it in items:
        media_links = []
        # Look for media links in enclosures or Media RSS content tags
        for child in it.iter():
            local = _local_name(child.tag)
            if local in ("enclosure", "content"):
                url = child.attrib.get("url")
                if url:
                    media_links.append(url)

        yield {
            "title": _child_text(it, "title"),
            "link": _child_text(it, "link"),
            "pubDate": _child_text(it, "pubDate"),
            "media_links": media_links,
        }


def extract_article_text(html: str, max_paragraphs: int = 5) -> str:
    """
    Very simple extraction: grab first few <p> blocks.
    Real-world crawlers use better article extraction + site-specific rules.
    """
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n".join(paragraphs[:max_paragraphs])


def main():
    if not can_fetch(RSS_URL):
        raise SystemExit(f"Robots.txt disallows fetching RSS: {RSS_URL}")

    rss = fetch(RSS_URL)
    items = list(parse_rss_items(rss, limit=5))

    for i, item in enumerate(items, 1):
        print(f"\n{i}. {item['title']}")
        print(f"   {item['link']}")
        print(f"   {item['pubDate']}")
        for m_link in item.get("media_links", []):
            print(f"   [Media] {m_link}")

        # Optional: fetch the article page (check robots first)
        if item["link"] and can_fetch(item["link"]):
            time.sleep(1.0)  # be polite: rate limit
            html = fetch(item["link"])
            snippet = extract_article_text(html, max_paragraphs=3)
            if snippet:
                print("\n   --- article snippet ---")
                print("   " + snippet.replace("\n", "\n   "))
        else:
            print("   (Skipping article fetch due to robots.txt or missing link.)")


if __name__ == "__main__":
    main()