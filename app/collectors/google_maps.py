"""Google Maps → competitors table (SQL) + reviews document (PageIndex), via gosom/google-maps-scraper.

The scraper (MIT, https://github.com/gosom/google-maps-scraper) drives a headless browser. It is not an
official Google API and scraping may violate Google's Terms of Service: keep volume low, one job at a time.
Reviewer names, photos and profile links are dropped; review text is PII-scrubbed.
"""
import json
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.guardrails.input_guard import scrub_pii
from app.ingestion import doc_indexer
from app.ingestion.table_loader import upsert_rows

log = logging.getLogger(__name__)
BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
TABLE = "competitors"


def find_binary() -> Path:
    configured = get_settings().gmaps_scraper_bin
    if configured:
        return configured
    found = sorted(BIN_DIR.glob("google_maps_scraper*"))
    if not found:
        raise ValueError("Google Maps scraper not installed. Run: python -m scripts.install_gmaps_scraper")
    return found[-1]


def validate_queries(queries: list[str]) -> list[str]:
    """Queries go one-per-line into a file, so newlines would smuggle in extra searches."""
    clean = [q.strip() for q in queries if q and q.strip()]
    if not clean:
        raise ValueError("At least one query is required")
    if len(clean) > get_settings().gmaps_max_queries:
        raise ValueError(f"At most {get_settings().gmaps_max_queries} queries per job")
    for q in clean:
        if len(q) > 200 or re.search(r"[\r\n\x00]", q):
            raise ValueError(f"Invalid query: {q[:50]!r}")
    return clean


def scrape(queries: list[str], depth: int = 1, extra_reviews: bool = False) -> list[dict]:
    """Run the scraper and return its raw JSON records (one per place)."""
    queries = validate_queries(queries)
    workdir = Path(tempfile.mkdtemp(prefix="gmaps_"))
    try:
        (workdir / "queries.txt").write_text("\n".join(queries) + "\n", encoding="utf-8")
        cmd = [str(find_binary()), "-input", "queries.txt", "-results", "results.json", "-json",
               "-depth", str(depth), "-c", "2", "-exit-on-inactivity", "2m"]
        if extra_reviews:
            cmd.append("-extra-reviews")
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=get_settings().gmaps_timeout_s)
        results = workdir / "results.json"
        if proc.returncode != 0 or not results.exists():
            raise RuntimeError(f"Scraper failed (exit {proc.returncode}): {proc.stderr[-500:] or proc.stdout[-500:]}")
        return [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def to_places(records: list[dict], scraped_at: str) -> pd.DataFrame:
    """One row per place. Business phone/owner fields are left out; they aren't needed for decisions."""
    rows = []
    for r in records:
        if not r.get("place_id"):
            continue
        stars = r.get("reviews_per_rating") or {}
        rows.append({
            "place_id": r["place_id"],
            "name": r.get("title", ""),
            "category": r.get("category", ""),
            "address": r.get("address", ""),
            "city": (r.get("complete_address") or {}).get("city", ""),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude") or r.get("longtitude"),  # scraper has both spellings
            "rating": r.get("review_rating"),
            "review_count": r.get("review_count"),
            **{f"stars_{i}": int(stars.get(str(i), 0)) for i in range(1, 6)},
            "price_range": r.get("price_range", ""),
            "website": r.get("web_site", ""),
            "maps_link": r.get("link", ""),
            "scraped_at": scraped_at,
        })
    return pd.DataFrame(rows)


def to_reviews_markdown(records: list[dict], queries: list[str], scraped_at: str) -> str:
    """Headings per place so PageIndex builds a tree. No reviewer identity, PII scrubbed."""
    lines = [f"# Google Maps competitor reviews ({scraped_at[:10]})", "",
             "Searches: " + "; ".join(queries), ""]
    for r in records:
        if not r.get("place_id"):  # same rule as to_places, so doc and table describe the same places
            continue
        lines += [f"## {r.get('title', 'Unknown place')}",
                  f"Rating {r.get('review_rating')} from {r.get('review_count')} reviews. "
                  f"Category: {r.get('category', '')}. Address: {r.get('address', '')}.", ""]
        for rev in (r.get("user_reviews_extended") or r.get("user_reviews") or []):
            text = (rev.get("Description") or rev.get("text_original") or "").strip()
            if text:
                lines.append(f"- {rev.get('Rating', '?')}/5 ({rev.get('When', '')}): {scrub_pii(' '.join(text.split()))}")
        lines.append("")
    return "\n".join(lines)


def collect(queries: list[str], depth: int = 1, extra_reviews: bool = False) -> dict:
    """Scrape → upsert competitors table → index reviews document. Returns a summary."""
    queries = validate_queries(queries)
    records = scrape(queries, depth, extra_reviews)
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    places = to_places(records, scraped_at)
    if places.empty:
        raise RuntimeError("Scraper returned no places (blocked, or no results for these queries)")
    total = upsert_rows(places, TABLE, "place_id")

    md = Path(tempfile.mkdtemp()) / f"google_maps_reviews_{scraped_at[:10]}.md"
    md.write_text(to_reviews_markdown(records, queries, scraped_at), encoding="utf-8")
    doc_id = doc_indexer.register(md, md.name)
    doc_indexer.build_tree(doc_id)

    reviews = sum(len(r.get("user_reviews_extended") or r.get("user_reviews") or []) for r in records)
    log.info("Collected %d places, %d reviews", len(places), reviews)
    return {"places": len(places), "reviews": reviews, "table": TABLE, "table_rows": total, "doc_id": doc_id}
