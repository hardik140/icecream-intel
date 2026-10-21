import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.collectors import google_maps
from app.ingestion import doc_indexer
from app.main import app
from app.retrieval.sql_tool import run_sql

FIXTURE = Path(__file__).parent / "fixtures" / "gmaps_sample.jsonl"
RECORDS = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def fake_scrape(monkeypatch):
    monkeypatch.setattr(google_maps, "scrape", lambda queries, depth=1, extra_reviews=False: RECORDS)


def test_places_drop_records_without_id_and_handle_both_spellings():
    df = google_maps.to_places(RECORDS, "2026-10-21T00:00:00+00:00")
    assert list(df["place_id"]) == ["fake_place_1", "fake_place_2"]
    assert list(df["longitude"]) == [77.2220, 77.21]
    assert df.loc[0, "stars_5"] == 96 and df.loc[1, "stars_1"] == 0
    assert "phone" not in df.columns


def test_reviews_markdown_has_no_reviewer_identity_or_pii():
    md = google_maps.to_reviews_markdown(RECORDS, ["q"], "2026-10-21T00:00:00+00:00")
    assert "## Polar Scoops CP" in md
    assert "- 5/5 (2 months ago): Loved the mango sundae! Call me on [PHONE]" in md
    for leaked in ["Fake Reviewer", "p1.jpg", "example.com/u1", "fake.person@example.com", "98765"]:
        assert leaked not in md


@pytest.mark.parametrize("queries", [[], ["  "], ["a\nb"], ["x" * 201], ["q"] * 11])
def test_bad_queries_rejected(queries):
    with pytest.raises(ValueError):
        google_maps.validate_queries(queries)


def test_collect_feeds_sql_and_pageindex(fake_scrape):
    summary = google_maps.collect(["ice cream shop in Connaught Place Delhi"])
    assert summary["places"] == 2 and summary["reviews"] == 2
    rows = run_sql("SELECT name, rating FROM competitors ORDER BY rating DESC")
    assert rows[0] == {"name": "Kulfi Corner", "rating": 4.6}
    doc = doc_indexer.get_document(summary["doc_id"])
    assert doc["status"] == "ready"
    assert [n["title"] for n in doc["tree"][0]["nodes"]] == ["Polar Scoops CP", "Kulfi Corner"]

    google_maps.collect(["same query again"])  # re-scrape updates rows instead of duplicating
    assert run_sql("SELECT COUNT(*) AS n FROM competitors") == [{"n": 2}]


def test_collect_endpoint_runs_job(fake_scrape, monkeypatch):
    monkeypatch.setattr(google_maps, "find_binary", lambda: Path("fake"))
    client = TestClient(app)
    job = client.post("/collect/google-maps", json={"queries": ["ice cream Delhi"]}).json()
    done = client.get(f"/collect/jobs/{job['job_id']}").json()  # TestClient runs the background task first
    assert done["status"] == "done", done
    assert done["result"]["places"] == 2
    assert client.post("/collect/google-maps", json={"queries": ["a\nb"]}).status_code == 422


@pytest.mark.skipif(not os.getenv("RUN_LIVE_SCRAPE"), reason="live Google Maps scrape; set RUN_LIVE_SCRAPE=1")
def test_live_scrape_returns_real_places():
    records = google_maps.scrape(["ice cream shop in Connaught Place Delhi"], depth=1)
    places = google_maps.to_places(records, "now")
    assert len(places) >= 3
    assert places["name"].str.len().gt(0).all()
    assert places["rating"].between(1, 5).any()
