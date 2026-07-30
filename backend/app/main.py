from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import auth, capture, education, referral, verification, orchestrator


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler = None
    try:
        from app.agents.pedagogue.veille import start_scheduler

        scheduler = start_scheduler()
    except Exception:
        scheduler = None
    yield
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass


app = FastAPI(title="LedgerMind Backend", lifespan=lifespan)

# FRONTEND_ORIGIN may be a single URL or a comma-separated list.
# Also allow any localhost / 127.0.0.1 port in local dev (Vite often picks 5173, 8080, 8082…).
_cors_origins = [o.strip() for o in settings.frontend_origin.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(education.router)
app.include_router(referral.router)
app.include_router(capture.router)
app.include_router(verification.router)
app.include_router(orchestrator.router)


@app.get("/health")
async def health():
    chunks = 0
    try:
        from app.agents.pedagogue.rag import vectorstore

        chunks = vectorstore.count()
    except Exception:
        chunks = 0
    return {"status": "ok", "corpus_chunks": chunks}
