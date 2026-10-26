from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_student
from app.api.serializers import serialize_history
from app.database import get_db
from app.models import Problem, Student, TestCase


BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
router = APIRouter(tags=["web"], include_in_schema=False)


@router.get("/", response_class=RedirectResponse)
def index() -> RedirectResponse:
    return RedirectResponse(url="/ui/problems", status_code=302)


@router.get("/ui/problems", response_class=HTMLResponse)
def problem_list_page(
    request: Request,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> HTMLResponse:
    problems = list(
        db.scalars(
            select(Problem)
            .where(Problem.is_published.is_(True))
            .order_by(Problem.source_key, Problem.version)
        )
    )
    return templates.TemplateResponse(
        request=request,
        name="problems.html",
        context={"problems": problems, "student": student},
    )


@router.get("/ui/problems/{slug}", response_class=HTMLResponse)
def problem_detail_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> HTMLResponse:
    problem = db.scalar(
        select(Problem).where(Problem.slug == slug, Problem.is_published.is_(True))
    )
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="problem_not_found")
    public_tests = list(
        db.scalars(
            select(TestCase)
            .where(
                TestCase.problem_id == problem.id,
                TestCase.test_version == problem.test_version,
                TestCase.is_public.is_(True),
            )
            .order_by(TestCase.test_index)
        )
    )
    return templates.TemplateResponse(
        request=request,
        name="problem_detail.html",
        context={
            "problem": problem,
            "public_tests": public_tests,
            "student": student,
        },
    )


@router.get("/ui/history", response_class=HTMLResponse)
def history_page(
    request: Request,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> HTMLResponse:
    history = serialize_history(db, student.id)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"history": history, "student": student},
    )
