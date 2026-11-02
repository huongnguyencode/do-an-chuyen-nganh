# Kết quả kiểm chứng

Tài liệu chỉ ghi các lệnh đã thực sự chạy. Trạng thái `CHƯA CHẠY` không được
hiểu là thành công.

## Phần 1 — nền tảng và cơ sở dữ liệu

Ngày kiểm tra: 26/10/2026.

| Kiểm tra | Lệnh | Kết quả thực tế |
| --- | --- | --- |
| Cú pháp Python | `python3 -m compileall -q app alembic tests` | PASS |
| Phân giải Compose API/DB | `docker compose config` | PASS |
| Phân giải đầy đủ service test | `docker compose --profile test config` | PASS |
| Docker daemon ban đầu | `docker info` | BLOCKED: không có quyền truy cập `/var/run/docker.sock` |
| Build với cấu hình Docker ở `/tmp` | `DOCKER_CONFIG=/tmp/huong-docker-config docker compose --profile test build` | BLOCKED: Docker API từ chối quyền |
| Cài dependency tạm để test ngoài Docker | `pip install ...` trong virtualenv `/tmp` | BLOCKED: môi trường không phân giải được DNS/PyPI |
| Alembic trên PostgreSQL | `docker compose run --rm test` | PASS: chạy chuỗi upgrade → downgrade → upgrade |
| Pytest trên PostgreSQL | `docker compose run --rm test` | PASS: 48 test, 11 cảnh báo, 8.79 giây |
| Health/readiness qua TestClient | `docker compose run --rm test` | PASS |
| Health/readiness HTTP thật | `curl /health`, `curl /health/ready` | PASS: API và PostgreSQL đều trả `ok` |

## Nội dung test container sẽ thực hiện

Khi Docker daemon khả dụng, lệnh sau tạo database kiểm thử riêng, chạy migration
theo chuỗi lên/xuống/lên và cuối cùng chạy pytest:

```bash
docker compose --profile test build
docker compose up -d db
docker compose run --rm test
```

Các assertion hiện có:

- liveness trả HTTP 200;
- readiness truy vấn được PostgreSQL;
- không thể tạo hai test cùng `(problem_id, test_version, test_index)`;
- không thể đặt `all_passed=true` khi lượt chấm có 0 test;
- lượt chấm `completed` bắt buộc có verdict.

## Phần 2 — P01 và worker Judge0

| Kiểm tra | Kết quả hiện tại |
| --- | --- |
| Biên dịch cú pháp toàn bộ `app`, `alembic`, `tests` | PASS |
| Phân giải Compose với profile `test` và `grading` | PASS |
| Kiểm tra nội dung P01 | PASS: 8 test, 3 công khai, 5 ẩn; 8 expected khớp phép tổng độc lập |
| Kiểm tra nguồn harness và comparator không cần dependency | PASS: mã sinh viên được mã hóa; `9 != "9"`, `1 != true` |
| Số hàm test tự động đã viết | 28 |
| Build image test | PASS: container test khởi động bằng image mới |
| Seed idempotent trên PostgreSQL test | PASS qua `tests/test_seed.py`; seed database chính vẫn chưa chạy |
| Test client token/polling/HTTP/timeout bằng MockTransport | PASS |
| Test worker với fake Judge0 và PostgreSQL | PASS |
| Smoke test Judge0 thật | PASS với Judge0 CE công khai, Python 3.12.5 (language ID 100) |

### Smoke test Judge0 thật cho P01

Lệnh:

```bash
bash scripts/smoke_p01.sh
```

Cấu hình đã chạy: CPU 5 giây, wall time 10 giây, RAM 256000 KB. Cấu hình
CPU 2 giây, wall time 5 giây và RAM 128000 KB trước đó làm public instance trả
`time_limit_exceeded` cho mã đúng, nên không được ghi nhận là lần chấm đúng.

| Bài nộp | Kết quả |
| --- | --- |
| `return sum(numbers)` | PASS: `completed`, `all_passed=true`, 8/8 test đạt |
| `return` đặt trong vòng lặp | PASS: `completed`, `all_passed=false`, 2/8 test đạt; ba test công khai là `wrong_answer` |
| Thiếu dấu `:` ở khai báo hàm | PASS: `completed`, `all_passed=false`, 0/8; ba test công khai là `syntax_error` |

API chỉ xuất chi tiết ba test công khai trong cả ba phản hồi. Năm test ẩn chỉ
đóng góp vào số tổng. Smoke test này sử dụng dịch vụ công khai để nghiệm thu kỹ
thuật; không dùng endpoint công khai cho mã riêng tư hoặc môi trường production.

## Phần 3 — API sinh viên

| Kiểm tra | Kết quả hiện tại |
| --- | --- |
| Cú pháp API/schema/serializer | PASS qua `compileall` |
| Compose sau khi thêm API | PASS cấu hình tĩnh |
| Test API đã viết | 6 ca |
| Test API + PostgreSQL trong Docker | PASS: 6/6 hàm test API |

Sáu ca API bao phủ danh sách/chi tiết bài, snapshot khi nộp, từ chối
`student_id` từ client, lọc bí mật test ẩn khỏi JSON thật, chặn đọc lượt chấm
của sinh viên khác và lịch sử đúng chủ sở hữu.

## Phần 4 — danh mục bài tập

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Số bài | PASS: 20 |
| Số test | PASS: 160 |
| Phân bố | PASS: 60 công khai, 100 ẩn |
| Lời giải tham chiếu | PASS cú pháp: 20/20 |
| Mã sai mẫu | PASS cú pháp: 20/20 |
| Expected so với oracle độc lập | PASS: 160/160 |
| Seed 20 bài trên PostgreSQL | CHƯA CHẠY vì Docker daemon bị chặn |
| 20 lời giải qua Judge0 thật | CHƯA CHẠY vì chưa có instance/cấu hình chạy được |
| 20 mã sai qua Judge0 thật | CHƯA CHẠY vì chưa có instance/cấu hình chạy được |

Lệnh kiểm tra nội dung đã chạy:

```bash
PYTHONPATH=. python3 tests/test_problem_catalog.py
```

Kết quả: `PASS catalog: 20 problems, 160 independently verified tests`.

## Phần 5 — HintContextV1

| Kiểm tra | Kết quả hiện tại |
| --- | --- |
| Cú pháp schema/service/test | PASS qua `compileall` |
| Số hàm test | 5 hàm, gồm 4 trường hợp eligibility tham số hóa |
| Context có test công khai sai | Đã viết test chọn test_index 1, 2 khi K=2 |
| Chỉ sai test ẩn | Đã viết test JSON không có key args/expected/actual và không có secret |
| Pending/technical/all passed | Đã viết test từ chối với mã lỗi tương ứng |
| Sai chủ sở hữu | Đã viết test `not_owner` |
| Đúng snapshot mã cũ | Đã viết test không trộn bài nộp mới |
| Chạy pytest trên PostgreSQL | PASS: 8 ca chạy sau tham số hóa |

## Phần 6 — giao diện

| Kiểm tra | Kết quả hiện tại |
| --- | --- |
| Cú pháp Python web routes/templates integration | PASS qua `compileall` |
| Cú pháp JavaScript | PASS qua `node --check app/static/problem.js` |
| Compose sau khi thêm Jinja2/UI | PASS cấu hình tĩnh |
| Test UI đã viết | 3 ca, PASS |
| Danh sách đủ 20 card | PASS |
| Trang đề không có nội dung test ẩn/nút AI giả | PASS |
| Mã sinh viên được HTML escape trong lịch sử | PASS |
| Build image test sau Phần 6 | PASS |

Tổng kết lượt chạy trước Phần 7: pytest thu thập 48 ca, **48 passed**, 11 cảnh báo trong
8.79 giây.

## Phần 7 — Module LLM Sư phạm (KM/KH), Output Guardrail, Quota/Cooldown & Benchmark Framework

Ngày kiểm tra: 02/11/2026 (Python 3.12.6 trên Windows `.venv`).

| Kiểm tra | Lệnh thực thi | Kết quả thực tế |
| --- | --- | --- |
| Biên dịch cú pháp toàn bộ `app`, `alembic`, `tests`, `scripts` | `py -3.12 -m compileall -q app alembic tests scripts` | PASS (exit code 0) |
| PoC Chương 2 (Hải Anh) — Execution Harness Base64 + Nonce trên 5 kịch bản `TC01–TC05` | `py -3.12 scripts/poc_mbpp_harness.py` | PASS: `TC01` (`value: 9`), `TC02` (`value: 2`), `TC03` (`syntax_error`), `TC04` (`value: 0`, bỏ qua stdout JSON giả mạo), `TC05` (`SystemExit`) |
| PoC Chương 2 (Bảo) — Prompt Framing `v1.0`, chống thoát thẻ XML, Output Guardrail & Retry (`max_retries=2`) | `.\.venv\Scripts\python.exe scripts/poc_guardrail_and_injection.py` | PASS: `xml_breakout_sanitized=true`, chặn `fenced_code_leak` / `inline_replacement_leak` / `token_overlap_leak`, retry thành công ở lần thử 2 |
| Chạy Offline Benchmark Pipeline `M1–M5` & xuất CSV chấm chéo Rubric `R1–R5` cho 20 bài (40 mẫu KM + KH) | `.\.venv\Scripts\python.exe scripts/run_benchmark_m1_m5.py --mode fake --limit 20` | PASS: sinh đủ `benchmark_generations.jsonl`, `rubric_evaluation_sheet.csv` (40 dòng), `summary_m1_m5.json` (`N=40, S=40`) |
| Unit tests không phụ thuộc PostgreSQL (`test_comparison`, `test_harness`, `test_judge0_client`, `test_problem_catalog`, `test_hints_and_guardrail`) | `.\.venv\Scripts\python.exe -m pytest tests/test_comparison.py tests/test_harness.py tests/test_judge0_client.py tests/test_problem_catalog.py tests/test_hints_and_guardrail.py` | PASS: **24 passed in 0.91s** (không còn cảnh báo `PytestCollectionWarning` trên `TestCase`/`TestResult`) |
| Kiểm tra cú pháp JavaScript giao diện sau tối ưu | `node --check app/static/problem.js` | PASS (exit code 0) |
| Integration tests `test_hint_quota_integration.py` (Quota 3 lượt, Cooldown 120s, Idempotency, Lease recovery, Refund khi guardrail fail) trên PostgreSQL | `docker compose run --rm test` | CHƯA CHẠY trên máy local hiện tại (cần khởi chạy container PostgreSQL qua Docker Compose) |
| Benchmark thực nghiệm với `Qwen2.5-Coder-7B-Instruct` trên Colab T4 (`--mode colab`) | `.\.venv\Scripts\python.exe scripts/run_benchmark_m1_m5.py --mode colab --limit 20` | CHƯA CHẠY (cần cấu hình `COLAB_QWEN_BASE_URL` trỏ tới ngrok/cloudflared endpoint trên Google Colab) |
