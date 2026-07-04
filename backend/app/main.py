"""FastAPI app entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import init_db
from app.db.seed import is_seeded, seed_database
from app.routers import ecosystem, msmes, runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not is_seeded():
        seed_database()
    yield


app = FastAPI(title="UdyamMitra AI", version="0.1.0",
              description="AI credit & cash-flow intelligence for MSMEs (IDBI MSME track prototype)",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(msmes.router)
app.include_router(runs.router)
app.include_router(ecosystem.router)


@app.get("/")
def root() -> dict:
    return {"name": "UdyamMitra AI", "status": "ok", "offline": settings.offline_mode,
            "model": settings.openai_model, "docs": "/docs"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "offline": settings.offline_mode}