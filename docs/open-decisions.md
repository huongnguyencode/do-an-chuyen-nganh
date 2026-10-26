# Các quyết định còn mở

Các mục dưới đây chưa phải quyết định chính thức của nhóm. Mặc định PoC được
ghi riêng để có thể triển khai nhất quán và thay đổi có kiểm soát.

| Chủ đề | Mặc định PoC hiện tại | Trạng thái |
| --- | --- | --- |
| Định dạng bài | Một hàm, đối số và kết quả biểu diễn được bằng JSON | Chờ nhóm chốt |
| Nguồn 20 bài | Nhóm tự soạn, không gắn nhãn MBPP | Chờ nhóm chốt |
| Python runtime | Python 3.12 trong container | Chờ xác nhận Judge0 |
| Test công khai/ẩn | Đang dùng 3 công khai + 5 ẩn/bài; API không lộ chi tiết ẩn | Mặc định đã triển khai, chờ nhóm phê duyệt |
| Bằng chứng gợi ý | Tối đa K=2 test công khai sai, theo `test_index` | Mặc định đã triển khai, chờ nhóm phê duyệt |
| Chỉ sai test ẩn | Chỉ gửi `hidden_summary`, không có args/expected/actual/index | Mặc định đã triển khai, chờ nhóm phê duyệt |
| Xác thực | `DEMO_LOGIN_NAME` do backend xác định | Đã triển khai cho PoC; chưa phải auth thật |
| Worker | Tiến trình riêng lấy việc từ PostgreSQL bằng `SKIP LOCKED` | Đã dùng; phục hồi run treo chờ chốt |
| Judge0 | Polling token, không mặc định `wait=true` | Chờ URL/credential instance |
| Số thực | Chưa hỗ trợ cho tới khi có quy tắc sai số | Chờ nhóm chốt |
| Lưu lịch sử | Không xóa dữ liệu đã được chấm trong PoC | Chờ chính sách chính thức |
| AI/quota | Ngoài phạm vi Hưởng và Hải Anh | Phần của Bảo |
