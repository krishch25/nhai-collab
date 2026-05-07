"""FastAPI application."""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_download, routes_rules, routes_status, routes_upload
from app.core.logging import setup_logging
from app.db.init_db import init_db
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging early
    setup_logging()
    # Initialise DB and optionally seed dev data
    init_db(seed=os.environ.get("SEED_DEV_DATA", "").lower() in ("1", "true", "yes"))
    yield


app = FastAPI(
    title="Continuous Learning Taxonomy Classification System",
    description="Agentic AI system for classifying raw materials into L0/L1/L2 taxonomy.",
    version="0.1.0",
    lifespan=lifespan,
)

# Basic CORS; adjust allowed origins as needed for your deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_upload.router, prefix="/api")
app.include_router(routes_download.router, prefix="/api")
app.include_router(routes_rules.router, prefix="/api")
app.include_router(routes_status.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}

# Mount the static frontend at root
app.mount("/", StaticFiles(directory="static", html=True), name="static")

