"""
NadiNet FastAPI Application
Full-stack NGO volunteer coordination platform.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.auth import create_access_token, verify_token

# Import all API routers
from app.api.v1.ingest import router as ingest_router
from app.api.v1.needs import router as needs_router
from app.api.v1.volunteers import router as volunteers_router
from app.api.v1.dispatch import router as dispatch_router
from app.api.v1.debrief import router as debrief_router
from app.api.v1.reporters import router as reporters_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.reports import router as reports_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)


async def run_nightly_decay_job():
    async with AsyncSessionLocal() as db:
        from app.jobs.nightly_decay import run_nightly_decay
        await run_nightly_decay(db)


async def run_reverification_job():
    async with AsyncSessionLocal() as db:
        from app.jobs.reverification import run_reverification
        await run_reverification(db)


async def run_retrain_job():
    async with AsyncSessionLocal() as db:
        from app.jobs.retrain_classifier import run_retrain
        await run_retrain(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start APScheduler
    scheduler.add_job(run_nightly_decay_job, CronTrigger(hour=2, minute=0), id="nightly_decay")
    scheduler.add_job(run_reverification_job, CronTrigger(hour=8, minute=0), id="reverification")
    scheduler.add_job(run_retrain_job, CronTrigger(day=1, hour=3, minute=0), id="retrain_classifier")
    scheduler.start()
    logger.info("APScheduler started with 3 cron jobs")
    yield
    scheduler.shutdown()
    logger.info("APScheduler shut down")


app = FastAPI(
    title="NadiNet API",
    description="Full-stack NGO volunteer coordination platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth endpoints ───
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


@app.post("/api/v1/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Simple JWT login — in production use proper user management."""
    # Dev-mode: accept any credentials, issue a token
    if form_data.username and form_data.password:
        token = create_access_token({"sub": form_data.username, "role": "coordinator"})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


# ─── Include all routers ───
PREFIX = "/api/v1"

# Public (no auth): webhooks
app.include_router(webhooks_router, prefix=PREFIX, tags=["webhooks"])

# Protected routes
app.include_router(ingest_router, prefix=PREFIX, tags=["ingest"])
app.include_router(needs_router, prefix=PREFIX, tags=["needs"])
app.include_router(volunteers_router, prefix=PREFIX, tags=["volunteers"])
app.include_router(dispatch_router, prefix=PREFIX, tags=["dispatch"])
app.include_router(debrief_router, prefix=PREFIX, tags=["debrief"])
app.include_router(reporters_router, prefix=PREFIX, tags=["reporters"])
app.include_router(dashboard_router, prefix=PREFIX, tags=["dashboard"])
app.include_router(reports_router, prefix=PREFIX, tags=["reports"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nadinet-api"}


@app.get("/")
async def root():
    return {"message": "NadiNet API — visit /docs for OpenAPI documentation"}
