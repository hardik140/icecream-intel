import threading
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.collectors import google_maps

router = APIRouter(prefix="/collect", tags=["collect"])

# shortcut: in-memory job registry, lost on restart; move to a table if jobs must survive restarts
_jobs: dict[str, dict] = {}
_one_at_a_time = threading.Lock()  # parallel scrapes get blocked by Google faster


class GoogleMapsRequest(BaseModel):
    queries: list[str] = Field(min_length=1, examples=[["ice cream shop in Connaught Place Delhi"]])
    depth: int = Field(1, ge=1, le=5, description="scroll depth of the results list (more = more places)")
    extra_reviews: bool = False


def _run(job_id: str, req: GoogleMapsRequest) -> None:
    try:
        _jobs[job_id].update(status="done", result=google_maps.collect(req.queries, req.depth, req.extra_reviews))
    except Exception as e:
        _jobs[job_id].update(status="failed", error=str(e))
    finally:
        _one_at_a_time.release()


@router.post("/google-maps", status_code=202)
def collect_google_maps(req: GoogleMapsRequest, background: BackgroundTasks) -> dict:
    """Scrape Google Maps into the `competitors` table + a reviews document. Takes 1-5 minutes."""
    try:
        google_maps.validate_queries(req.queries)
        google_maps.find_binary()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if not _one_at_a_time.acquire(blocking=False):
        raise HTTPException(409, "A Google Maps job is already running")
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"job_id": job_id, "status": "running", "queries": req.queries}
    background.add_task(_run, job_id, req)
    return _jobs[job_id]


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    return _jobs[job_id]
