import sys

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Problem, Student, TestCase
from app.problems.catalog import ALL_PROBLEMS


def seed_problem(db: Session, data: dict) -> Problem:
    problem_values = {
        key: value
        for key, value in data.items()
        if key not in {"tests", "wrong_samples"}
    }
    statement = insert(Problem).values(**problem_values)
    inserted_id = db.execute(
        statement.on_conflict_do_nothing(index_elements=[Problem.slug]).returning(
            Problem.id
        )
    ).scalar_one_or_none()
    if inserted_id is None:
        problem_id = db.execute(
            select(Problem.id).where(Problem.slug == data["slug"])
        ).scalar_one()
    else:
        problem_id = inserted_id

    for test in data["tests"]:
        values = {
            "problem_id": problem_id,
            "test_version": data["test_version"],
            "test_index": test["test_index"],
            "arguments_json": test["args"],
            "expected_json": test["expected"],
            "is_public": test["is_public"],
            "purpose": test["purpose"],
        }
        test_statement = (
            insert(TestCase)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_test_case_problem_version_index")
        )
        db.execute(test_statement)

    return db.execute(select(Problem).where(Problem.id == problem_id)).scalar_one()


def seed_all(db: Session) -> None:
    demo_student = insert(Student).values(login_name="demo")
    db.execute(demo_student.on_conflict_do_nothing(index_elements=[Student.login_name]))
    for problem_data in ALL_PROBLEMS:
        seed_problem(db, problem_data)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with SessionLocal.begin() as db:
        seed_all(db)
    print("Seed hoàn tất: 20 bài, 160 test và tài khoản demo.")


if __name__ == "__main__":
    main()
