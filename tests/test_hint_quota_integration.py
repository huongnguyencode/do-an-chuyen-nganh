from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.hints import get_hint_service
from app.config import Settings
from app.database import SessionLocal
from app.hints.adapters import FakeLLMAdapter, LLMGenerationResult
from app.hints.service import HintOrchestrationService, HintRequestRejectedError
from app.main import app
from app.models import (
    GradingRun,
    HelpQuota,
    HintRequest,
    Problem,
    Student,
    Submission,
    TestCase,
    TestResult,
)
from app.seed import seed_all


class FakeClock:
    def __init__(self, initial: datetime) -> None:
        self.current = initial

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current = self.current + timedelta(seconds=seconds)


def create_graded_submission(
    *,
    failed_indexes: set[int] = {1, 2},
    owner_login: str = "demo",
    source_code: str = "def sum_numbers(numbers):\n    return 0",
    run_status: str = "completed",
    all_passed: bool | None = False,
) -> tuple[int, int, int, int]:
    with SessionLocal.begin() as db:
        seed_all(db)
        student = db.scalar(select(Student).where(Student.login_name == owner_login))
        if student is None:
            student = Student(login_name=owner_login)
            db.add(student)
            db.flush()
        problem = db.scalar(select(Problem).where(Problem.slug == "p01-sum-numbers"))
        assert problem is not None
        submission = Submission(
            student_id=student.id,
            problem_id=problem.id,
            source_code=source_code,
            problem_version=1,
            test_version=1,
        )
        db.add(submission)
        db.flush()
        run = GradingRun(
            submission_id=submission.id,
            problem_id=problem.id,
            test_version=1,
            status=run_status,
            all_passed=all_passed,
            expected_test_count=8,
            runtime_config={},
        )
        db.add(run)
        db.flush()
        if run_status == "completed":
            tests = list(
                db.scalars(
                    select(TestCase)
                    .where(TestCase.problem_id == problem.id)
                    .order_by(TestCase.test_index)
                )
            )
            for test in tests:
                failed = test.test_index in failed_indexes
                db.add(
                    TestResult(
                        grading_run_id=run.id,
                        test_case_id=test.id,
                        problem_id=problem.id,
                        test_version=1,
                        status="wrong_answer" if failed else "passed",
                        actual_json=0 if failed else test.expected_json,
                        error_summary=None,
                    )
                )
        return student.id, problem.id, submission.id, run.id


def test_full_quota_cooldown_resubmission_and_ai_failure_lifecycle(
    clean_database: None,
) -> None:
    """Kiểm chứng chuỗi nghiệp vụ mục 7.3 & Bảng 2.6.8 Chương 2 bằng đồng hồ giả."""
    student_id, problem_id, sub1_id, run1_id = create_graded_submission(
        failed_indexes={1, 2}
    )
    clock = FakeClock(datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC))
    settings = Settings(
        llm_mode="fake",
        hint_max_quota=3,
        hint_cooldown_seconds=120,
        hint_request_expire_seconds=60,
        hint_max_retries=2,
    )
    adapter = FakeLLMAdapter(
        responses=[
            "Gợi ý KM lần 1: Hàm của bạn đang dừng ngay ở phần tử đầu tiên của danh sách.",
            LLMGenerationResult(
                raw_text=None,
                latency_ms=50,
                model_id="fake-poc-provider",
                provider="fake",
                error="llm_timeout",
            ),
            "Gợi ý KH lần 2: Hãy kiểm tra vị trí đặt lệnh trả về so với vòng lặp cộng dồn.",
            "Gợi ý KH lần 3: Hãy thử chạy tay với danh sách [2, 3, 4] sau khi dời lệnh trả về ra ngoài vòng lặp.",
        ]
    )
    service = HintOrchestrationService(
        SessionLocal, adapter=adapter, settings=settings, now_fn=clock
    )

    # 1. Lúc 10:00:00: Yêu cầu gợi ý lần 1 -> nhận KM, quota = 1/3, cooldown tới 10:02:00
    req1, quota1 = service.request_hint(
        student_id=student_id,
        submission_id=sub1_id,
        grading_run_id=run1_id,
        request_key="key-km-1",
    )
    assert req1.status == "succeeded"
    assert req1.level == "KM"
    assert quota1.used_count == 1
    assert quota1.remaining_count == 2
    assert quota1.next_level == "KH"

    # 2. Gửi trùng idempotency key -> trả lại đúng yêu cầu cũ, không gọi thêm LLM, không trừ thêm lượt
    req1_dup, quota1_dup = service.request_hint(
        student_id=student_id,
        submission_id=sub1_id,
        grading_run_id=run1_id,
        request_key="key-km-1",
    )
    assert req1_dup.id == req1.id
    assert quota1_dup.used_count == 1

    # 3. Lúc 10:00:30: Sinh viên nộp lại bài mới -> quota vẫn 1/3, vẫn bị chặn bởi cooldown 90s
    clock.advance(30)
    _, _, sub2_id, run2_id = create_graded_submission(
        failed_indexes={1, 3},
        source_code="def sum_numbers(numbers):\n    return -1",
    )
    with pytest.raises(HintRequestRejectedError) as cooldown_err:
        service.request_hint(
            student_id=student_id,
            submission_id=sub2_id,
            grading_run_id=run2_id,
            request_key="key-during-cooldown",
        )
    assert cooldown_err.value.code == "cooldown_active"
    assert cooldown_err.value.retry_after_seconds == 90

    # 4. Lúc 10:02:01 (đã qua 120s): Gọi gợi ý nhưng AI bị lỗi timeout -> status=failed, KHÔNG trừ lượt!
    clock.advance(91)
    req_fail, quota_after_fail = service.request_hint(
        student_id=student_id,
        submission_id=sub2_id,
        grading_run_id=run2_id,
        request_key="key-ai-fail",
    )
    assert req_fail.status == "failed"
    assert req_fail.error_code == "llm_timeout"
    assert quota_after_fail.used_count == 1
    assert quota_after_fail.remaining_count == 2
    assert quota_after_fail.cooldown_remaining_seconds == 0

    # 5. Lúc 10:02:10: Yêu cầu lại với key mới -> nhận KH (lượt 2/3), mốc cooldown mới 10:04:10
    clock.advance(9)
    req2, quota2 = service.request_hint(
        student_id=student_id,
        submission_id=sub2_id,
        grading_run_id=run2_id,
        request_key="key-kh-2",
    )
    assert req2.status == "succeeded"
    assert req2.level == "KH"
    assert quota2.used_count == 2
    assert quota2.remaining_count == 1

    # 6. Lúc 10:04:15: Yêu cầu lượt 3 -> nhận KH (lượt 3/3), hết lượt
    clock.advance(125)
    req3, quota3 = service.request_hint(
        student_id=student_id,
        submission_id=sub2_id,
        grading_run_id=run2_id,
        request_key="key-kh-3",
    )
    assert req3.status == "succeeded"
    assert req3.level == "KH"
    assert quota3.used_count == 3
    assert quota3.remaining_count == 0
    assert quota3.next_level is None

    # 7. Lúc 10:07:00: Yêu cầu lượt 4 -> bị từ chối vì quota_exhausted (429)
    clock.advance(165)
    with pytest.raises(HintRequestRejectedError) as exhausted_err:
        service.request_hint(
            student_id=student_id,
            submission_id=sub2_id,
            grading_run_id=run2_id,
            request_key="key-kh-4",
        )
    assert exhausted_err.value.code == "quota_exhausted"
    assert exhausted_err.value.status_code == 429
    assert problem_id == req3.problem_id


def test_only_one_processing_request_per_student_problem_and_stale_recovery(
    clean_database: None,
) -> None:
    student_id, problem_id, sub_id, run_id = create_graded_submission(
        failed_indexes={1}
    )
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
    clock = FakeClock(now)
    settings = Settings(llm_mode="fake")
    service = HintOrchestrationService(
        SessionLocal, adapter=FakeLLMAdapter(), settings=settings, now_fn=clock
    )

    with SessionLocal.begin() as db:
        db.add(HelpQuota(student_id=student_id, problem_id=problem_id, used_count=0))
        db.flush()
        db.add(
            HintRequest(
                student_id=student_id,
                problem_id=problem_id,
                submission_id=sub_id,
                grading_run_id=run_id,
                request_key="in-flight-1",
                level="KM",
                status="processing",
                prompt_version="v1.0",
                model_id="fake",
                evidence_snapshot={},
                generation_log=[],
                created_at=now,
                expires_at=now + timedelta(seconds=60),
            )
        )

    # 1. Partial unique index ở PostgreSQL chặn tạo dòng processing thứ hai cho cùng (student_id, problem_id)
    with SessionLocal.begin() as db:
        db.add(
            HintRequest(
                student_id=student_id,
                problem_id=problem_id,
                submission_id=sub_id,
                grading_run_id=run_id,
                request_key="in-flight-2",
                level="KM",
                status="processing",
                prompt_version="v1.0",
                model_id="fake",
                evidence_snapshot={},
                generation_log=[],
                created_at=now,
                expires_at=now + timedelta(seconds=60),
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()

    # 2. Service từ chối với request_already_processing khi request đầu chưa hết hạn
    with pytest.raises(HintRequestRejectedError) as in_flight_err:
        service.request_hint(
            student_id=student_id,
            submission_id=sub_id,
            grading_run_id=run_id,
            request_key="new-request-while-busy",
        )
    assert in_flight_err.value.code == "request_already_processing"

    # 3. Sau khi quá hạn 65 giây, request treo được tự động thu hồi thành failed (không trừ lượt) và cho phép tạo mới
    clock.advance(65)
    recovered_req, quota_view = service.request_hint(
        student_id=student_id,
        submission_id=sub_id,
        grading_run_id=run_id,
        request_key="request-after-lease-expiry",
    )
    assert recovered_req.status == "succeeded"
    assert quota_view.used_count == 1


def test_hidden_only_failure_is_rejected_without_consuming_quota(
    clean_database: None,
) -> None:
    student_id, _, sub_id, run_id = create_graded_submission(failed_indexes={8})
    settings = Settings(llm_mode="fake", hint_allow_hidden_only=False)
    service = HintOrchestrationService(
        SessionLocal, adapter=FakeLLMAdapter(), settings=settings
    )

    with pytest.raises(HintRequestRejectedError) as caught:
        service.request_hint(
            student_id=student_id,
            submission_id=sub_id,
            grading_run_id=run_id,
            request_key="hidden-only-key",
        )
    assert caught.value.code == "no_public_evidence_available"


def test_hint_api_endpoints_and_history_integration(clean_database: None) -> None:
    _, _, sub_id, run_id = create_graded_submission(failed_indexes={1, 2})
    settings = Settings(llm_mode="fake")
    fake_service = HintOrchestrationService(
        SessionLocal, adapter=FakeLLMAdapter(), settings=settings
    )
    app.dependency_overrides[get_hint_service] = lambda: fake_service
    client = TestClient(app)
    try:
        post_resp = client.post(
            f"/api/submissions/{sub_id}/hints",
            json={"grading_run_id": run_id, "request_key": "api-key-1"},
        )
        assert post_resp.status_code == 200, post_resp.text
        data = post_resp.json()
        assert data["status"] == "succeeded"
        assert data["level"] == "KM"
        assert data["quota"]["used_count"] == 1
        assert data["quota"]["remaining_count"] == 2
        request_id = data["request_id"]

        # Xem lại gợi ý qua GET /api/hint-requests/{id} không trừ thêm lượt
        get_resp = client.get(f"/api/hint-requests/{request_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["hint_text"] == data["hint_text"]
        assert get_resp.json()["quota"]["used_count"] == 1

        # Xem danh sách gợi ý theo bài qua GET /api/problems/{slug}/hints
        prob_hints_resp = client.get("/api/problems/p01-sum-numbers/hints")
        assert prob_hints_resp.status_code == 200
        prob_hints = prob_hints_resp.json()
        assert prob_hints["quota"]["used_count"] == 1
        assert len(prob_hints["hints"]) == 1
        assert prob_hints["hints"][0]["request_id"] == request_id

        # Xem lịch sử bài nộp qua GET /api/submissions chứa gợi ý đã lưu gắn với submission
        hist_resp = client.get("/api/submissions")
        assert hist_resp.status_code == 200
        hist = hist_resp.json()
        assert len(hist) == 1
        assert len(hist[0]["hints"]) == 1
        assert hist[0]["hints"][0]["level"] == "KM"
    finally:
        app.dependency_overrides.pop(get_hint_service, None)

