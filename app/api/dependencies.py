from fastapi import HTTPException, status
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Student


def get_current_student() -> Student:
    """Danh tính demo do backend cấu hình, không nhận student_id hay header chưa ký từ client.

    Mở và đóng phiên đọc ngắn hạn ngay lập tức để tránh giữ kết nối CSDL
    trong suốt thời gian chờ các tác vụ ngoại vi (như gọi LLM ở API gợi ý).
    """
    login_name = get_settings().demo_login_name
    with SessionLocal() as db:
        student = db.scalar(select(Student).where(Student.login_name == login_name))
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="demo_student_not_seeded",
            )
        db.expunge(student)
        return student
