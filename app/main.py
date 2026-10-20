from fastapi import FastAPI

from app.api import chat, data, documents, health
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Ice Cream Brand Intelligence", version="0.1.0")
    for module in (health, documents, data, chat):
        app.include_router(module.router)
    return app


app = create_app()
