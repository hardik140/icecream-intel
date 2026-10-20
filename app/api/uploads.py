import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings


async def save_upload(file: UploadFile, allowed: set[str]) -> Path:
    """Stream an upload to a temp file in the data dir, enforcing type and size limits."""
    name = Path(file.filename or "").name
    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(415, f"Unsupported file type '{suffix}'. Allowed: {sorted(allowed)}")
    s = get_settings()
    limit = s.max_upload_mb * 1024 * 1024
    size = 0
    with tempfile.NamedTemporaryFile(dir=s.data_dir, suffix=suffix, delete=False) as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                Path(out.name).unlink(missing_ok=True)
                raise HTTPException(413, f"File larger than {s.max_upload_mb} MB")
            out.write(chunk)
    return Path(out.name)
