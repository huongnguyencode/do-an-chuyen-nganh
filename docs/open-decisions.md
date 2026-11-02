# Các quyết định còn mở

Các mục dưới đây chưa phải quyết định chính thức cuối cùng của nhóm cho toàn bộ giai đoạn triển khai lớp thật. Mặc định PoC đã được triển khai nhất quán trong mã nguồn và cấu hình để có thể thay đổi có kiểm soát.

| Chủ đề | Mặc định PoC hiện tại | Trạng thái |
| --- | --- | --- |
| Định dạng bài | Một hàm Python thuần, đối số và kết quả biểu diễn được bằng JSON | Đã triển khai cho 20 bài; chờ nhóm xác nhận nếu mở rộng stdin/stdout |
| Nguồn 20 bài | 20 bài tự soạn (`P01`–`P20`), không gắn nhãn MBPP giả | Đã triển khai; có thể nhập thêm bài MBPP ở Chương 3 |
| Python runtime | Python 3.12 trong container | Đã kiểm chứng với Judge0 Python 3.12.5 |
| Test công khai/ẩn | 3 test công khai + 5 test ẩn/bài; API không lộ chi tiết ẩn | Đã triển khai và kiểm thử tự động |
| Bằng chứng gợi ý | Tối đa `K=2` test công khai sai (`HINT_MAX_EVIDENCE=2`), theo `test_index` | Đã triển khai; cấu hình được qua `.env` |
| Chỉ sai test ẩn | Mặc định từ chối sinh gợi ý theo test (`no_public_evidence_available`) và không trừ lượt; có cờ `HINT_ALLOW_HIDDEN_ONLY` | Đã triển khai theo Mục 2.2.3 & 2.3.5 Chương 2 |
| Xác thực | `DEMO_LOGIN_NAME` do backend xác định | Đã triển khai cho PoC; chưa phải auth đa người dùng production |
| Worker | Tiến trình riêng lấy việc từ PostgreSQL bằng `SKIP LOCKED` | Đã triển khai |
| Judge0 | Polling token, không mặc định `wait=true` | Đã triển khai |
| Chiến lược LLM lai | `LLM_MODE` hỗ trợ `api_demo` (`APIDemoAdapter`), `colab_qwen` (`ColabQwenAdapter`), `fake` (test) và `disabled` | Đã triển khai Adapter Pattern theo Mục 2.2.2 Chương 2 |
| Hạn mức & Cooldown | Tối đa 3 lượt thành công/sinh viên/bài (`KM` lượt 1, `KH` lượt 2–3), cooldown 120s, nộp lại không reset, lỗi AI/Guardrail không trừ lượt | Đã triển khai trong `help_quota`, `hint_request` và `HintOrchestrationService` |
| Output Guardrail | Regex Filter (Vận hành + Benchmark) + Token Overlap Filter (Benchmark), retry tối đa `N=2` lần (`HINT_MAX_RETRIES=2`) | Đã triển khai trong `app/hints/guardrail.py` |
