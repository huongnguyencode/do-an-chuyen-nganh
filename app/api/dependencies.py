from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Student


def get_current_student(db: Session = Depends(get_db)) -> Student:
    """Danh tính demo do backend cấu hình, không nhận student_id từ client."""
    login_name = get_settings().demo_login_name
    student = db.scalar(select(Student).where(Student.login_name == login_name))
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_student_not_seeded",
        )
    return student
