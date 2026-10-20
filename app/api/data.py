from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.api.uploads import save_upload
from app.ingestion.table_loader import get_schema, load_table

router = APIRouter(prefix="/data", tags=["data"])


@router.post("", status_code=201)
async def upload_table(file: UploadFile, table_name: str = Form(...)) -> dict:
    """Load a CSV/Excel file into DuckDB as `table_name` (replaces an existing table of that name)."""
    tmp = await save_upload(file, {".csv", ".xlsx", ".xls"})
    try:
        return load_table(tmp, table_name)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/tables")
def list_tables() -> list[dict]:
    return [{"table": t, "columns": cols} for t, cols in get_schema().items()]
