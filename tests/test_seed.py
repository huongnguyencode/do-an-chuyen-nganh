from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Problem, Student, TestCase
from app.seed import seed_all


def test_seed_is_idempotent(clean_database: None) -> None:
    with SessionLocal.begin() as db:
        seed_all(db)
    with SessionLocal.begin() as db:
        seed_all(db)

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Problem)) == 20
        assert db.scalar(select(func.count()).select_from(TestCase)) == 160
        assert db.scalar(select(func.count()).select_from(Student)) == 1
        problem = db.scalar(select(Problem))
        assert problem is not None
        assert problem.source_name == "self_authored"
        assert problem.function_name == "sum_numbers"
