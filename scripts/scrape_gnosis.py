#!/usr/bin/env python3
"""
Scrape Manichaean texts from the Gnostic Society Library (gnosis.org).

Parses the collection index at http://www.gnosis.org/library/manis.htm,
discovers all text links organized by category, fetches each text page,
extracts the content, and saves as clean markdown files.

Uses the same patterns as the structured-data-analysis shared scrapers
(retry logic, rate limiting, clean text extraction).

Usage:
    python scripts/scrape_gnosis.py                      # Scrape all
    python scripts/scrape_gnosis.py --category parables   # One category
    python scripts/scrape_gnosis.py --list-categories     # Show categories
    python scripts/scrape_gnosis.py --dry-run             # Preview only
    python scripts/scrape_gnosis.py --delay 1.5           # Custom delay
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "texts"
INDEX_PATH = PROJECT_ROOT / "output" / "index.json"

# ── Configuration ───────────────────────────────────────────────────────────
INDEX_URL = "http://www.gnosis.org/library/manis.htm"
BASE_URL = "http://www.gnosis.org/library/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)
DEFAULT_DELAY = 0.75  # seconds between requests
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 1.0

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("scrape_gnosis")


# ── HTTP utilities (adapted from structured-data-analysis) ──────────────────

_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Get or create a requests session with proper headers."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
    return _session


def http_get(url: str, delay: float = DEFAULT_DELAY) -> requests.Response:
    """Fetch URL with retry logic and rate limiting."""
    session = get_session()
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=90)
            response.raise_for_status()

            # Fix encoding
            if response.encoding and response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or response.encoding

            time.sleep(delay)
            return response

        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
            log.warning(f"Request failed (attempt {attempt + 1}), retrying in {backoff}s: {exc}")
            time.sleep(backoff)

    raise last_error if last_error else RuntimeError(f"Failed to fetch {url}")


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class TextEntry:
    """A single text discovered on the index page."""
    title: str
    url: str
    category: str
    slug: str  # filesystem-safe identifier

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScrapedText:
    """A fully scraped Manichaean text."""
    title: str
    url: str
    category: str
    slug: str
    content: str
    reference: str = ""
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Slug generation ─────────────────────────────────────────────────────────

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to filesystem-safe slug."""
    text = text.lower()
    text = _SLUG_PATTERN.sub("_", text)
    text = text.strip("_")
    return text[:max_length] or "entry"


# ── Index parsing ───────────────────────────────────────────────────────────

# Category definitions: maps section header text → category slug
# These are matched against the text content of the index page
CATEGORY_MARKERS = [
    ("The Psalms to Jesus", "psalms_to_jesus"),
    ("The Psalms of the Festival of Bema", "bema_psalms"),
    ("Separate Psalms", "separate_psalms"),
    ("The Kephalia of the Lord Mani", "kephalia"),
    ("Parthian Hymns and Prayers", "parthian_hymns"),
    ("Hymns and Writings Ascribed to Mani", "writings_of_mani"),
    ("Parables", "parables"),
    ("Miscellaneous Manichaean Scriptures", "miscellaneous"),
    ("Secondary Sources: Anti-Manichaean Writings of Augustine", "augustine"),
]


def parse_index(html: str) -> List[TextEntry]:
    """
    Parse the gnosis.org Manichaean index page to extract all text links.

    The page has sections with headers followed by bullet lists of links.
    We identify categories by scanning for known header text, then collect
    all links until the next category header.
    """
    soup = BeautifulSoup(html, "lxml")
    entries: List[TextEntry] = []
    seen_urls: set[str] = set()

    # Get all text content to find category boundaries
    # The page structure uses a mix of bold text, headers, and plain text
    # to delineate sections. We'll walk through all elements sequentially.

    # Find the main content area
    body = soup.find("body")
    if body is None:
        log.error("Could not find <body> in index page")
        return entries

    # Strategy: walk through all elements, track current category,
    # collect links that point to .htm/.html files on the same domain.
    # Links before the first category marker are navigation links to other
    # parts of the Gnostic Society Library — skip them.
    current_category: Optional[str] = None  # None = haven't hit first category yet

    # Build a flat list of (element, text) for scanning
    for element in body.descendants:
        if isinstance(element, NavigableString):
            text = element.strip()
            if not text:
                continue

            # Check if this text marks a new category
            for marker_text, cat_slug in CATEGORY_MARKERS:
                if marker_text in text:
                    current_category = cat_slug
                    break

        elif isinstance(element, Tag) and element.name == "a":
            # Skip links before the first category marker (navigation to other collections)
            if current_category is None:
                continue

            href = element.get("href", "")
            if not href:
                continue

            # Build full URL
            full_url = urljoin(INDEX_URL, href)

            # Only collect gnosis.org library links (not bookstore, amazon, etc.)
            if "gnosis.org/library/" not in full_url:
                continue
            if full_url == INDEX_URL:
                continue
            # Skip non-text links
            if any(skip in full_url for skip in [
                "amazon.com", "bookstore", "search_form",
                "welcome.html", "library.html", "lectures",
                "eghome", "gnostsoc", "mani-sources.htm",
                "manis.htm",
            ]):
                continue

            # Skip duplicate URLs
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Extract title from link text
            link_text = element.get_text(strip=True)
            if not link_text or len(link_text) < 3:
                continue

            # Clean up title
            title = link_text.rstrip(".")

            slug = slugify(title)

            entries.append(TextEntry(
                title=title,
                url=full_url,
                category=current_category,
                slug=slug,
            ))

    # Deduplicate by slug within categories (some links appear twice)
    deduped: List[TextEntry] = []
    seen_slugs: set[str] = set()
    for entry in entries:
        key = f"{entry.category}/{entry.slug}"
        if key not in seen_slugs:
            seen_slugs.add(key)
            deduped.append(entry)

    return deduped


# ── Text extraction ─────────────────────────────────────────────────────────

# Elements to strip from text pages (nav bars, footers, etc.)
NAV_PHRASES = [
    "Gnosis Archive",
    "Gnostic Society Library",
    "Return to Manichaean",
    "Collection Index",
    "Bookstore",
    "Web Lectures",
    "Ecclesia Gnostica",
]


def extract_text(html: str, url: str) -> tuple[str, str, str]:
    """
    Extract clean text content from a gnosis.org text page.

    Returns: (title, content, reference)
    """
    soup = BeautifulSoup(html, "lxml")

    # Find the title — usually in an h2 or the first substantial heading
    title = ""
    for tag_name in ["h2", "h1", "h3"]:
        for heading in soup.find_all(tag_name):
            text = heading.get_text(strip=True)
            # Skip navigation headings
            if any(nav in text for nav in NAV_PHRASES):
                continue
            if text and len(text) > 5:
                title = text
                break
        if title:
            break

    # Extract reference line (usually at the bottom in small text)
    reference = ""
    for small_tag in soup.find_all(["h6", "small", "font"]):
        text = small_tag.get_text(strip=True)
        if "Referance" in text or "Reference" in text or "Edited by" in text:
            reference = text
            break
        # Also check for source attribution
        if any(attr in text for attr in [
            "Psalm-Book", "Allberry", "translated by", "Translation",
            "from the", "Source:", "Klimkeit", "Boyce",
        ]):
            reference = text
            break

    # Remove nav bars, footers, images, scripts
    for tag in soup.find_all(["script", "style", "img"]):
        tag.decompose()

    # Remove navigation elements
    for tag in soup.find_all(["h6", "h5"]):
        text = tag.get_text(strip=True)
        if any(nav in text for nav in NAV_PHRASES):
            tag.decompose()
    for tag in soup.find_all("a"):
        text = tag.get_text(strip=True)
        if any(nav in text for nav in NAV_PHRASES):
            parent = tag.parent
            if parent and parent.name in ["h6", "h5", "p", "div"]:
                parent.decompose()
            else:
                tag.decompose()

    # Find the main content body
    body = soup.find("body")
    if body is None:
        return title, "", reference

    # Extract text, preserving paragraph structure
    lines: list[str] = []
    skip_next_blank = False

    for element in body.descendants:
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if not text:
                continue
            # Skip remaining nav elements
            if any(nav in text for nav in NAV_PHRASES):
                continue
            if text in ["•", "|", " "]:
                continue
            lines.append(text)
        elif isinstance(element, Tag):
            if element.name in ["p", "br", "div", "blockquote"]:
                if lines and lines[-1] != "":
                    lines.append("")
            elif element.name in ["h1", "h2", "h3", "h4"]:
                text = element.get_text(strip=True)
                if text and not any(nav in text for nav in NAV_PHRASES):
                    if lines and lines[-1] != "":
                        lines.append("")
                    lines.append(f"## {text}")
                    lines.append("")

    # Clean up the collected lines
    content = "\n".join(lines)

    # Remove excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Remove the generic "Manichaean Scriptures" page heading
    content = re.sub(r"^\s*Manichaean Scriptures\s*\n+", "", content)

    # Remove the title from content if it appears at the start
    if title:
        content = re.sub(
            r"^(##\s*)?" + re.escape(title) + r"\s*\n*",
            "",
            content,
            count=1,
        )

    # Remove reference from content body (we store it separately)
    if reference:
        content = content.replace(reference, "")

    content = content.strip()

    return title, content, reference


# ── Markdown generation ─────────────────────────────────────────────────────

def text_to_markdown(text: ScrapedText) -> str:
    """Convert a scraped text to a clean markdown document."""
    lines = [
        f"# {text.title}",
        "",
        f"**Category**: {text.category}",
        f"**Source**: [{text.url}]({text.url})",
    ]

    if text.reference:
        lines.append(f"**Reference**: {text.reference}")

    lines.extend([
        f"**Scraped**: {text.scraped_at[:10]}",
        "",
        "---",
        "",
        text.content,
        "",
    ])

    return "\n".join(lines)


# ── Main scraping logic ────────────────────────────────────────────────────

def scrape_index(delay: float = DEFAULT_DELAY) -> List[TextEntry]:
    """Fetch and parse the index page."""
    log.info(f"Fetching index: {INDEX_URL}")
    response = http_get(INDEX_URL, delay=delay)
    entries = parse_index(response.text)
    log.info(f"Found {len(entries)} texts across {len(set(e.category for e in entries))} categories")
    return entries


def scrape_text(entry: TextEntry, delay: float = DEFAULT_DELAY) -> Optional[ScrapedText]:
    """Fetch and extract a single text."""
    try:
        response = http_get(entry.url, delay=delay)
        title, content, reference = extract_text(response.text, entry.url)

        if not content or len(content) < 50:
            log.warning(f"  Skipping {entry.title} — insufficient content ({len(content)} chars)")
            return None

        # Prefer the index page title — the extracted title is often the
        # generic "Manichaean Scriptures" page heading, while the index
        # title is always the specific text name
        if entry.title and len(entry.title) > 3:
            title = entry.title

        return ScrapedText(
            title=title,
            url=entry.url,
            category=entry.category,
            slug=entry.slug,
            content=content,
            reference=reference,
        )
    except Exception as exc:
        log.error(f"  Failed to scrape {entry.url}: {exc}")
        return None


def save_text(text: ScrapedText) -> Path:
    """Save a scraped text as markdown, organized by category."""
    category_dir = OUTPUT_DIR / text.category
    category_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{text.slug}.md"
    filepath = category_dir / filename

    markdown = text_to_markdown(text)
    filepath.write_text(markdown, encoding="utf-8")

    return filepath


def save_index(entries: List[TextEntry], scraped: List[ScrapedText]) -> None:
    """Save a JSON index of all discovered and scraped texts."""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    index = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": INDEX_URL,
        "total_discovered": len(entries),
        "total_scraped": len(scraped),
        "categories": {},
    }

    for entry in entries:
        cat = entry.category
        if cat not in index["categories"]:
            index["categories"][cat] = {
                "texts": [],
                "count": 0,
            }
        was_scraped = any(s.url == entry.url for s in scraped)
        index["categories"][cat]["texts"].append({
            **entry.to_dict(),
            "scraped": was_scraped,
        })
        index["categories"][cat]["count"] += 1

    INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info(f"Index saved to {INDEX_PATH}")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Manichaean texts from gnosis.org"
    )
    parser.add_argument(
        "--category", "-c",
        help="Scrape only this category (use --list-categories to see options)",
    )
    parser.add_argument(
        "--list-categories", "-l",
        action="store_true",
        help="List available categories and exit",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be scraped without fetching",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-scrape texts that already exist",
    )
    parser.add_argument(
        "--skip-augustine",
        action="store_true",
        help="Skip Augustine's anti-Manichaean writings (secondary sources)",
    )
    args = parser.parse_args()

    # Fetch and parse the index
    entries = scrape_index(delay=args.delay)

    if args.list_categories:
        categories: dict[str, int] = {}
        for entry in entries:
            categories[entry.category] = categories.get(entry.category, 0) + 1
        print("\nAvailable categories:")
        for cat, count in categories.items():
            print(f"  {cat:30s} ({count} texts)")
        return

    # Filter by category
    if args.category:
        entries = [e for e in entries if e.category == args.category]
        if not entries:
            log.error(f"No texts found in category '{args.category}'")
            return
        log.info(f"Filtered to {len(entries)} texts in category '{args.category}'")

    if args.skip_augustine:
        before = len(entries)
        entries = [e for e in entries if e.category != "augustine"]
        log.info(f"Skipped Augustine ({before - len(entries)} texts)")

    if args.dry_run:
        print(f"\nWould scrape {len(entries)} texts:\n")
        for entry in entries:
            print(f"  [{entry.category:25s}] {entry.title}")
            print(f"    {entry.url}")
        return

    # Check for existing files (skip unless --overwrite)
    if not args.overwrite:
        to_scrape = []
        skipped = 0
        for entry in entries:
            filepath = OUTPUT_DIR / entry.category / f"{entry.slug}.md"
            if filepath.exists():
                skipped += 1
            else:
                to_scrape.append(entry)
        if skipped:
            log.info(f"Skipping {skipped} existing texts (use --overwrite to re-scrape)")
        entries = to_scrape

    if not entries:
        log.info("Nothing to scrape — all texts already exist")
        return

    # Scrape each text
    scraped: List[ScrapedText] = []
    total = len(entries)

    for i, entry in enumerate(entries, 1):
        log.info(f"[{i}/{total}] {entry.title}")
        text = scrape_text(entry, delay=args.delay)
        if text:
            path = save_text(text)
            scraped.append(text)
            log.info(f"  → {path.relative_to(PROJECT_ROOT)}")

    # Save index
    all_entries = scrape_index(delay=args.delay) if args.category else entries
    save_index(all_entries if not args.category else entries, scraped)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Scraping complete")
    print(f"  Texts scraped:  {len(scraped)}/{total}")
    print(f"  Output:         {OUTPUT_DIR.relative_to(PROJECT_ROOT)}/")

    categories_done = set(t.category for t in scraped)
    for cat in sorted(categories_done):
        count = sum(1 for t in scraped if t.category == cat)
        print(f"    {cat}: {count}")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
