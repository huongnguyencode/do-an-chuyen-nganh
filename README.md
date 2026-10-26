# PoC hệ thống luyện tập Python

Ứng dụng FastAPI cho sinh viên xem bài tập Python, nộp mã, chấm từng test qua
Judge0 và xem lại lịch sử. Dữ liệu ứng dụng được lưu trong PostgreSQL riêng;
backend không trực tiếp chạy mã sinh viên.

## Trạng thái hiện tại

- 20 bài Python tự soạn, mỗi bài có 3 test công khai và 5 test ẩn.
- Migration PostgreSQL có kiểm tra cả `upgrade → downgrade → upgrade`.
- API, giao diện, worker Judge0 và `HintContextV1` đã được triển khai.
- Pytest trên PostgreSQL: **48/48 test pass**.
- Smoke test thật P01 qua Judge0: mã đúng 8/8, mã sai 2/8, mã lỗi cú pháp 0/8.
- AI, nội dung KM/KH và quota gợi ý chưa được triển khai; đây là phần tích hợp
  sau với Bảo.

Xem kết quả thực chạy tại [`docs/verification.md`](docs/verification.md), mô tả
kiến trúc tại [`docs/implementation-guide.md`](docs/implementation-guide.md) và
các quyết định chưa chốt tại [`docs/open-decisions.md`](docs/open-decisions.md).

## Kiến trúc

```text
Trình duyệt / API client
        │
        ▼
FastAPI ───────────────► PostgreSQL ứng dụng
  │                         │
  │ tạo grading_run         │ lưu problem, test_case,
  │                         │ submission và test_result
  ▼                         │
Worker ◄────────────────────┘
  │
  │ gửi harness, nhận token và polling
  ▼
Judge0
```

Các service Docker của repository:

| Service | Chức năng | Cổng |
| --- | --- | --- |
| `db` | PostgreSQL 17 của ứng dụng | `5432` |
| `api` | FastAPI, UI và OpenAPI | `8000` |
| `test` | Migration test và pytest | Không mở cổng |
| `worker` | Lấy lượt chấm từ PostgreSQL và gọi Judge0 | Không mở cổng |

Judge0 không nằm trong `compose.yaml` của dự án. Worker kết nối tới một Judge0
đã được triển khai riêng qua HTTP API.

## Yêu cầu hệ thống

- Linux hoặc môi trường có Docker Engine.
- Docker Compose v2 (`docker compose`).
- Git nếu cần tải hoặc đưa mã lên GitHub.
- Một Judge0 có thể truy cập từ container worker.
- Các cổng `5432` và `8000` chưa bị ứng dụng khác sử dụng.

Kiểm tra:

```bash
docker --version
docker compose version
docker info
git --version
```

Nếu `docker info` báo không có quyền truy cập `/var/run/docker.sock`, hãy khởi
động Docker và cấp quyền Docker cho tài khoản hiện tại theo chính sách của máy.

## 1. Chuẩn bị cấu hình

Từ thư mục dự án:

```bash
cd /home/huong/do_an_chuyen_nganh
cp .env.example .env
```

`.env` chứa cấu hình cục bộ và đã được `.gitignore` loại khỏi Git. Không commit
file này lên GitHub.

Các biến quan trọng:

```dotenv
DATABASE_URL=postgresql+psycopg://python_poc:python_poc@db:5432/python_poc
POSTGRES_DB=python_poc
POSTGRES_USER=python_poc
POSTGRES_PASSWORD=python_poc

JUDGE0_BASE_URL=http://judge0:2358
JUDGE0_LANGUAGE_ID=
JUDGE0_CPU_TIME_LIMIT_SECONDS=5
JUDGE0_WALL_TIME_LIMIT_SECONDS=10
JUDGE0_MEMORY_LIMIT_KB=256000
```

Giữ hostname `db` trong `DATABASE_URL` khi API chạy bằng Compose. `localhost`
bên trong container không trỏ tới container PostgreSQL.

### Cấu hình Judge0

Luôn lấy language ID từ chính instance sẽ dùng:

```bash
curl -fsS "https://DIA_CHI_JUDGE0/languages/" |
python3 -c 'import json,sys; print([x for x in json.load(sys.stdin) if "Python" in x["name"]])'
```

Sau đó sửa `.env`:

```dotenv
JUDGE0_BASE_URL=https://DIA_CHI_JUDGE0
JUDGE0_LANGUAGE_ID=ID_PYTHON_CUA_INSTANCE
```

Để smoke test, dự án đã được kiểm chứng ngày 26/10/2026 với Judge0 CE công
khai, Python 3.12.5:

```dotenv
JUDGE0_BASE_URL=https://ce.judge0.com
JUDGE0_LANGUAGE_ID=100
```

Language ID có thể thay đổi theo deployment, vì vậy cần kiểm tra lại endpoint
`/languages/`. Dịch vụ công khai chỉ phù hợp cho mã mẫu; không gửi mã riêng tư
hoặc dùng nó làm production. Với production, nên triển khai Judge0 riêng theo
[hướng dẫn phát hành chính thức](https://github.com/judge0/judge0/releases).

## 2. Build Docker image

Build API, test và worker:

```bash
docker compose --profile test --profile grading build
```

Khi dependency, Dockerfile hoặc cấu hình đóng gói thay đổi và cần loại bỏ cache:

```bash
docker compose --profile test --profile grading build --no-cache
```

## 3. Chạy PostgreSQL và toàn bộ test

```bash
docker compose up -d db
docker compose ps
docker compose run --rm test
```

Service `test` sẽ:

1. Tạo database riêng `python_poc_test` nếu chưa tồn tại.
2. Chạy `alembic upgrade head`.
3. Chạy `alembic downgrade base`.
4. Chạy lại `alembic upgrade head`.
5. Chạy toàn bộ pytest trên PostgreSQL thật.

Kết quả đã kiểm chứng:

```text
48 passed
```

Các cảnh báo collection của model `TestCase`/`TestResult`, cảnh báo TestClient
và rollback fixture hiện không làm test thất bại.

## 4. Migration và seed database chính

Tạo schema ứng dụng:

```bash
docker compose run --rm api alembic upgrade head
```

Seed 20 bài, 160 test và tài khoản demo:

```bash
docker compose run --rm api python -m app.seed
```

Có thể chạy lại để kiểm tra idempotency; dữ liệu không được nhân đôi:

```bash
docker compose run --rm api python -m app.seed
```

Kết quả mong đợi:

```text
Seed hoàn tất: 20 bài, 160 test và tài khoản demo.
```

## 5. Khởi động API và worker

```bash
docker compose up -d api
docker compose --profile grading up -d worker
docker compose ps
```

Nếu vừa sửa `.env`, tạo lại container để nạp cấu hình mới:

```bash
docker compose up -d --force-recreate api
docker compose --profile grading up -d --force-recreate worker
```

Theo dõi log:

```bash
docker compose logs -f api worker
```

Nhấn `Ctrl+C` chỉ dừng theo dõi log, không dừng container.

## 6. Kiểm tra API và giao diện

```bash
curl -fsS http://localhost:8000/health
echo
curl -fsS http://localhost:8000/health/ready
echo
curl -fsS http://localhost:8000/api/problems |
python3 -c 'import json,sys; data=json.load(sys.stdin); print("Số bài:", len(data))'
```

Kết quả mong đợi:

```text
{"status":"ok","service":"Python Practice PoC"}
{"status":"ok","database":"ready"}
Số bài: 20
```

Các địa chỉ:

- Giao diện bài tập: <http://localhost:8000/ui/problems>
- Lịch sử bài nộp: <http://localhost:8000/ui/history>
- OpenAPI/Swagger: <http://localhost:8000/docs>

## 7. Smoke test Judge0 end-to-end

Sau khi API và worker đều chạy:

```bash
bash scripts/smoke_p01.sh
```

Script tự động kiểm tra:

- health và readiness;
- mã đúng đạt 8/8;
- mã `return` quá sớm đạt 2/8 và các ví dụ công khai là `wrong_answer`;
- mã thiếu dấu `:` đạt 0/8 và các ví dụ công khai là `syntax_error`;
- cả ba lượt được lưu với trạng thái `completed`;
- API chỉ xuất chi tiết ba test công khai.

Kết quả cuối mong đợi:

```text
PASS correct submission
PASS wrong submission
PASS syntax-error submission
All P01 smoke checks passed.
```

## API sinh viên

| Method | Endpoint | Chức năng |
| --- | --- | --- |
| `GET` | `/api/problems` | Danh sách bài đã công bố |
| `GET` | `/api/problems/{slug}` | Chi tiết bài và test công khai |
| `POST` | `/api/submissions` | Lưu mã và tạo lượt chấm `queued` |
| `GET` | `/api/submissions` | Lịch sử sinh viên hiện tại |
| `GET` | `/api/submissions/{submission_id}/grading-runs/{run_id}` | Trạng thái và kết quả chấm |

PoC xác định sinh viên bằng `DEMO_LOGIN_NAME`; client không được gửi
`student_id`. API không trả lời giải tham chiếu, Judge0 token hoặc chi tiết test
ẩn.

## Các lệnh vận hành thường dùng

Xem container:

```bash
docker compose ps
```

Xem 100 dòng log gần nhất:

```bash
docker compose logs --tail=100 api worker db
```

Khởi động lại API/worker:

```bash
docker compose restart api worker
```

Dừng container nhưng giữ volume PostgreSQL:

```bash
docker compose --profile grading down
```

Xóa toàn bộ container **và dữ liệu PostgreSQL của dự án** để làm lại từ đầu:

```bash
docker compose --profile grading down -v
```

Lệnh `down -v` làm mất dữ liệu bài nộp/lịch sử trong volume và không thể hoàn
tác nếu chưa sao lưu.

## Xử lý lỗi thường gặp

### `Directory '/usr/local/.../app/static' does not exist`

Image cũ chưa chứa package-data. Build lại không dùng cache:

```bash
docker compose --profile test --profile grading build --no-cache
```

### Worker báo `judge0_language_id_not_configured`

Điền `JUDGE0_LANGUAGE_ID` trong `.env`, sau đó:

```bash
docker compose --profile grading up -d --force-recreate worker
```

### Submission đứng ở `queued`

Kiểm tra worker:

```bash
docker compose ps
docker compose logs --tail=100 worker
```

### Mã rất ngắn vẫn `time_limit_exceeded`

Kiểm tra `/config_info` của Judge0 và bảo đảm `.env` đang dùng giới hạn phù
hợp. Cấu hình đã smoke thành công là CPU 5 giây, wall time 10 giây và RAM
256000 KB. Sau khi sửa phải force-recreate worker.

### Không kết nối được Judge0

URL phải truy cập được từ **bên trong container**, không chỉ từ trình duyệt máy
host. Kiểm tra URL, DNS, firewall, proxy và credential của deployment Judge0.

### Cổng 5432 hoặc 8000 đã được dùng

Kiểm tra tiến trình/container đang giữ cổng:

```bash
docker ps
ss -ltnp | grep -E ':5432|:8000'
```

Đổi phần cổng bên trái trong `compose.yaml` nếu cần, ví dụ `8001:8000`.

## Cấu trúc thư mục

```text
alembic/              Migration PostgreSQL
app/api/              API bài tập và bài nộp
app/hint_context/     Hợp đồng dữ liệu cho phần gợi ý sau này
app/judging/          Judge0 client, harness, comparator và grading service
app/models/           SQLAlchemy models
app/problems/         Danh mục 20 bài và 160 test
app/templates/        Giao diện Jinja
app/static/           CSS và JavaScript
app/web/              Route giao diện
codexs/               Yêu cầu và báo cáo thiết kế
docs/                 Hướng dẫn, quyết định và kết quả kiểm chứng
scripts/              Script smoke test
tests/                Unit/integration/API/UI tests
```

## Đưa dự án lên GitHub

### 1. Kiểm tra dữ liệu trước khi commit

Repository đã khai báo ignore `.env`, virtualenv, cache, build output và các
thư mục công cụ cục bộ. Trước khi khởi tạo Git, kiểm tra quy tắc `.env` tồn tại:

```bash
cd /home/huong/do_an_chuyen_nganh
grep -n '^\.env$' .gitignore
```

Không dùng `git add -f .env`. Không commit token Judge0, mật khẩu thật, file
credential, private key hoặc dữ liệu sinh viên.

### 2. Khởi tạo Git

Trong bản workspace hiện tại, `.git` là thư mục rỗng chứ chưa phải repository.
Lệnh `rmdir` dưới đây chỉ xóa được khi thư mục thực sự rỗng, nên không xóa nhầm
lịch sử Git hợp lệ:

```bash
cd /home/huong/do_an_chuyen_nganh
rmdir .git 2>/dev/null || true
git init -b main
git check-ignore -v .env
```

Thiết lập danh tính commit nếu máy chưa có:

```bash
git config user.name "TEN_CUA_BAN"
git config user.email "EMAIL_GITHUB_CUA_BAN"
```

### 3. Kiểm tra và tạo commit đầu tiên

```bash
git add .
git status
git check-ignore -v .env
git diff --cached --stat
```

Đọc danh sách trong `git status` trước khi commit. `.env`, `.aws`, `.codex` và
`.agents` không được xuất hiện trong phần staged.

```bash
git commit -m "Initial Python practice PoC"
```

### 4A. Tạo và push bằng GitHub CLI

Đây là cách ngắn nhất nếu máy đã cài `gh`:

```bash
gh auth login
gh repo create do-an-chuyen-nganh \
  --private \
  --source=. \
  --remote=origin \
  --push
```

Đổi `--private` thành `--public` chỉ khi đã kiểm tra nội dung và muốn công khai
repository. GitHub CLI có thể đăng nhập qua trình duyệt và lưu credential Git.

### 4B. Tạo repository trên website và push bằng Git

1. Đăng nhập GitHub và chọn **New repository**.
2. Đặt tên, ví dụ `do-an-chuyen-nganh`.
3. Chọn `Private` hoặc `Public`.
4. Không tạo thêm README, `.gitignore` hoặc license vì dự án đã có các file đó.
5. Tạo repository rồi chạy:

```bash
git remote add origin https://github.com/USERNAME/do-an-chuyen-nganh.git
git push -u origin main
```

Thay `USERNAME` bằng tài khoản GitHub. GitHub không nhận mật khẩu tài khoản cho
Git qua HTTPS; dùng GitHub CLI/Git Credential Manager, personal access token,
hoặc SSH key. Không ghi token trực tiếp vào remote URL hay README.

Nếu muốn dùng SSH:

```bash
git remote set-url origin git@github.com:USERNAME/do-an-chuyen-nganh.git
git push -u origin main
```

Hướng dẫn chính thức: [đưa mã cục bộ lên GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
và [xác thực GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github).

### 5. Các lần cập nhật sau

```bash
git status
git add -A
git status
git commit -m "Mo ta thay doi"
git push
```

Có thể dùng `git add .` sau khi đã kiểm tra `.gitignore` và `git status`.

### 6. Chạy dự án sau khi clone từ GitHub

```bash
git clone https://github.com/USERNAME/do-an-chuyen-nganh.git
cd do-an-chuyen-nganh
cp .env.example .env
# Sửa JUDGE0_BASE_URL và JUDGE0_LANGUAGE_ID trong .env
docker compose --profile test --profile grading build
docker compose up -d db
docker compose run --rm test
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed
docker compose up -d api
docker compose --profile grading up -d worker
bash scripts/smoke_p01.sh
```

## Giới hạn của PoC

- Auth hiện là tài khoản demo, chưa phải đăng nhập production.
- Judge0 phải được vận hành riêng.
- Chưa có phục hồi tự động cho grading run bị kẹt lâu ở `running`.
- Chưa có AI, KM/KH, quota và cooldown gợi ý.
- Bộ test chứng minh bài nộp đạt các ca đã cấu hình, không chứng minh đúng với
  mọi đầu vào có thể có.
