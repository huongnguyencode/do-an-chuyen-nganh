# Hệ thống Chấm bài tập Lập trình Python Tự động có Phản hồi Sư phạm bằng Mô hình Ngôn ngữ Lớn (LLM)

Ứng dụng FastAPI hỗ trợ sinh viên luyện tập lập trình Python: xem đề bài, nộp mã nguồn, chấm từng ca kiểm thử trong sandbox **Judge0**, chủ động yêu cầu gợi ý sư phạm theo hai cấp độ **KM (Knowledge about Mistakes)** và **KH (Knowledge about How to Proceed)** từ mô hình ngôn ngữ lớn (LLM) có kiểm duyệt đầu ra (**Output Guardrail**) và quản lý hạn mức (**3 lượt/bài, cooldown 120 giây**).

---

## Trạng thái hiện tại

- **20 bài tập Python (`P01`–`P20`)**: mỗi bài có 3 test công khai + 5 test ẩn (tổng **160 test**), kèm lời giải tham chiếu (`reference_code`) và các mẫu mã sai có chủ đích (`wrong_samples`).
- **Migrations PostgreSQL (`0001` → `0002` → `0003`)**: đầy đủ 8 bảng `student`, `problem`, `test_case`, `submission`, `grading_run`, `test_result`, `help_quota` và `hint_request` (kèm partial unique index chống xử lý đồng thời).
- **Luồng chấm Judge0 & Harness**: tách biệt thực thi mã không tin cậy với backend FastAPI; chống giả mạo JSON trên `stdout` bằng `nonce` ngẫu nhiên.
- **Module Phản hồi Sư phạm LLM (Chương 2 - Mục 2.2 & 2.4)**:
  - **Adapter Pattern (`LLMServiceInterface`)**: hỗ trợ `APIDemoAdapter` (OpenAI/Groq/OpenRouter/Gemini-compatible REST API), `ColabQwenAdapter` (`Qwen2.5-Coder-7B-Instruct` trên Google Colab T4) và `FakeLLMAdapter` (kiểm thử tự động).
  - **Prompt KM/KH phiên bản hóa (`v1.0`)**: đóng khung `<student_code>` và `<execution_evidence>` chống Prompt Injection.
  - **Output Guardrail**: lọc khối mã có rào, định nghĩa hàm, câu lệnh trả về đáp án trực tiếp (Regex) và độ trùng lặp token với lời giải chuẩn (`Token Overlap` trong Benchmark), tự động sinh lại tối đa `N=2` lần (`HINT_MAX_RETRIES=2`).
  - **Giao dịch Quota & Cooldown (`HintOrchestrationService`)**: tối đa 3 lượt thành công/sinh viên/bài (lần 1 `KM`, lần 2–3 `KH`), cooldown 120s, nộp lại không reset quota, lỗi AI hoặc vi phạm Guardrail **không trừ lượt**.
- **Khung Đánh giá Thực nghiệm Benchmark (Chương 2 - Mục 2.6 & Chương 3)**:
  - Xuất log sinh phản hồi `.jsonl`, bảng chấm Rubric R1–R5 `.csv` cho hai người chấm độc lập và công cụ tính bộ chỉ số **M1–M5**.
- **Tài liệu tham khảo cốt lõi**: xem tại [`docs/references.md`](docs/references.md), hướng dẫn kiến trúc tại [`docs/implementation-guide.md`](docs/implementation-guide.md), kết quả kiểm chứng tại [`docs/verification.md`](docs/verification.md) và các quyết định thiết kế tại [`docs/open-decisions.md`](docs/open-decisions.md).

---

## Kiến trúc tổng thể

```text
Trình duyệt / API client
        │
        ▼
FastAPI (UC01–UC06) ──────────────────────► PostgreSQL ứng dụng
  │                  │                        │ lưu student, problem, test_case,
  │ tạo grading_run  │ kiểm tra help_quota,   │ submission, grading_run, test_result,
  │                  │ dựng HintContextV1     │ help_quota và hint_request
  ▼                  ▼                        │
Worker ◄─────────────┼────────────────────────┘
  │                  │
  │ gửi harness,     │ đóng gói Prompt KM/KH, gọi Adapter
  │ polling token    │ và kiểm duyệt Output Guardrail (retry <= 2)
  ▼                  ▼
Judge0          LLM Service (API Demo / Colab Qwen)
```

Các service Docker của repository:

| Service | Chức năng | Cổng |
| --- | --- | --- |
| `db` | PostgreSQL 17 của ứng dụng | `5432` |
| `api` | FastAPI, Giao diện Web (UC01–UC06) và OpenAPI | `8000` |
| `test` | Migration test (`upgrade → downgrade → upgrade`) và pytest | Không mở cổng |
| `worker` | Lấy lượt chấm từ PostgreSQL và gọi Judge0 | Không mở cổng |

---

## 1. Chuẩn bị cấu hình (`.env`)

```bash
cp .env.example .env
```

Các nhóm biến môi trường chính trong `.env`:

```dotenv
# 1. PostgreSQL ứng dụng
DATABASE_URL=postgresql+psycopg://python_poc:python_poc@db:5432/python_poc
POSTGRES_DB=python_poc
POSTGRES_USER=python_poc
POSTGRES_PASSWORD=python_poc

# 2. Judge0 Execution Sandbox
JUDGE0_BASE_URL=https://ce.judge0.com
JUDGE0_LANGUAGE_ID=100
JUDGE0_CPU_TIME_LIMIT_SECONDS=5
JUDGE0_WALL_TIME_LIMIT_SECONDS=10
JUDGE0_MEMORY_LIMIT_KB=256000

# 3. Chính sách Hạn mức & Gợi ý KM/KH
HINT_MAX_QUOTA=3
HINT_COOLDOWN_SECONDS=120
HINT_REQUEST_EXPIRE_SECONDS=60
HINT_MAX_EVIDENCE=2
HINT_MAX_RETRIES=2
HINT_ALLOW_HIDDEN_ONLY=false

# 4. Chiến lược LLM lai (api_demo | colab_qwen | fake | disabled)
LLM_MODE=api_demo
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL_ID=gpt-4o-mini
COLAB_QWEN_MODEL_ID=Qwen/Qwen2.5-Coder-7B-Instruct
COLAB_QWEN_ENDPOINT_URL=
GUARDRAIL_TOKEN_OVERLAP_THRESHOLD=0.75
```

> **Lưu ý:** Nếu `LLM_MODE=api_demo` mà chưa điền `LLM_API_KEY`, khi bấm yêu cầu gợi ý hệ thống sẽ báo lỗi dịch vụ (`llm_api_key_not_configured`) và **không trừ lượt gợi ý của sinh viên**. Để thử nghiệm luồng giao diện offline không cần khóa API, có thể đặt `LLM_MODE=fake` (phản hồi sẽ được gắn nhãn `[FAKE-PROVIDER]`).

---

## 2. Chạy bằng Docker Compose (PostgreSQL + Pytest + API + Worker)

```bash
docker compose --profile test --profile grading build
docker compose up -d db
docker compose run --rm test
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed
docker compose up -d api
docker compose --profile grading up -d worker
```

Các địa chỉ truy cập sau khi khởi động:
- Giao diện danh sách bài tập (UC01, UC02, UC03, UC04, UC05): <http://localhost:8000/ui/problems>
- Giao diện lịch sử bài nộp & gợi ý KM/KH (UC06): <http://localhost:8000/ui/history>
- Tài liệu OpenAPI / Swagger: <http://localhost:8000/docs>

---

## 3. Chạy các kịch bản PoC Chương 2 & Công cụ Benchmark Chương 3

Từ thư mục dự án (với môi trường ảo Python `.venv` hoặc trong container `api`):

```bash
# 1. PoC Harness (Hưởng & Hải Anh): thử mã đúng, mã sai, in JSON giả và sys.exit()
python -m scripts.poc_mbpp_harness

# 2. PoC Prompt KM/KH, chống Prompt Injection & Output Guardrail (Bảo)
python -m scripts.poc_guardrail_and_injection

# 3. PoC Kiểm tra /languages, /config_info và giới hạn RAM 128 MB trên Judge0 (Hải Anh)
python -m scripts.poc_judge0_memory

# 4. Chạy Batch Benchmark ngoại tuyến và xuất JSONL + CSV Rubric R1–R5 + chỉ số M1–M5
python -m scripts.run_benchmark_m1_m5 --mode fake --limit 20 --output-dir artifacts/benchmark
```

---

## 4. Danh sách API Sinh viên (UC01–UC06)

| Method | Endpoint | Use Case | Chức năng |
| --- | --- | --- | --- |
| `GET` | `/api/problems` | UC01 | Danh sách 20 bài tập đã công bố |
| `GET` | `/api/problems/{slug}` | UC02 | Chi tiết đề bài và 3 ví dụ kiểm thử công khai |
| `POST` | `/api/submissions` | UC03 | Lưu snapshot mã nguồn và tạo lượt chấm `queued` |
| `GET` | `/api/submissions/{submission_id}/grading-runs/{run_id}` | UC04 | Trạng thái chấm và kết quả kiểm thử công khai |
| `POST` | `/api/submissions/{submission_id}/hints` | UC05 | Yêu cầu gợi ý KM/KH (kiểm tra quota, cooldown, Guardrail) |
| `POST` | `/api/hint-requests` | UC05 | Endpoint thay thế nhận trực tiếp `submission_id`, `grading_run_id`, `request_key` |
| `GET` | `/api/hint-requests/{request_id}` | UC05/UC06 | Xem lại trạng thái/nội dung gợi ý đã lưu (không trừ lượt) |
| `GET` | `/api/problems/{slug}/hints` | UC02/UC05 | Xem trạng thái quota, đồng hồ cooldown và danh sách gợi ý của bài |
| `GET` | `/api/submissions` | UC06 | Lịch sử bài nộp kèm các lần chấm và gợi ý KM/KH đã lưu |

---

## 5. Cấu trúc thư mục

```text
alembic/              Chuỗi migration PostgreSQL (0001 -> 0002 -> 0003)
app/api/              Router FastAPI cho bài tập, bài nộp và gợi ý KM/KH
app/benchmark/        Khung đánh giá ngoại tuyến, xuất JSONL/CSV Rubric và tính M1–M5
app/hint_context/     Trích xuất ngữ cảnh lỗi đã lọc bí mật (HintContextV1)
app/hints/            Adapter LLM (API Demo / Colab Qwen), Prompt KM/KH, Output Guardrail & Quota Service
app/judging/          Judge0 client, harness có nonce, comparator và grading service
app/models/           SQLAlchemy models (8 bảng quan hệ)
app/problems/         Danh mục 20 bài tập Python, 160 test, lời giải chuẩn và mẫu mã sai
app/templates/        Giao diện Jinja2 (problems, problem_detail, history)
app/static/           CSS và JavaScript điều phối chấm bài + yêu cầu gợi ý KM/KH
app/web/              Route giao diện HTML
codexs/               Tài liệu đặc tả yêu cầu hệ thống ban đầu
docs/                 Hướng dẫn triển khai, tài liệu tham khảo, quyết định mở và kết quả kiểm chứng
scripts/              Script smoke test Judge0, PoC Chương 2 và CLI chạy Benchmark M1–M5
tests/                Bộ kiểm thử tự động (Unit, Guardrail, Benchmark, API, UI, PostgreSQL Integration)
```
