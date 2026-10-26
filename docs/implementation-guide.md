# Hướng dẫn triển khai phần Hưởng và Hải Anh

Tài liệu này giải thích cấu trúc mã nguồn, trách nhiệm của từng phần và cách kiểm
thử. Tài liệu được cập nhật trước hoặc cùng lúc với mỗi lát cắt triển khai để
người trong nhóm có thể đọc mã theo đúng luồng nghiệp vụ.

## Phạm vi

Ứng dụng nhận bài làm Python, lưu snapshot mã nguồn, gửi từng ca kiểm thử đến
Judge0, chuẩn hóa kết quả và cung cấp dữ liệu đã lọc cho `HintContextV1`.

Phần hiện tại **không** gọi AI, không sinh KM/KH và không quản lý quota. Những
chức năng đó thuộc phần tích hợp với Bảo sau khi đường chấm bài ổn định.

## Quy ước kiến trúc

Luồng phụ thuộc được giữ theo một chiều:

```text
API / giao diện -> service nghiệp vụ -> repository / Judge0 client
                                      -> PostgreSQL ứng dụng
```

Mã sinh viên không bao giờ được chạy trực tiếp trong tiến trình FastAPI. Khi
phần chấm được triển khai, mã chỉ được chuyển tới Judge0 qua API.

Mỗi bài yêu cầu một hàm Python có tên và chữ ký xác định. Đối số và giá trị trả
về phải biểu diễn được bằng JSON. `print()` không phải hợp đồng đầu ra.

## Phần 1 — nền tảng ứng dụng và dữ liệu

### Thành phần

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `app/main.py` | Khởi tạo FastAPI, cung cấp liveness và readiness endpoint. |
| `app/config.py` | Đọc cấu hình từ biến môi trường; không hard-code credential. |
| `app/database.py` | Tạo SQLAlchemy engine và session PostgreSQL. |
| `app/models/` | Mô hình quan hệ cho bài tập, bài nộp và kết quả chấm. |
| `alembic/` | Migration có phiên bản; không tạo bảng tự động khi khởi động API. |
| `tests/` | Kiểm tra HTTP và ràng buộc thật trên PostgreSQL. |
| `compose.yaml` | Chạy PostgreSQL, API và test trong container. |

### Mô hình dữ liệu

```text
student 1---N submission N---1 problem 1---N test_case
                    |
                    1
                    |
                    N
               grading_run 1---N test_result N---1 test_case
```

- `submission` là snapshot bất biến của mã và phiên bản bài/test lúc nộp.
- `grading_run` là một lần chấm; chấm lại tạo hàng mới.
- `test_result` thuộc đồng thời một lần chấm và một test.
- Khóa ghép bảo đảm test result không trỏ sang bài hoặc phiên bản test khác.
- `all_passed=true` chỉ hợp lệ khi lượt chấm `completed` và có ít nhất một test.
- Chi tiết test ẩn và `reference_code` là dữ liệu nội bộ, không thuộc response
  công khai.

### Cách kiểm thử bằng Docker

```bash
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm test
docker compose up api
```

Test service chạy chuỗi `upgrade -> downgrade -> upgrade` trước `pytest`. Như
vậy cả hai chiều migration đều được thử và test dùng schema do migration tạo
trên PostgreSQL thật, không dùng SQLite thay thế.

Kiểm tra thủ công sau khi API chạy:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

Kỳ vọng cả hai trả trạng thái `ok`; readiness chỉ thành công khi truy vấn được
PostgreSQL.

## Phần 2 — lát cắt chấm P01

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `app/problems/` | Danh mục bài, test, lời giải tham chiếu và mã sai mẫu nội bộ. |
| `app/seed.py` | Nạp 20 bài/160 test và tài khoản demo; chạy lặp không nhân bản. |
| `app/judging/harness.py` | Tạo runner cho đúng một test và kiểm tra envelope/nonce. |
| `app/judging/judge0.py` | Gửi submission, nhận token, polling và giải mã phản hồi. |
| `app/judging/comparison.py` | So sánh JSON theo kiểu và giá trị. |
| `app/judging/service.py` | Claim lượt chấm, gọi Judge0 ngoài transaction và lưu verdict. |
| `app/worker.py` | Tiến trình lấy các lượt `queued` từ PostgreSQL. |

Mỗi test là một submission Judge0. Harness chứa mã sinh viên ở dạng base64,
gọi hàm với arguments của test và chỉ phát một envelope có nonce. `stdout` và
`stderr` Python thông thường của mã sinh viên được chuyển hướng; output thừa,
JSON sai hoặc nonce sai làm báo cáo `incomplete`, tuyệt đối không tạo kết quả
đạt. `expected` không được gửi vào harness mà chỉ được so sánh trong ứng dụng.

Worker claim hàng bằng `FOR UPDATE SKIP LOCKED`, commit trạng thái `running` rồi
mới gọi Judge0. Vì thế không giữ khóa DB trong lúc chờ dịch vụ ngoài. Khi hoàn
tất, worker khóa lại đúng lượt chấm, insert kết quả với unique constraint và chỉ
cập nhật lượt còn `running`; kết quả đến muộn không ghi đè lượt đã kết thúc.

Phân loại chính:

- Judge0 Accepted + envelope value: `passed` hoặc `wrong_answer`;
- envelope syntax/runtime: lỗi mã sinh viên, lượt chấm vẫn `completed`;
- Judge0 status 5: `time_limit_exceeded`;
- network/HTTP/phản hồi Judge0 hỏng: `technical_error`;
- output harness thiếu/sai: `incomplete` và lượt chấm `technical_error`.

Harness làm giảm nguy cơ `print()` giả bằng redirect, JSON chính xác và nonce,
nhưng PoC không tuyên bố chống mọi mã đối kháng trong cùng tiến trình. Smoke test
trên Judge0 thật vẫn bắt buộc cho `os._exit`, thay file descriptor và giới hạn
sandbox.

Seed không cập nhật nội dung một problem/test version đã tồn tại. Muốn sửa đề
hoặc oracle phải tăng version và thực hiện migration/seed tương ứng; cách này
tránh một lần chạy seed làm thay đổi ý nghĩa của lịch sử chấm cũ.

### Chạy Phần 2

```bash
docker compose run --rm api python -m app.seed
docker compose --profile grading run --rm worker --once
```

`JUDGE0_LANGUAGE_ID` không có giá trị mặc định. Người vận hành phải lấy danh
sách `/languages` từ chính instance Judge0 rồi cấu hình ID Python phù hợp.

## Phần 3 — API sinh viên và lọc test ẩn

| Endpoint | Chức năng |
| --- | --- |
| `GET /api/problems` | Danh sách bài đã công bố, không có test/lời giải. |
| `GET /api/problems/{slug}` | Đề và chỉ các test công khai. |
| `POST /api/submissions` | Lưu snapshot mã và tạo lượt `queued`. |
| `GET /api/submissions/{id}/grading-runs/{run}` | Kết quả tổng hợp và chi tiết test công khai. |
| `GET /api/submissions` | Lịch sử của sinh viên hiện tại. |

`student_id` không có trong request schema. Trong PoC, backend lấy tài khoản từ
`DEMO_LOGIN_NAME`; dữ liệu phải được seed trước. Một submission của tài khoản
khác trả 404 để không xác nhận tài nguyên đó có tồn tại.

Serializer kết quả chỉ đưa các hàng `is_public=true` vào `public_results`.
Test ẩn chỉ đóng góp vào tổng số đã ghi, số đạt và số trượt; API không xuất
args, expected, actual, error hoặc Judge0 token của test ẩn.

## Phần 4 — danh mục 20 bài

`app/problems/catalog.py` chứa P02–P20 và ghép với P01. Tất cả bài là nội dung
tự soạn, không gắn nguồn MBPP. Mỗi bài có đúng 8 test: 3 công khai và 5 ẩn,
một lời giải tham chiếu và một mã sai mẫu kèm danh sách test dự kiến trượt.

Các quy tắc dễ mơ hồ đã được chốt trong đề:

- P03 trả `None` cho danh sách rỗng;
- P05 phân biệt hoa thường và dấu cách;
- P09 chỉ nhận số không âm và `gcd(0, 0) = 0`;
- P11 trả `None` nếu thiếu hai giá trị phân biệt;
- P15 dùng trị tuyệt đối của số âm;
- P17 giữ thứ tự xuất hiện đầu tiên trong danh sách trái;
- P19 tách từ theo nhóm khoảng trắng;
- P20 bỏ qua ký tự không phải ngoặc.

`tests/test_problem_catalog.py` dùng 20 oracle độc lập với các chuỗi lời giải
tham chiếu để kiểm tra toàn bộ 160 expected. Test cũng xác minh dữ liệu JSON,
chỉ số test, cờ công khai và cú pháp của 20 lời giải/20 mã sai mẫu. Việc chạy
các chuỗi mã qua Judge0 thật vẫn thuộc kiểm chứng tích hợp, không được thay bằng
`exec` trong backend.

## Phần 5 — hợp đồng `HintContextV1`

Service nội bộ:

```python
build_hint_context(
    db,
    student_id=...,
    submission_id=...,
    grading_run_id=...,
    max_evidence=2,
)
```

Service kiểm tra đúng chủ sở hữu, run thuộc submission, trạng thái đã hoàn tất,
kết quả không phải lỗi kỹ thuật, bài chưa đạt và đủ đúng số test snapshot. Các
mã lỗi ổn định gồm `not_owner`, `grading_run_not_found`, `grading_pending`,
`grading_technical_error` và `all_passed`.

Nếu có test công khai sai, context chọn ổn định theo `test_index` và lấy tối đa
K=2. Nếu chỉ test ẩn sai, context chỉ có `HiddenSummaryEvidence`; kiểu dữ liệu
này không định nghĩa trường args/expected/actual nên không thể vô tình serialize
các trường đó thành `null`. Context không có reference code, quota, KM/KH hoặc
nội dung AI.

## Phần 6 — giao diện sinh viên

Các trang HTML:

- `/ui/problems`: danh sách 20 bài đã công bố;
- `/ui/problems/{slug}`: đề, ví dụ công khai, editor và nút Nộp bài;
- `/ui/history`: snapshot mã và trạng thái các lượt đã nộp.

JavaScript chỉ gửi `problem_id` và `source_code`, sau đó polling endpoint kết
quả tối đa 120 lần. Kết quả được dựng bằng DOM `textContent`, không đưa chuỗi từ
mã sinh viên/error vào `innerHTML`. Jinja autoescape mã nguồn trên trang lịch
sử. Giao diện không có nút gợi ý AI giả.

## Công việc kiểm chứng còn lại

Code theo phạm vi Phần 1–6 đã có. Trước nghiệm thu vẫn phải chạy toàn bộ pytest
trên PostgreSQL, chạy smoke Judge0 thật và kiểm tra trực tiếp JSON/UI trong môi
trường Docker có quyền truy cập daemon.

Mỗi phần chỉ được triển khai sau khi nội dung “code gì – làm gì – test gì” được
xác nhận.
