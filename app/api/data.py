from fastapi import APIRouter, Form, HTTPException, UploadFile

router = APIRouter(prefix="/data", tags=["data"])


@router.post("", status_code=201)
async def upload_table(file: UploadFile, table_name: str = Form(...)) -> dict:
    """Load CSV/XLSX into DuckDB (M2)."""
    raise HTTPException(501, "Not implemented yet (M2)")


@router.get("/tables")
def list_tables() -> list[dict]:
    raise HTTPException(501, "Not implemented yet (M2)")
