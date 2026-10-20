import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api import chat, data, documents, health
from app.core.logging import setup_logging

log = logging.getLogger(__name__)


def _error(status: int, code: str, message) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Ice Cream Brand Intelligence", version="0.2.0")
    for module in (health, documents, data, chat):
        app.include_router(module.router)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return _error(exc.status_code, "http_error", exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return _error(422, "validation_error", exc.errors())

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return _error(500, "internal_error", "Something went wrong")

    return app


app = create_app()
