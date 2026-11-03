
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ServiceError, service_error_handler
from app.routers import auth
from app.routers import student
from app.routers import trainer
from app.routers import admin
from app.routers import account
from app.routers import notifications
from app.routers import games
from app.routers import content
from app.routers import feedback
from app.routers import reports

app = FastAPI(title="Chess Academy API", version="0.1.0")

app.add_exception_handler(ServiceError, service_error_handler)

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(trainer.router)
app.include_router(admin.router)
app.include_router(account.router)
app.include_router(notifications.router)
app.include_router(games.router)
app.include_router(content.router)
app.include_router(content.media_router)
app.include_router(feedback.router)
app.include_router(reports.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "connected"}
