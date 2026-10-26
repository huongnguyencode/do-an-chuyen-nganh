from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_student
from app.api.schemas import ProblemDetail, ProblemSummary, PublicTestExample
from app.database import get_db
from app.models import Problem, Student, TestCase


router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("", response_model=list[ProblemSummary])
def list_problems(
    db: Session = Depends(get_db),
    _: Student = Depends(get_current_student),
) -> list[ProblemSummary]:
    problems = db.scalars(
        select(Problem)
        .where(Problem.is_published.is_(True))
        .order_by(Problem.source_key, Problem.version)
    )
    return [
        ProblemSummary(
            id=problem.id,
            slug=problem.slug,
            title=problem.title,
            function_signature=problem.function_signature,
            version=problem.version,
        )
        for problem in problems
    ]


@router.get("/{slug}", response_model=ProblemDetail)
def get_problem(
    slug: str,
    db: Session = Depends(get_db),
    _: Student = Depends(get_current_student),
) -> ProblemDetail:
    problem = db.scalar(
        select(Problem).where(Problem.slug == slug, Problem.is_published.is_(True))
    )
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="problem_not_found")
    public_tests = db.scalars(
        select(TestCase)
        .where(
            TestCase.problem_id == problem.id,
            TestCase.test_version == problem.test_version,
            TestCase.is_public.is_(True),
        )
        .order_by(TestCase.test_index)
    )
    return ProblemDetail(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        function_signature=problem.function_signature,
        version=problem.version,
        statement=problem.statement,
        constraints_text=problem.constraints_text,
        public_tests=[
            PublicTestExample(
                test_index=test.test_index,
                args=test.arguments_json,
                expected=test.expected_json,
                purpose=test.purpose,
            )
            for test in public_tests
        ],
    )
