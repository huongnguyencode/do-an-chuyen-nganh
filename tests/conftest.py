import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def clean_database() -> None:
    """Xóa dữ liệu trong database test dành riêng cho integration test."""
    with SessionLocal.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE test_result, grading_run, submission, test_case, "
                "problem, student RESTART IDENTITY CASCADE"
            )
        )
