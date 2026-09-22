"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from .api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Shrimp Germplasm Identification API",
        version="0.3.0",
        description="Asynchronous API for PLINK and weighted-KNN identification jobs.",
    )
    app.include_router(router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "shrimp-germplasm-identification",
            "version": "0.3.0",
            "docs": "/docs",
        }

    return app


app = create_app()

