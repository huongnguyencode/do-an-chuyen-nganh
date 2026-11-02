# Hướng dẫn triển khai hệ thống chấm bài Python & phản hồi sư phạm LLM

Tài liệu này giải thích cấu trúc mã nguồn, trách nhiệm của từng phần (Hưởng, Hải Anh, Bảo) và cách kiểm thử toàn hệ thống.

## Phạm vi toàn hệ thống

Ứng dụng nhận bài làm Python của sinh viên, lưu snapshot mã nguồn, gửi từng ca kiểm thử đến Judge0 qua API, chuẩn hóa kết quả và hiển thị cho sinh viên. Khi bài làm đã chấm xong (`completed`), chưa đạt hết kiểm thử (`all_passed=false`) và sinh viên **chủ động bấm yêu cầu gợi ý**, hệ thống kiểm tra hạn mức (`help_quota`), dựng `HintContextV1` đã lọc bí mật, đóng gói Prompt theo mức **KM** (lượt 1) hoặc **KH** (lượt 2–3), gọi mô hình ngôn ngữ lớn qua `LLMServiceInterface` và kiểm duyệt qua **Output Guardrail** trước khi lưu và trừ lượt.

## Quy ước kiến trúc

Luồng phụ thuộc được giữ theo một chiều:

```text
API / giao diện -> service nghiệp vụ -> repository / Judge0 client / LLM Adapter
                                       -> PostgreSQL ứng dụng
```

Mã sinh viên không bao giờ được chạy trực tiếp trong tiến trình FastAPI. Mô hình ngôn ngữ lớn (LLM) chỉ diễn giải bằng chứng lỗi đã xác minh, tuyệt đối không tự quyết định trạng thái đúng/sai của bài nộp (theo cơ sở thực nghiệm của Phung et al., 2023).

---

## Phần 1 — Nền tảng ứng dụng và dữ liệu

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `app/main.py` | Khởi tạo FastAPI, đăng ký router bài tập, bài nộp, gợi ý KM/KH và giao diện web. |
| `app/config.py` | Đọc cấu hình từ biến môi trường (`.env`) cho PostgreSQL, Judge0, Quota và LLM Adapter. |
| `app/database.py` | Tạo SQLAlchemy engine và session PostgreSQL. |
| `app/models/` | Mô hình quan hệ cho `Student`, `Problem`, `TestCase`, `Submission`, `GradingRun`, `TestResult`, `HelpQuota` và `HintRequest`. |
| `alembic/` | Chuỗi migration có phiên bản (`0001` → `0002` → `0003`). |

### Mô hình dữ liệu toàn hệ thống (Chương 2 - Mục 2.5)

```text
student 1---N submission N---1 problem 1---N test_case
   |                |             |
   |                1             |
   |                |             |
   |                N             |
   |           grading_run 1---N test_result
   |                |
   +---N help_quota N---+
            |
            1
            |
            N
       hint_request (tham chiếu đồng thời help_quota, submission và grading_run)
```

---

## Phần 2 — Lát cắt chấm P01 & Worker Judge0 (Hải Anh)

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `app/judging/harness.py` | Tạo runner cho đúng một test, mã hóa base64 mã sinh viên và kiểm tra envelope/nonce. |
| `app/judging/judge0.py` | Gửi submission (`wait=false`), nhận token, polling và giải mã phản hồi base64. |
| `app/judging/comparison.py` | So sánh JSON theo đúng kiểu và giá trị (`9 != "9"`, `1 != True`). |
| `app/judging/service.py` | Claim lượt chấm bằng `FOR UPDATE SKIP LOCKED`, gọi Judge0 ngoài transaction và lưu verdict. |
| `app/worker.py` | Tiến trình worker lấy các lượt `queued` từ PostgreSQL. |

---

## Phần 3 & 4 — API sinh viên, lọc test ẩn & Danh mục 20 bài (Hưởng & Hải Anh)

- `app/problems/p01_sum_numbers.py` và `app/problems/catalog.py`: 20 bài tập Python (`P01`–`P20`), mỗi bài 8 test (3 công khai + 5 ẩn = 160 test), kèm `reference_code` và `wrong_samples`.
- `app/api/problems.py`, `app/api/submissions.py`, `app/api/serializers.py`: Chỉ xuất chi tiết test công khai; tuyệt đối không lộ `args`, `expected`, `actual`, `error_summary` hay `judge0_token` của test ẩn.

---

## Phần 5 — Hợp đồng `HintContextV1`

- `app/hint_context/schemas.py` và `app/hint_context/service.py`: Hàm `build_hint_context` kiểm tra sở hữu, trạng thái chấm `completed`, `all_passed=false`, không có lỗi kỹ thuật và trích xuất tối đa `K=2` test công khai sai ổn định theo `test_index`.

---

## Phần 6 — Giao diện sinh viên (UC01–UC06)

- `/ui/problems`: Danh sách 20 bài đã công bố.
- `/ui/problems/{slug}`: Đề bài, ví dụ công khai, trình soạn thảo mã, kết quả chấm trực tiếp và bảng **Hỗ trợ sư phạm (Scaffolding KM / KH)** kèm đồng hồ đếm ngược cooldown 120s.
- `/ui/history`: Lịch sử các snapshot mã đã nộp, kết quả các lần chấm và danh sách gợi ý KM/KH đã lưu gắn với từng phiên bản mã.

---

## Phần 7 — Module Phản hồi Sư phạm LLM, Output Guardrail & Hạn mức (Bảo)

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `app/hints/prompts.py` | Đóng gói System Prompt phiên bản hóa (`v1.0`) tách biệt mức **KM** (lượt 1) và **KH** (lượt 2–3) theo Keuning et al. (2018); bọc mã sinh viên và bằng chứng trong thẻ `<student_code>` / `<execution_evidence>` chống Prompt Injection. |
| `app/hints/guardrail.py` | Bộ lọc đầu ra **Output Guardrail**: kiểm tra bằng Regex (chặn khối mã ```...```, định nghĩa `def`/`class`/`lambda`, câu lệnh `return` đáp án trực tiếp, gợi ý thay thế một dòng) và kiểm tra độ trùng lặp token (`Token Overlap`) với `reference_code` trong chế độ Benchmark. |
| `app/hints/adapters.py` | Giao diện `LLMServiceInterface` (Adapter Pattern): `APIDemoAdapter` (gọi REST API OpenAI/Groq/OpenRouter/Gemini-compatible), `ColabQwenAdapter` (gọi `Qwen2.5-Coder-7B-Instruct` trên Colab T4), `FakeLLMAdapter` (phục vụ kiểm thử tự động có dán nhãn). |
| `app/hints/service.py` | Cài đặt **Thuật toán 2.2** (`generate_and_validate_hint_core` và `HintOrchestrationService`): khóa ngắn `help_quota` bằng `SELECT FOR UPDATE`, kiểm tra tối đa 3 lượt/sinh viên/bài, cooldown 120s, chống gửi trùng bằng `request_key`, thu hồi yêu cầu quá hạn (`expires_at`), gọi LLM + retry tối đa `max_retries=2` lần ngoài transaction DB, và chỉ cộng `used_count` trong giao dịch hoàn tất khi có gợi ý hợp lệ. |
| `app/api/hints.py` | Cung cấp các endpoint `POST /api/submissions/{id}/hints`, `POST /api/hint-requests`, `GET /api/hint-requests/{id}` và `GET /api/problems/{slug}/hints`. |

---

## Phần 8 — Khung Đánh giá Benchmark M1–M5 & Script PoC Chương 2 / Chương 3

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `app/benchmark/evaluator.py` | Chạy đánh giá ngoại tuyến (`run_offline_benchmark`) trên tập bài tập và `wrong_samples`, xuất log `.jsonl`, bảng chấm Rubric R1–R5 `.csv` cho hai người chấm độc lập và tính bộ chỉ số **M1–M5** (`compute_m1_to_m5`). |
| `scripts/poc_mbpp_harness.py` | Kịch bản PoC Chương 2 (Hưởng & Hải Anh): kiểm chứng harness với lời giải chuẩn, mã sai mẫu, lỗi cú pháp, in JSON giả ra `stdout` và gọi `sys.exit(0)`. |
| `scripts/poc_guardrail_and_injection.py` | Kịch bản PoC Chương 2 (Bảo): kiểm chứng đóng khung Prompt chống Prompt Injection, bộ lọc Regex + Token Overlap và cơ chế retry tối đa `N=2` lần. |
| `scripts/poc_judge0_memory.py` | Kịch bản PoC Chương 2 (Hải Anh): kiểm tra `/languages`, `/config_info` và hành vi vượt giới hạn bộ nhớ `128000 KB` (128 MB) trên Judge0. |
| `scripts/run_benchmark_m1_m5.py` | CLI chạy batch benchmark (`--mode fake | api_demo | colab_qwen`) phục vụ thực nghiệm Chương 3. |
| `docs/references.md` | Tổng hợp và ghi chú chi tiết 6 tài liệu/liên kết tham khảo cốt lõi của đề tài. |
