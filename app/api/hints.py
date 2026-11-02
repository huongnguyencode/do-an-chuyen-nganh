from functools import lru_cache
import threading

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_student
from app.api.schemas import (
    DirectHintRequestCreate,
    HintRequestResponse,
    HistoryHintItem,
    ProblemHintsResponse,
    SubmissionHintCreate,
)
from app.api.serializers import serialize_hint_request, serialize_quota_status
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.hints.service import HintOrchestrationService, HintRequestRejectedError
from app.models import Student


router = APIRouter(prefix="/api", tags=["hints"])

# Vách ngăn cô lập tài nguyên (Non-blocking Bulkhead Semaphore):
# Giới hạn cứng tối đa 15 luồng đồng thời được phép đi vào vùng gọi LLM bên trong Default AnyIO Threadpool (40 tokens).
# Request thứ 16 sẽ fail-fast (429 llm_busy) trong < 0.1ms và trả lại luồng ngay lập tức,
# đảm bảo luôn có tối thiểu 25/40 token rảnh rỗi cho get_current_student, xem đề bài và nộp bài.
MAX_CONCURRENT_LLM_REQUESTS = 15
LLM_BULKHEAD_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_LLM_REQUESTS)


@lru_cache(maxsize=1)
def get_hint_service() -> HintOrchestrationService:
    return HintOrchestrationService(SessionLocal, settings=get_settings())


def _rejection_response(exc: HintRequestRejectedError) -> JSONResponse:
    content: dict[str, object] = {
        "detail": exc.code,
        "error_code": exc.code,
    }
    if exc.retry_after_seconds is not None:
        content["retry_after_seconds"] = exc.retry_after_seconds
    if exc.remaining_count is not None:
        content["remaining_count"] = exc.remaining_count
    headers = (
        {"Retry-After": str(exc.retry_after_seconds)}
        if exc.retry_after_seconds is not None
        else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=headers,
    )


def _busy_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "llm_busy",
            "error_code": "llm_busy",
            "retry_after_seconds": 5,
        },
        headers={"Retry-After": "5"},
    )


def _execute_hint_request_with_bulkhead(
    service: HintOrchestrationService,
    *,
    student_id: int,
    submission_id: int,
    grading_run_id: int,
    request_key: str,
) -> HintRequestResponse | JSONResponse:
    if not LLM_BULKHEAD_SEMAPHORE.acquire(blocking=False):
        return _busy_response()
    try:
        req, quota_view = service.request_hint(
            student_id=student_id,
            submission_id=submission_id,
            grading_run_id=grading_run_id,
            request_key=request_key,
        )
    except HintRequestRejectedError as exc:
        return _rejection_response(exc)
    finally:
        LLM_BULKHEAD_SEMAPHORE.release()
    return serialize_hint_request(req, quota_view)


@router.post(
    "/submissions/{submission_id}/hints",
    response_model=HintRequestResponse,
    status_code=status.HTTP_200_OK,
)
def request_submission_hint(
    submission_id: int,
    payload: SubmissionHintCreate,
    student: Student = Depends(get_current_student),
    service: HintOrchestrationService = Depends(get_hint_service),
) -> HintRequestResponse | JSONResponse:
    return _execute_hint_request_with_bulkhead(
        service,
        student_id=student.id,
        submission_id=submission_id,
        grading_run_id=payload.grading_run_id,
        request_key=payload.request_key,
    )


@router.post(
    "/hint-requests",
    response_model=HintRequestResponse,
    status_code=status.HTTP_200_OK,
)
def create_hint_request(
    payload: DirectHintRequestCreate,
    student: Student = Depends(get_current_student),
    service: HintOrchestrationService = Depends(get_hint_service),
) -> HintRequestResponse | JSONResponse:
    return _execute_hint_request_with_bulkhead(
        service,
        student_id=student.id,
        submission_id=payload.submission_id,
        grading_run_id=payload.grading_run_id,
        request_key=payload.request_key,
    )


@router.get("/hint-requests/{request_id}", response_model=HintRequestResponse)
def get_hint_request(
    request_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
    service: HintOrchestrationService = Depends(get_hint_service),
) -> HintRequestResponse:
    found = service.get_hint_request(
        db,
        student_id=student.id,
        request_id=request_id,
    )
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="hint_request_not_found",
        )
    req, quota_view = found
    return serialize_hint_request(req, quota_view)


@router.get("/problems/{slug}/hints", response_model=ProblemHintsResponse)
def get_problem_hints_and_quota(
    slug: str,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
    service: HintOrchestrationService = Depends(get_hint_service),
) -> ProblemHintsResponse:
    result = service.list_problem_hints(
        db,
        student_id=student.id,
        problem_slug=slug,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="problem_not_found",
        )
    quota_view, hints = result
    return ProblemHintsResponse(
        quota=serialize_quota_status(quota_view),
        hints=[
            HistoryHintItem(
                request_id=hint.id,
                grading_run_id=hint.grading_run_id,
                level=hint.level,  # type: ignore[arg-type]
                hint_text=hint.hint_text or "",
                prompt_version=hint.prompt_version,
                model_id=hint.model_id,
                created_at=hint.created_at,
                completed_at=hint.completed_at,
            )
            for hint in hints
            if hint.hint_text
        ],
    )
