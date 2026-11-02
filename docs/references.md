# Tài liệu & Liên kết Tham khảo của Dự án

Tài liệu này tổng hợp các bài báo khoa học, bộ dữ liệu chuẩn (benchmark datasets) và các hệ thống mã nguồn mở làm cơ sở lý thuyết và thực nghiệm cho đề tài **"Hệ thống chấm bài tập lập trình tự động có phản hồi bằng mô hình ngôn ngữ lớn"**.

---

## 1. Cơ sở lý thuyết về Phản hồi Sư phạm & AI trong Giáo dục Lập trình

### 1.1. Phân loại Phản hồi Tự động (Keuning et al., 2018)
* **Liên kết:** <https://dl.acm.org/doi/10.1145/3231711>
* **Trích dẫn chuẩn:**
  > Hieke Keuning, Johan Jeuring, and Bastiaan Heeren. 2018. *A Systematic Literature Review of Automated Feedback Generation for Programming Exercises*. ACM Transactions on Computing Education (TOCE), Vol. 19, No. 1, Article 3 (September 2018), 43 pages. DOI: `10.1145/3231711`.
* **Bản PDF trong workspace:** `Tổng quan Tài liệu Hệ thống về Phản hồi Tự độngTạo cho các bài tập lập trình.pdf`
* **Nội dung cốt lõi & Ứng dụng trong dự án:**
  * Phân loại các công cụ phản hồi bài tập lập trình theo khung lý thuyết của Narciss, trong đó hai nhóm phản hồi quan trọng nhất là:
    1. **KM (*Knowledge about Mistakes* — Kiến thức về lỗi):** Chỉ ra triệu chứng, loại lỗi, vị trí vùng mã nghi ngờ và nguyên nhân làm chương trình không vượt qua kiểm thử (không đưa mã sửa).
    2. **KH (*Knowledge about How to Proceed* — Kiến thức về cách tiếp tục):** Đưa ra câu hỏi dẫn dắt, gợi ý chiến lược, điều kiện biên hoặc hướng điều chỉnh thuật toán để sinh viên tự sửa bài (không đưa lời giải hoàn chỉnh).
  * **Ánh xạ vào code (`app/hints/prompts.py`, `app/hints/service.py`):**
    * Lượt yêu cầu gợi ý thành công thứ 1 (`used_count = 0`) kích hoạt System Prompt mức **KM**.
    * Lượt yêu cầu gợi ý thành công thứ 2 và 3 (`used_count in {1, 2}`) kích hoạt System Prompt mức **KH**.

---

### 1.2. Đánh giá LLM so với Gia sư Con người (Phung et al., 2023)
* **Liên kết:** <https://arxiv.org/abs/2306.17156>
* **Trích dẫn chuẩn:**
  > Tung Phung, Victor-Alexandru Pădurean, José Cambronero, Sumit Gulwani, Tobias Kohn, Rupak Majumdar, Adish Singla, and Gustavo Soares. 2023. *Generative AI for Programming Education: Benchmarking ChatGPT, GPT-4, and Human Tutors*. In Proceedings of the 2023 ACM Conference on International Computing Education Research (ICER '23) / arXiv:2306.17156.
* **Bản PDF trong workspace:** `Generative AI for Programming Education.pdf`
* **Nội dung cốt lõi & Ứng dụng trong dự án:**
  * Đánh giá thực nghiệm khả năng của GPT-4 so với gia sư con người trên các tác vụ giáo dục lập trình:
    * **Contextualized Explanation (Giải thích theo ngữ cảnh):** Khớp **84%**.
    * **Hint Generation (Sinh gợi ý sửa lỗi):** Khớp **66%**.
    * **Grading Feedback (Chấm điểm trực tiếp bằng LLM):** Chỉ đạt **16%**.
  * **Ánh xạ vào kiến trúc hệ thống (Chương 1 & Chương 2):**
    * Là cơ sở khoa học trực tiếp cho nguyên tắc thiết kế cốt lõi của đồ án: **Tuyệt đối không dùng LLM để tự quyết định bài nộp đúng hay sai.**
    * Tách bạch hoàn toàn **Khối thực thi kiểm thử (Judge0 + Harness)** làm nguồn chân lý định lượng và **Khối sinh phản hồi sư phạm (LLM Pipeline)** chỉ nhận ngữ cảnh lỗi đã xác minh (`HintContextV1`) để giải thích nguyên nhân (KM) và gợi ý hướng đi (KH).

---

## 2. Bộ Dữ liệu Bài tập & Thực nghiệm (Benchmark Datasets)

### 2.1. Google Research MBPP (Mostly Basic Programming Problems)
* **Liên kết HuggingFace:** <https://huggingface.co/datasets/google-research-datasets/mbpp>
* **Trích dẫn chuẩn:**
  > Jacob Austin et al. 2021. *Program Synthesis with Large Language Models*. arXiv:2108.07732.
* **Cấu trúc dữ liệu:**
  * Gồm các bài toán lập trình Python cấp độ nhập môn – cơ bản (`full` gồm 974 bài, tập `sanitized` đã rà soát thủ công gồm 427 bài).
  * Các trường chính: `task_id`, `text` (hoặc `prompt` trong bản sanitized), `code` (lời giải tham chiếu), `test_list` (danh sách các câu lệnh `assert` kiểm thử), `test_setup_code`, `challenge_test_list`.
* **Ứng dụng trong dự án (`app/problems/`, `app/benchmark/`):**
  * Định hình chuẩn bài tập hàm Python một điểm vào (`function_signature`) kèm bộ kiểm thử công khai/ẩn.
  * Phục vụ quy trình chạy **Benchmark ngoại tuyến (Mục 2.6)** với mô hình `Qwen2.5-Coder-7B-Instruct` trên Google Colab T4 để đo bộ chỉ số **M1–M5** và kiểm tra độ trùng lặp token (`Token Overlap`) với `reference_code`.

---

### 2.2. IBM Project CodeNet
* **Liên kết GitHub:** <https://github.com/IBM/Project_CodeNet>
* **Trích dẫn chuẩn:**
  > Ruchir Puri et al. 2021. *Project CodeNet: A Large-Scale AI for Code Dataset for Learning a Diversity of Coding Tasks*. NeurIPS 2021 Datasets and Benchmarks Track (arXiv:2105.12655).
* **Cấu trúc dữ liệu:**
  * Quy mô ~13,9 triệu bài nộp cho 4.053 bài toán trên 55 ngôn ngữ lập trình (trong đó có tập con lớn cho Python).
  * Kèm theo siêu dữ liệu thực thi: trạng thái chấm (`Accepted`, `Wrong Answer`, `Time Limit Exceeded`, `Runtime Error`, `Compile Error`), thời gian CPU, dung lượng bộ nhớ và mã nguồn thực tế của người học.
* **Ứng dụng trong dự án:**
  * Cung cấp mẫu các kiểu lỗi thực tế của người học lập trình Python (sai điều kiện biên, đặt `return` sớm trong vòng lặp, lỗi `IndexError`/`TypeError`, vòng lặp vô hạn) để thiết kế các `wrong_samples` có chủ đích và kịch bản kiểm thử độ phủ của hệ thống phản hồi.

---

## 3. Hệ thống Thực thi & Chấm bài Tự động Tham khảo

### 3.1. Judge0 — Hệ thống Thực thi Mã nguồn Mở trong Sandbox
* **Liên kết GitHub:** <https://github.com/judge0/judge0>
* **Nội dung cốt lõi & Ứng dụng trong dự án (`app/judging/judge0.py`, `app/judging/service.py`):**
  * Cung cấp HTTP API thực thi mã nguồn cô lập dựa trên Docker và `isolate` (Linux namespaces & cgroups).
  * Quy tắc tích hợp an toàn đã áp dụng trong dự án:
    * Gửi mã qua `POST /submissions?base64_encoded=true&wait=false`, nhận `token` và polling qua `GET /submissions/{token}?base64_encoded=true`.
    * Kiểm tra động `JUDGE0_LANGUAGE_ID` từ `/languages` và giới hạn tài nguyên (`cpu_time_limit`, `wall_time_limit`, `memory_limit`, `max_file_size`) từ `/config_info`.
    * Không suy diễn `status_id = 3 (Accepted)` của Judge0 là bài làm đúng: trạng thái Judge0 chỉ xác nhận tiến trình harness chạy xong, còn kết luận `passed` / `wrong_answer` / `syntax_error` / `runtime_error` được quyết định bởi lớp đối chiếu `HarnessReport` có gắn `nonce` chống giả mạo stdout.

---

### 3.2. Jupyter `nbgrader` — Hệ thống Giao và Chấm bài Tập Lập trình
* **Liên kết GitHub:** <https://github.com/jupyter/nbgrader>
* **Nội dung cốt lõi & Bài học thiết kế cho dự án (`app/judging/harness.py`, `app/api/serializers.py`, `app/hint_context/service.py`):**
  * `nbgrader` là công cụ chuẩn trong giáo dục Python để thiết kế bài tập theo mô hình **Autograder tests**:
    * Tách biệt rõ **Public Tests (Test công khai)** giúp sinh viên tự kiểm tra sơ bộ và **Hidden Tests (Test ẩn)** để đánh giá toàn diện tránh học vẹt/hard-code kết quả.
    * Kết hợp giữa điểm chấm tự động theo test case và phản hồi nhận xét (written feedback) cho sinh viên.
  * **Ánh xạ vào dự án:**
    * Mỗi bài tập trong hệ thống có 3 test công khai (`is_public = True`) và 5 test ẩn (`is_public = False`).
    * Serializer công khai (`app/api/serializers.py`) và bộ chọn bằng chứng (`app/hint_context/service.py`) tuyệt đối không tiết lộ `args`, `expected`, `actual` hay `stderr` của test ẩn cho cả phía trình duyệt sinh viên lẫn Prompt gửi sang LLM.

---

## 4. Bảng Tổng hợp Ánh xạ Tài liệu vào Các Chương Báo cáo & Mã nguồn

| Tài liệu / Nguồn | Vai trò trong Báo cáo (Chương 1, 2, 3) | Mô-đun Mã nguồn Liên quan |
| --- | --- | --- |
| **Keuning et al. (2018)** (`10.1145/3231711`) | Cơ sở lý thuyết phân cấp phản hồi **KM** (lượt 1) và **KH** (lượt 2–3), nguyên tắc *scaffolding* | `app/hints/prompts.py`, `app/hints/service.py` |
| **Phung et al. (2023)** (`arXiv:2306.17156`) | Lý do tách rời bộ chấm thực thi (Judge0) và bộ sinh gợi ý (LLM); tiêu chí đánh giá chất lượng | `app/judging/`, `app/hint_context/`, `app/hints/` |
| **Google MBPP** (`huggingface.co/.../mbpp`) | Chuẩn hóa bài toán hàm Python, bộ test và đánh giá thực nghiệm ngoại tuyến M1–M5 | `app/problems/catalog.py`, `app/benchmark/`, `scripts/run_benchmark_m1_m5.py` |
| **IBM Project CodeNet** (`IBM/Project_CodeNet`) | Phân loại trạng thái lỗi (`AC`, `WA`, `TLE`, `RE`, `CE`) và xây dựng mẫu bài nộp sai (`wrong_samples`) | `app/problems/`, `app/judging/service.py` |
| **Judge0** (`judge0/judge0`) | Kiến trúc sandbox thực thi cô lập, quản lý tài nguyên CPU/RAM, cơ chế polling token | `app/judging/judge0.py`, `scripts/poc_judge0_memory.py` |
| **Jupyter nbgrader** (`jupyter/nbgrader`) | Cơ chế kiểm thử theo hàm, phân tách Public/Hidden tests và bảo mật đáp án/test ẩn | `app/judging/harness.py`, `app/api/serializers.py`, `app/hint_context/service.py` |

