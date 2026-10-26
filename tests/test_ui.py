from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Problem
from app.seed import seed_all


client = TestClient(app)


def prepare_ui() -> Problem:
    with SessionLocal.begin() as db:
        seed_all(db)
        problem = db.scalar(select(Problem).where(Problem.slug == "p01-sum-numbers"))
        assert problem is not None
        db.expunge(problem)
        return problem


def test_problem_page_renders_all_twenty_problems(clean_database: None) -> None:
    prepare_ui()

    response = client.get("/ui/problems")

    assert response.status_code == 200
    assert response.text.count('class="problem-card"') == 20
    assert "Tính tổng danh sách" in response.text
    assert "Kiểm tra ngoặc cân bằng" in response.text


def test_detail_page_has_editor_and_no_hidden_or_fake_hint_content(
    clean_database: None,
) -> None:
    prepare_ui()

    response = client.get("/ui/problems/p01-sum-numbers")

    assert response.status_code == 200
    assert 'id="source-code"' in response.text
    assert 'id="submit-code"' in response.text
    assert "Danh sách dài hơn để phát hiện return sớm" not in response.text
    assert "Tạo gợi ý AI" not in response.text
    assert "Cần trợ giúp" not in response.text


def test_history_escapes_student_source_code(clean_database: None) -> None:
    problem = prepare_ui()
    source = "def sum_numbers(numbers):\n    return '<script>alert(1)</script>'"
    accepted = client.post(
        "/api/submissions",
        json={"problem_id": problem.id, "source_code": source},
    )
    assert accepted.status_code == 202

    response = client.get("/ui/history")

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
