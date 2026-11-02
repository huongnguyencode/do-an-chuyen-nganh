from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.hints import router as hints_router
from app.api.problems import router as problems_router
from app.api.submissions import router as submissions_router
from app.config import get_settings
from app.database import get_db
from app.request_logging import RequestLoggingMiddleware
from app.web.routes import router as web_router


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(RequestLoggingMiddleware)
app.include_router(problems_router)
app.include_router(submissions_router)
app.include_router(hints_router)
app.include_router(web_router)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness: tiến trình API vẫn phục vụ request."""
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/ready", tags=["system"])
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness: API truy vấn được PostgreSQL ứng dụng."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database_unavailable",
        ) from exc
    return {"status": "ok", "database": "ready"}
