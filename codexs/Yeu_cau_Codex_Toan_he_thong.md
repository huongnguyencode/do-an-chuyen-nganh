# Yêu cầu triển khai toàn hệ thống luyện tập Python và gợi ý AI — Hưởng, Hải Anh, Bảo

> **Dành cho Codex trong VS Code.** Hãy đọc toàn bộ file này và kiểm tra repository hiện tại trước khi sửa mã. **Triển khai hoàn chỉnh PoC từ bài tập, kiểm thử, nộp mã, chấm bằng Judge0, lưu PostgreSQL, yêu cầu KM/KH, AI tạo/kiểm tra gợi ý, quota/cooldown đến xem lịch sử và demo.** Làm từng lát cắt để kiểm chứng nhưng không dừng ở `HintContextV1`; đây là yêu cầu làm **sản phẩm chạy được**, không phải chỉ viết bản thiết kế.

## 0. Bối cảnh và ranh giới

Sinh viên xem bài Python, nộp mã, ứng dụng gọi Judge0 qua API để thực thi, đánh giá từng ca kiểm thử và lưu kết quả trong PostgreSQL. Nếu lượt chấm hợp lệ có lỗi, sinh viên có thể **chủ động** yêu cầu gợi ý. Backend kiểm tra quyền, quota/cooldown, dựng `HintContextV1` đã lọc; dịch vụ của Bảo tạo và kiểm tra KM/KH; hệ thống chỉ trừ lượt khi gợi ý hợp lệ được lưu thành công. Gợi ý không làm thay đổi verdict chấm bài.

Quyết định đã chốt: backend FastAPI/Python; CSDL ứng dụng PostgreSQL riêng với CSDL nội bộ Judge0; Judge0 được gọi qua API. Mục tiêu dữ liệu: **20 bài tập Python**, mỗi bài có đề rõ ràng và nhiều test có đầu vào/kết quả mong đợi. Test không có nhãn “đúng/sai” cố định: nó chỉ `passed` hay `failed` đối với **một lượt nộp mã cụ thể**. Không phân tích độ phức tạp thời gian/không gian trong PoC này.

### 0.1. Mục tiêu sản phẩm và luồng sử dụng đầy đủ

Ứng dụng giúp sinh viên **tự luyện bài Python**: đọc yêu cầu, viết một hàm, nộp nhiều lần, thấy bằng chứng bài mình đạt/trượt test nào trong phạm vi được phép, rồi *nếu chủ động yêu cầu* mới nhận gợi ý theo mức. Hệ thống dạy hướng tìm lỗi, **không tự hiện lời giải hoặc mã hoàn chỉnh**. Phần chấm dựa vào test, nên “đạt tất cả test đã cấu hình” không phải chứng minh đúng với mọi đầu vào. **Toàn bộ đường chấm và đường gợi ý trong sơ đồ là phạm vi phải triển khai.**

```mermaid
flowchart TD
    A["Sinh viên: xem đề, nộp mã"] --> B["FastAPI: xác thực, lưu bài nộp"]
    B --> C["Dịch vụ chấm: lấy test, gọi Judge0"]
    C --> D["Judge0: thực thi mã Python"]
    D --> C
    C --> E["PostgreSQL ứng dụng: lưu kết quả từng test"]
    E --> F["Sinh viên: xem kết quả, lịch sử"]
    F --> G{"Chủ động yêu cầu gợi ý?"}
    G -- "Có" --> H["Kiểm tra quota, tạo ngữ cảnh lỗi"]
    H --> I["Bảo: AI tạo và kiểm tra KM/KH"]
    I --> E
```

| Thành phần | Làm gì | Không được nhầm với |
| --- | --- | --- |
| Ứng dụng FastAPI | Quy tắc nghiệp vụ, API, điều phối chấm, lọc dữ liệu, lịch sử | Môi trường thực thi mã không tin cậy |
| PostgreSQL **ứng dụng** | Bài, test, sinh viên, bài nộp, lượt chấm, kết quả, quota và gợi ý | CSDL nội bộ của Judge0 |
| Judge0 | Chạy mã trong sandbox, trả status và dữ liệu thực thi | Người tự hiểu đề, tự quyết định đúng/sai ở mức bài học hoặc tạo gợi ý |
| Dịch vụ gợi ý của Bảo | Tạo/kiểm tra KM hoặc KH từ ngữ cảnh đã lọc | Nguồn chân lý để sửa verdict chấm bài |

### 0.2. Từ điển nghiệp vụ: một dòng dữ liệu là gì?

| Thuật ngữ | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| Bài tập (`problem`) | Yêu cầu viết hàm và hợp đồng vào/ra | P01: `sum_numbers(numbers)` |
| Ca kiểm thử (`test_case`) | Đầu vào + kết quả **mong đợi** do người ra đề xác minh | `args=[[2,3,4]]`, `expected=9` |
| Bài nộp (`submission`) | Một snapshot mã nguồn do một sinh viên nộp cho một bài | Bản nộp số 17, có `return` đặt sai |
| Lượt chấm (`grading_run`) | Một lần hệ thống chạy một bài nộp trên một phiên bản test | Chấm bản 17 với bộ test version 1 |
| Kết quả test (`test_result`) | Kết quả **thực tế** của một test trong một lượt chấm | T1 thực tế `2` → `wrong_answer` |
| Bằng chứng lỗi (`HintContextV1`) | Bản tóm tắt **đã lọc** từ một lượt chấm sai hợp lệ | Đề + bản mã 17 + một test công khai trượt |
| Yêu cầu/gợi ý (`hint_request`) | Sinh viên chủ động yêu cầu; lưu trạng thái và nội dung nếu thành công | KM chỉ hướng tìm lỗi, KH định hướng sửa |

Một test không “sai” sẵn trong PostgreSQL. Với cùng `test_case`, mã sinh viên A có thể `passed` và mã sinh viên B có thể `wrong_answer`. Lưu `test_result` gắn với **cả** lượt chấm và test tương ứng; không ghi đè kết quả cũ khi nộp lại.

### 0.3. Sáu hành vi người dùng để kiểm tra tính đầy đủ

| Use Case | Người dùng nhìn thấy | Dữ liệu/đường xử lý cần có |
| --- | --- | --- |
| UC01 Xem danh sách bài | Danh sách bài đang công bố | `problem`, không lộ test ẩn |
| UC02 Xem chi tiết bài | Đề, chữ ký hàm, ví dụ công khai | `problem` + test công khai |
| UC03 Nộp mã Python | Mã được nhận, có ID và trạng thái chấm | `submission` → `grading_run` → Judge0 |
| UC04 Xem kết quả chấm | Tổng test, trạng thái, lỗi cho phép hiện | `test_result` qua serializer sinh viên |
| UC05 Yêu cầu KM/KH | Nút yêu cầu, trạng thái xử lý, gợi ý đã lưu, lỗi có thể thử lại | Điều kiện quota/cooldown + `HintContextV1` + Bảo + lưu gợi ý |
| UC06 Xem lịch sử | Các bài đã nộp, kết quả cũ, gợi ý cũ | Lịch sử `submission`/`grading_run`/`hint_request`, không bị mất khi nộp lại |

**Phải làm đủ UC01–UC06**, gồm xem lại gợi ý cũ không trừ lượt. Nếu chưa có cấu hình AI thật thì báo rõ phần nào chưa chạy trong môi trường hiện tại; test bằng fake provider để kiểm thử luồng, nhưng không gọi phản hồi mock là gợi ý AI thực tế trong demo.

### 0.4. Trình tự chính xác của một lượt nộp

1. Sinh viên gửi `problem_id` và mã Python. FastAPI xác định `student_id` từ auth hoặc chế độ demo được cấu hình; kiểm tra bài tồn tại/được công bố và có test hợp lệ.
2. Lưu `submission` chứa **nguyên mã tại thời điểm nộp**, tạo `grading_run` với version/snapshot test và trạng thái `queued`.
3. Dịch vụ chấm lấy test của đúng version, lần lượt đưa mã/harness/đầu vào vào Judge0. Lưu token, polling và kiểm tra status, stdout/stderr, compile_output/message; không giữ giao dịch/khóa PostgreSQL suốt thời gian chờ dịch vụ ngoài.
4. Với từng test, so sánh giá trị trả về đã chuẩn hóa với expected; lưu `test_result`. Nếu lỗi cú pháp/runtime/timeout, phân loại là lỗi mã sinh viên; nếu Judge0/network/runner lỗi, phân loại là lỗi kỹ thuật.
5. Chỉ kết luận đạt toàn bài khi có **ít nhất một test**, tất cả test bắt buộc có kết quả hợp lệ và đều `passed`. Trả trạng thái chấm cho sinh viên; che mọi chi tiết test ẩn ở **API**, không chỉ che trên giao diện.
6. Giữ lịch sử lượt nộp/lượt chấm. Nếu chấm sai hợp lệ, cho phép **nút yêu cầu gợi ý**; chỉ sau thao tác đó mới dựng `HintContextV1`, gọi phần của Bảo và xử lý quota như mục 0.5. Nộp bài không tự gọi AI.

Ví dụ P01: T1 `[2,3,4] → 9`, T2 `[] → 0`. Sinh viên nộp hàm `return` ngay trong vòng lặp: T1 có thể trả `2`, T2 có thể trả `None`. Hai hàng `test_result` này giải thích **mã đó** sai thế nào; chúng không biến T1/T2 thành “test sai” cố định.

Trạng thái lượt chấm cần có chuyển tiếp kiểm tra được: `queued → running → completed` khi chấm tin cậy, hoặc `queued/running → technical_error` khi dịch vụ/harness không cho phép kết luận. Mã sinh viên sai kết quả, lỗi cú pháp, lỗi runtime hay quá thời gian **vẫn là một kết quả chấm hợp lệ** nếu phân loại tin cậy; dùng `test_result.status`/verdict để mô tả lỗi, không biến mọi mã sai thành `technical_error`. Khi API được gọi lại hoặc worker chạy lại, cập nhật idempotent theo `grading_run_id` và không tạo trùng các hàng test; yêu cầu đến muộn không ghi đè kết quả cuối đã xác nhận.

Phân tách mô-đun theo trách nhiệm: `problems` (đề/seed), `submissions` (bài nộp/lịch sử), `judging` (Judge0 client + harness + verdict), `persistence` (models/migrations), `presentation` (API/giao diện và lọc test ẩn), `hint_context` (dữ liệu đã lọc), `hint_policy` (quota, cooldown, trạng thái yêu cầu), `hint_generation` (provider + prompt + checker). Đây là **gợi ý về ranh giới**, không buộc đặt chính xác tên thư mục đó nếu repo đã có cấu trúc phù hợp. Các dependency đi từ API → service → repository/client; API không tự ghép prompt AI hay trực tiếp đọc CSDL nội bộ Judge0.

### 0.5. Luồng gợi ý cần triển khai đầy đủ

Sinh viên bấm **Yêu cầu gợi ý** trên một `submission_id`/`grading_run_id` cụ thể. Backend phải xác minh đúng chủ bài, lượt chấm đã hoàn tất hợp lệ, bài không đạt toàn bộ test; tra quota theo **`(student_id, problem_id)`**, không theo từng submission. Nếu hết 3 lượt thành công, chưa hết 120 giây từ gợi ý đã lưu gần nhất, hoặc cặp sinh viên–bài đang có yêu cầu gợi ý xử lý, thì từ chối với lý do rõ ràng. Nếu đủ điều kiện, xác định mức KM ở lượt thành công thứ 1, KH ở lượt thành công thứ 2–3; chọn bằng chứng lỗi cho phép rồi chuyển context đến Bảo. Bảo tạo và kiểm tra nội dung; **chỉ khi nội dung hợp lệ được lưu thành công** mới tăng quota và đặt mốc cooldown. AI/checker thất bại không trừ lượt; xem lại nội dung đã lưu không trừ lượt; nộp bài mới không reset quota/cooldown. Phải xử lý yêu cầu đồng thời và yêu cầu bị treo.

| Trường hợp | Kết quả nghiệp vụ phải triển khai |
| --- | --- |
| Bài sai, còn quota, hết cooldown, không có yêu cầu đang chạy | Cho phép yêu cầu KM/KH theo số **gợi ý thành công trước đó** |
| Nộp lại bài sau một gợi ý thành công | Vẫn đã dùng 1/3; gợi ý thành công tiếp theo là KH; cooldown vẫn tính từ gợi ý trước |
| Bài vượt qua tất cả test | Không cấp gợi ý **sửa lỗi** trong PoC |
| Lỗi Judge0/API hoặc kết quả chấm không tin cậy | Báo lỗi kỹ thuật; không suy diễn mã sai để tạo gợi ý |
| AI/bộ kiểm tra gợi ý thất bại | Không lưu gợi ý thành công, không trừ quota |

Tạo bảng quota và `hint_request` **có sử dụng thật**, migration và test cho trạng thái xử lý, thành công, thất bại, hết hạn. `HintContextV1` là dữ liệu nội bộ cho Bảo; lịch sử gợi ý lấy từ nội dung **đã lưu thành công**, không suy từ context. Không giữ khóa DB trong lúc chờ AI.

### Tài liệu GitHub đã đối chiếu với mã nguồn (24/10/2026)

| Nguồn và vị trí nên đọc | Bài học đưa vào PoC | Không sao chép nguyên |
| --- | --- | --- |
| [AI_Tutor](https://github.com/sheheenmtp/AI_Tutor), nhất là [`backend/app.py`](https://github.com/sheheenmtp/AI_Tutor/blob/main/backend/app.py), [`backend/models.py`](https://github.com/sheheenmtp/AI_Tutor/blob/main/backend/models.py), [`backend/seed_data.py`](https://github.com/sheheenmtp/AI_Tutor/blob/main/backend/seed_data.py) (đối chiếu commit `7902776`) | Có luồng xem bài, `validate`, `submit`, test công khai/ẩn, PostgreSQL và Judge0; hữu ích để hình dung bản chạy đầu tiên | `execute_test_cases` gửi `wait=true`, so sánh `stdout.strip()` với expected, gộp exception thành test trượt, và có thể coi **0 test là đạt hết** (`0 == 0`); chi tiết test được trả trong kết quả. Hãy thiết kế trạng thái riêng cho lỗi hạ tầng, từ chối bài không có test và lọc test ẩn trước khi xuất API. README nói chưa có bộ test tự động chuyên biệt. |
| [Online-Judge-platform](https://github.com/everlastingQAQ/Online-Judge-platform), đặc biệt [`judge0_service.py`](https://github.com/everlastingQAQ/Online-Judge-platform/blob/master/backend/app/services/judge0_service.py), [`submission_service.py`](https://github.com/everlastingQAQ/Online-Judge-platform/blob/master/backend/app/services/submission_service.py), [`test_judge0_service.py`](https://github.com/everlastingQAQ/Online-Judge-platform/blob/master/backend/tests/test_judge0_service.py) (commit `1636836`) | Tham khảo tách service/worker, lưu kết quả từng test, kiểm tra ngôn ngữ thực tế của Judge0, polling token và test mock; dự án có cách chạy multi-file trong một lượt Judge0 | PoC chưa cần Redis/thi đấu/multi-language. [`test_case.py`](https://github.com/everlastingQAQ/Online-Judge-platform/blob/master/backend/app/models/test_case.py) dùng `is_sample` nhưng không có cờ `is_hidden` tường minh; [`submissions.py`](https://github.com/everlastingQAQ/Online-Judge-platform/blob/master/backend/app/api/endpoints/submissions.py) dựng chi tiết trả cả input/expected test. Cần chính sách ẩn test và serializer riêng cho sinh viên. |
| [Moodle CodeRunner](https://github.com/trampgeek/moodle-qtype_coderunner), [`authorguide.md`](https://github.com/trampgeek/moodle-qtype_coderunner/blob/master/authorguide.md) (commit `0c70d01`) | Tham khảo mẫu “viết hàm → gọi từ test”, test ví dụ, test ẩn và kiểm tra lời giải lúc biên soạn đề | Đây là plugin Moodle/PHP, không phải backend của dự án; chỉ học quy ước soạn đề và cách phân biệt bài thử với bài nộp. |
| [Google Research MBPP](https://github.com/google-research/google-research/tree/master/mbpp), [`README`](https://github.com/google-research/google-research/blob/master/mbpp/README.md) và [`sanitized-mbpp.json`](https://github.com/google-research/google-research/blob/master/mbpp/sanitized-mbpp.json) (commit `8bedbbd`) | Gợi ý nội dung bài Python, lời giải và test để Hưởng chọn, rà, diễn đạt lại và bổ sung ca biên | `sanitized-mbpp.json` là **một mảng JSON 427 mục** với `task_id`, `prompt`, `code`, `test_list`; `mbpp.jsonl` là **974 dòng JSONL** và dùng khóa `text`. Các test nguồn là câu lệnh `assert` Python, không phải sẵn JSON input/expected: không dùng `eval`/`exec` trên dữ liệu nhập hay tự động chuyển tất cả 20 bài. Một số hàm trả `tuple`, `set` hoặc phụ thuộc import, không hợp ngay với hợp đồng JSON PoC. |
| [Judge0](https://github.com/judge0/judge0), [`create_a_submission.md`](https://github.com/judge0/judge0/blob/master/docs/api/submissions/create_a_submission.md), [`get_a_submission.md`](https://github.com/judge0/judge0/blob/master/docs/api/submissions/get_a_submission.md) (commit `4f630ff`) | Dùng token để thăm dò trạng thái, kiểm tra status, stdout/stderr/compile_output/message và giới hạn chạy; thiết lập base64 khi cần theo API/deployment | Tài liệu ghi `wait=true` có thể không được bật và không khuyến nghị dùng làm mặc định; status Judge0 là trạng thái thực thi, không thay cho kết luận đúng/sai của ứng dụng. Không hard-code `language_id` lấy từ một instance khác. |

Các nhận xét trên dựa vào các commit nêu trong bảng; nếu repository đổi, Codex cần đối chiếu phiên bản hiện tại và ghi rõ thay đổi. Tham khảo **ý tưởng và kiểm thử**, không copy mã của dự án khác vào sản phẩm mà không kiểm tra license và tính đúng đắn.

Chính sách gợi ý **đã được nhóm xác nhận và phải triển khai**: tối đa 3 gợi ý *lưu thành công*/sinh viên/bài; lần 1 KM, lần 2–3 KH; 120 giây từ khi lưu gợi ý; nộp lại không reset; lỗi AI/checker và xem lại không trừ; tối đa một yêu cầu đang xử lý cho mỗi sinh viên/bài; bài vượt qua tất cả test không có gợi ý sửa lỗi; lỗi hạ tầng chấm bài không được coi là lỗi sinh viên. Khóa quota theo `(student_id, problem_id)`, **không** theo `submission_id`.

## 1. Phân công ba người và sản phẩm bàn giao

| Người phụ trách | Phần cần làm | Tiêu chí bàn giao |
| --- | --- | --- |
| **Hưởng — nội dung, dữ liệu, nghiệp vụ, nghiệm thu** | Chuẩn bài tập, viết 20 bài và bộ test; định nghĩa quy tắc vào/ra; mã đúng tham chiếu và các mã sai mẫu nội bộ; rà ERD/schema; lập ma trận ca nghiệm thu; kiểm tra dữ liệu chấm và `HintContext` bằng các lỗi có chủ đích | Có seed dữ liệu, mô tả từng bài, test công khai/ẩn, tập bài nộp mẫu và báo cáo nghiệm thu theo bài; không có test mâu thuẫn đề hoặc đáp án mong đợi |
| **Hải Anh — thực thi và chấm** | API nộp bài/xem kết quả; điều phối Judge0; harness gọi hàm sinh viên; phân biệt lỗi mã/lỗi hạ tầng; lưu `submission`, `grading_run`, `test_result`; chuẩn hóa kết quả; xây bộ chọn bằng chứng và `HintContext`; log và kiểm thử tích hợp | Một bài đúng và một bài sai chạy end-to-end; 20 bài seed đều được thử; dữ liệu kết quả truy xuất được từ PostgreSQL; không đánh dấu đạt nếu chạy thiếu test |
| **Bảo — gợi ý AI và chất lượng nội dung** | Thiết kế provider/prompt KM–KH; sinh nội dung từ `HintContextV1`; bộ kiểm tra đúng căn cứ, đúng mức và không lộ lời giải; xử lý timeout/lỗi; phối hợp tích hợp quota/cooldown và lịch sử gợi ý | Có yêu cầu KM đầu tiên, KH ở lượt thành công 2–3; gợi ý được kiểm tra trước khi lưu; lỗi không trừ quota; có log/rubric đánh giá thực tế |
| **Tích hợp chung** | Ghép ba phần qua FastAPI/PostgreSQL và giao diện; phối hợp quyền truy cập, quota, trạng thái, lỗi; kiểm thử xuyên suốt | Demo: chọn bài → nộp Python → xem đúng/sai → bấm gợi ý → lưu KM/KH → xem lại; nộp lại không reset quota/cooldown |

Phân công trong bảng là **đầu mối trách nhiệm**. Chủ sở hữu cuối cùng của toàn bộ frontend, migrations, module quota và tích hợp API chưa được nhóm xác nhận; Codex phải triển khai phần mã cần thiết để **toàn bộ luồng chạy được**, ghi lại ai sẽ nhận bàn giao từng module, không bỏ trống phần chung. Không gán toàn bộ AI cho Hưởng/Hải Anh hoặc toàn bộ ứng dụng cho Bảo.

## 2. Cách Codex bắt đầu

1. Xem cấu trúc repository, README, quy ước sẵn có, môi trường chạy và các bài tập đã có. Giữ phần hiện hữu; không tạo một dự án thứ hai nếu repo đã có ứng dụng. Nếu chưa có repo ứng dụng, tạo cấu trúc tối thiểu cho FastAPI, PostgreSQL, migrations, seed, tests, giao diện và một AI provider cấu hình được.
2. Kiểm tra endpoint/kiểu phản hồi Judge0 của **instance thực tế** được cấu hình. Đọc tài liệu chính thức, không hard-code language ID lấy từ README dự án khác; ánh xạ các status ID theo tài liệu và xác minh với instance. Tạo submission nhận token rồi polling với backoff/timeout tổng; chỉ dùng `wait=true` nếu instance xác nhận hỗ trợ và nhóm có lý do rõ. Ghi nhận HTTP 400/422/429/503, lỗi mạng và giới hạn output như những nhánh cần xử lý.
3. Làm **một bài đầu tiên chạy trọn luồng cả chấm và gợi ý**, sau đó 1 bài biên có kiểu dữ liệu khác. Kiểm tra quota/cooldown và lỗi AI trên dữ liệu nhỏ trước khi mở rộng thành 20 bài.
4. Ghi lại các giả định chưa được nhóm chốt trong `docs/open-decisions.md`; chọn mặc định hợp lý cho PoC và ghi rõ rằng đó là mặc định triển khai, không phải quyết định nhóm đã xác nhận.

## 3. Quy ước PoC cho bài Python

Đề xuất mặc định: sinh viên chỉ viết **một hàm thuần Python** có tên/chữ ký nêu trong đề, chẳng hạn `def sum_numbers(numbers): ...`. Test truyền các đối số kiểu JSON và so sánh giá trị trả về kiểu JSON. Không dùng `input()`/`print()` làm hợp đồng trả lời của bài, không yêu cầu cài thư viện ngoài. Nếu repo đã có một quy ước khác ổn định, ghi nhận và thống nhất dữ liệu theo quy ước đó; không trộn nhiều kiểu chấm tùy tiện.

Mỗi bài có `slug`, tiêu đề, mô tả tiếng Việt, tên hàm, chữ ký, kiểu/thí dụ vào-ra, ràng buộc, tối thiểu một ví dụ công khai, thứ tự test, cờ test công khai/ẩn và phiên bản bài/test. Đề và test cần nhất quán với các trường hợp rỗng, âm, trùng lặp, phân biệt chữ hoa/thường, thứ tự phần tử, giới hạn đầu vào nếu có. Đầu ra số thực chỉ được dùng khi có quy tắc sai số tường minh; còn lại so sánh kiểu dữ liệu và giá trị đúng, không so sánh `str()` của đối tượng.

Định dạng seed đề xuất, **dữ liệu minh họa chứ chưa phải bài đã soạn xong**:

```json
{
  "slug": "p01-sum-numbers",
  "version": 1,
  "title": "Tính tổng danh sách",
  "function_name": "sum_numbers",
  "function_signature": "sum_numbers(numbers)",
  "statement": "Viết hàm trả về tổng các số nguyên trong danh sách; danh sách rỗng trả về 0.",
  "tests": [
    {"test_index": 1, "args": [[2, 3, 4]], "expected": 9, "is_public": true, "purpose": "Thông thường"},
    {"test_index": 2, "args": [[]], "expected": 0, "is_public": false, "purpose": "Danh sách rỗng"}
  ]
}
```

Với hàm nhiều tham số, `args` là mảng các đối số theo đúng thứ tự; nếu cần keyword arguments, thiết kế `kwargs` có kiểm tra kiểu. `expected` là oracle được Hưởng kiểm tra độc lập. Không nhầm `is_public=false` với “test sai”.

### Danh sách 20 bài để Hưởng soạn thành dữ liệu thật

Danh sách này là **đề xuất nội dung PoC**, không phải bộ test hoàn chỉnh. Hãy viết đầy đủ đề, chữ ký, hàm tham chiếu, test và mã sai mẫu cho từng bài. Giữ độ khó nhập môn đến trung bình, ưu tiên các lỗi có thể giải thích bằng KM/KH về sau.

| Mã | Tên bài | Chữ ký đề xuất | Test đáng chú ý |
| --- | --- | --- | --- |
| P01 | Tính tổng danh sách | `sum_numbers(numbers)` | Rỗng, một phần tử, số âm |
| P02 | Đếm số chẵn | `count_even(numbers)` | 0, âm chẵn, toàn số lẻ |
| P03 | Tìm giá trị lớn nhất | `find_max(numbers)` | Âm, trùng max; quy định rõ rỗng |
| P04 | Đảo ngược chuỗi | `reverse_text(text)` | Rỗng, Unicode, ký tự lặp |
| P05 | Kiểm tra đối xứng | `is_palindrome(text)` | Lẻ/chẵn, rỗng; quy định rõ hoa-thường |
| P06 | Giai thừa | `factorial(n)` | 0, 1, n vừa phải; miền n không âm |
| P07 | Fibonacci thứ n | `fibonacci(n)` | 0, 1 và vài n nhỏ; n không âm |
| P08 | Kiểm tra số nguyên tố | `is_prime(n)` | n<2, 2, số chính phương, hợp số |
| P09 | Ước chung lớn nhất | `gcd(a, b)` | Cùng số, hoán đổi, số 0; quy định miền âm |
| P10 | Xóa trùng giữ thứ tự | `unique_in_order(items)` | Rỗng, lặp liên tiếp/rải rác |
| P11 | Phần tử lớn thứ hai phân biệt | `second_largest(numbers)` | Trùng max, không đủ hai giá trị; quy định sentinel |
| P12 | Gộp hai danh sách đã sắp | `merge_sorted(left, right)` | Một bên rỗng, trùng, số âm |
| P13 | Tìm vị trí đầu tiên | `first_index(items, target)` | Không thấy, trùng, đầu/cuối |
| P14 | Đếm tần suất ký tự | `char_counts(text)` | Rỗng, dấu cách, Unicode; quy tắc hoa-thường |
| P15 | Tổng các chữ số | `digit_sum(n)` | 0, nhiều chữ số; quy định n âm |
| P16 | Chuẩn hóa khoảng trắng | `normalize_spaces(text)` | Đầu/cuối, nhiều khoảng trắng, rỗng |
| P17 | Giao hai danh sách không trùng | `intersection(left, right)` | Trùng và thứ tự kết quả phải được quy định |
| P18 | Tính tổng đường chéo ma trận vuông | `diagonal_sum(matrix)` | Ma trận 1×1, nhiều hàng, số âm |
| P19 | Đếm từ trong câu | `word_count(text)` | Rỗng, nhiều khoảng trắng; quy tắc tách từ |
| P20 | Kiểm tra ngoặc cân bằng | `balanced_brackets(text)` | Lồng nhau, sai thứ tự, ký tự khác ngoặc |

Mỗi bài nên có khoảng **8 ca kiểm thử hoặc hơn nếu cần**, phủ thông thường, biên và lỗi thường gặp; đây là mục tiêu triển khai đề xuất. Đừng tạo 160 bản ghi một cách máy móc: mỗi ca phải có lý do và kết quả mong đợi xác minh độc lập. Viết ít nhất 2–3 bài nộp sai mẫu có *dự kiến test nào trượt* cho một số bài tiêu biểu; với cả 20 bài, tối thiểu có một lời giải đúng tham chiếu và một mã sai mẫu để kiểm tra pipeline.

Lưu seed bài/test trong file có version, nạp lặp lại không sinh bản ghi trùng. Chạy lời giải tham chiếu với test và tự kiểm tra tính nhất quán; không lấy giá trị mong đợi bằng cách chạy chính mã sinh viên. Không hiển thị lời giải tham chiếu hoặc test ẩn qua API công khai.

**Nếu sử dụng MBPP:** Hưởng ghi `source_name=MBPP`, `source_task_id`, đường dẫn nguồn và cách chỉnh sửa cho từng bài được chọn. Lọc thủ công những bài đúng phạm vi “một hàm, đối số/giá trị JSON”; rà các `assert` nguồn (có khi dùng `set(...)` để so sánh, có khi cần `test_imports`) rồi biên soạn lại thành test JSON theo hợp đồng của nhóm. Không đưa nguyên lời giải `code` vào prompt hoặc API sinh viên. Kiểm tra quyền sử dụng/ghi công theo license hiện hành trước khi công bố bộ đề chuyển thể. Nếu các P01–P20 được nhóm tự biên soạn thay vì chọn MBPP, ghi rõ là bài tự soạn; **không gắn nguồn MBPP khi không thực sự dùng**.

## 4. Luồng chấm do Hải Anh triển khai

```text
problem + test_case → submission → grading_run
                       → Judge0 API → normalized test_result[]
                       → persisted result + student-facing result
                       → eligible HintContext for future integration
```

Thiết kế harness đủ rõ để biết test nào thực sự được chạy. Mặc định PoC: **mỗi ca test là một tác vụ Judge0**, thu kết quả trả về của hàm bằng runner do server tạo; sau đó ứng dụng so sánh với `expected` được lưu riêng. Không gửi `expected` vào mã sinh viên khi có thể tránh. Có thể dùng chế độ multi-file/một submission cho cả bài **chỉ khi** môi trường Judge0 có hỗ trợ, cách cô lập test được kiểm chứng và parser xác minh đủ test. **Ưu tiên đúng và truy vết được trước khi tối ưu số lần gọi.** Harness cần bắt ngoại lệ mã sinh viên một cách hợp lý, phân biệt timeout/lỗi cú pháp/lỗi chạy, tách phần sinh viên in ra khỏi kết quả hàm và không tin JSON/marker do chính sinh viên `print()` để tuyên bố test đạt. Mã sinh viên có thể gọi `sys.exit()` hoặc in kết quả giả: khi không thu được đủ bằng chứng hợp lệ, kết luận lượt chấm chưa hợp lệ/không hoàn tất, tuyệt đối không `all_passed=true`. Không tuyên bố PoC chống được mọi mã độc; Judge0 cô lập quá trình, còn giao thức kết quả của harness vẫn phải được thử với mã đối kháng.

Judge0 thực thi mã, còn ứng dụng phải giữ mapping `test_case_id`/thứ tự test, diễn giải trạng thái, kiểm tra phản hồi và so sánh kết quả theo contract. **Không suy ra `passed` chỉ từ `status=Accepted` của Judge0**: trạng thái đó xác nhận tác vụ thực thi theo hợp đồng Judge0; phép so sánh hàm Python và test của nhóm là lớp riêng. Phân biệt rõ:

| Trạng thái chuẩn hóa | Ý nghĩa |
| --- | --- |
| `passed` | Đã chạy, đầu ra đúng theo quy tắc so sánh |
| `wrong_answer` | Đã chạy, khác đầu ra mong đợi |
| `syntax_error`/`runtime_error` | Mã sinh viên lỗi, lưu thông tin an toàn |
| `time_limit_exceeded` | Mã vượt giới hạn chạy |
| `infrastructure_error` | Judge0/API/network/phản hồi hỏng; không đổ lỗi cho sinh viên |
| `incomplete` | Không có kết quả tin cậy cho toàn bộ test; không coi là đạt hết |

`grading_run.status` cần tối thiểu `queued`, `running`, `completed`, `technical_error`. Từ chối xuất bản bài có **0 test hợp lệ**. `completed` chỉ khi đã kiểm tra đủ số test dự kiến hoặc có chính sách chấm dừng sớm được định nghĩa rõ; `all_passed=true` chỉ khi **tổng test > 0**, mọi test bắt buộc đã chạy và đều `passed`. Với lỗi cú pháp/runtime/timeout do mã sinh viên, cần trạng thái *đã chấm có lỗi mã* và bằng chứng phù hợp; với lỗi Judge0/API/network/runner, cần trạng thái *lỗi kỹ thuật*. Không gộp hai loại thành `wrong_answer`. Nếu có lỗi kỹ thuật, API trả trạng thái riêng để người dùng thử lại; không tạo `HintContext` lỗi thuật toán từ lần đó. Lưu ID/token Judge0 để đối chiếu log, không đưa khóa API vào log.

## 5. PostgreSQL, API và giao diện toàn hệ thống

Tạo migrations và ràng buộc khóa ngoại/check/unique phù hợp; tránh chỉ lưu toàn bộ phản hồi Judge0 vào một cột JSON rồi bỏ qua mô hình quan hệ. Tên bảng gợi ý:

| Bảng | Cột cốt lõi |
| --- | --- |
| `student` | id, định danh đăng nhập hoặc mã giả lập cho PoC |
| `problem` | id, slug unique, title, statement, function_signature, version, trạng thái xuất bản |
| `test_case` | id, problem_id, test_index, arguments_json, expected_json, is_public, test_version; unique `(problem_id, test_version, test_index)` |
| `submission` | id, student_id, problem_id, source_code, submitted_at |
| `grading_run` | id, submission_id, status, all_passed, expected_test_count, started_at, finished_at, technical_error_code |
| `test_result` | id, grading_run_id, test_case_id, status, actual_json, error_summary, judge0_token; unique `(grading_run_id, test_case_id)` |
| `help_quota` | `(student_id, problem_id)` khóa chính ghép, successful_count 0–3, last_success_at UTC; FK tới student/problem |
| `hint_request` | id, student_id, problem_id, submission_id, grading_run_id, requested_level, status, content, failure_code, lease_token, created_at, saved_at, idempotency_key; FK và ràng buộc trạng thái |

Tên trường có thể khác để phù hợp repo, nhưng quan hệ và ý nghĩa phải giữ. `submission` giữ nguyên mã tại thời điểm nộp; mỗi kết quả gắn với đúng version test. Nếu cho phép sửa đề/test, giữ snapshot hoặc version đủ để giải thích một kết quả cũ; không join lượt chấm cũ với test đã bị thay nội dung. `hint_request` tham chiếu **đúng** `submission_id` và `grading_run_id` của nó; thêm kiểm tra tại service/DB để không ghép một run thuộc submission khác. Nộp lại không xóa/reset quota `(student_id, problem_id)`. PostgreSQL ứng dụng tuyệt đối không dùng các bảng nội bộ của Judge0.

API tối thiểu (tên đường dẫn có thể theo repo): đăng ký/đăng nhập hoặc cơ chế nhận dạng có sẵn; `GET /problems`, `GET /problems/{id}`, `POST /submissions`, `GET /submissions/{id}`, `GET /submissions` (lịch sử của người dùng), `POST /submissions/{id}/hints` (truyền hoặc xác định run cụ thể, hỗ trợ idempotency key), `GET /hint-requests/{id}` (trạng thái/xem nội dung nếu thành công), `GET /problems/{id}/hints` (lịch sử gợi ý/quota của người dùng). `HintContext` chỉ qua **service nội bộ được bảo vệ**, không trả toàn bộ ở API sinh viên. **Phải có ít nhất hai tài khoản sinh viên riêng biệt và một vai trò quản trị/nạp đề**, dùng auth hiện có hoặc cơ chế đăng nhập tối thiểu với mật khẩu băm/session-token bảo vệ. Không tin `student_id` trong body để xác thực; mọi lịch sử/quota lấy từ danh tính đã xác thực. Demo ID cố định chỉ được bật ở chế độ phát triển riêng, không coi là hoàn thành tính năng đa sinh viên. Dùng OpenAPI do FastAPI sinh và thêm ví dụ request/response thành công/lỗi vào README.

Quản trị bài: Hưởng cần đường nạp/kiểm tra/đăng bài phù hợp repo, tối thiểu seed CLI có kiểm tra schema và idempotency; nếu giao diện quản trị được làm, phân quyền admin cho tạo/sửa đề/test và ẩn lời giải. Không cho sinh viên gọi API thay đổi test hoặc xem lời giải tham chiếu. Thay test sau khi đã có bài nộp phải tạo version/snapshot mới để lịch sử còn giải thích được; không xóa cascade bài nộp của sinh viên khi sửa đề.

Giao diện tối thiểu, theo stack hiện có hoặc HTML template nếu repo mới: danh sách 20 bài, chi tiết một bài, ô nhập mã Python, nút Nộp, trạng thái đang chấm, số test đạt/tổng số, thông tin lỗi được phép hiện, nút **Yêu cầu gợi ý** chỉ khi điều kiện hợp lệ, số lượt còn lại, đồng hồ cooldown, trạng thái đang sinh, KM/KH đã lưu, lịch sử bài nộp và lịch sử gợi ý. Không tạo nút AI giả nếu provider thực sự không được cấu hình; hiển thị lỗi dịch vụ rõ ràng và không trừ lượt. Nếu có test ẩn, **serializer API công khai** không trả input/expected/actual, stdout/stderr nguyên dạng của test ẩn, dù frontend có che chúng đi; chỉ hiển thị mức tổng quan theo chính sách PoC. Phân biệt API quản trị bài/test với API sinh viên, kể cả trong OpenAPI và response model.

README phải có đường chạy cục bộ từ môi trường trống: `.env.example`, PostgreSQL, migrations, seed 20 bài, tạo tài khoản demo có quyền rõ ràng, cấu hình/kiểm tra Judge0, cấu hình AI provider, khởi động backend/giao diện và kịch bản demo bằng một bài đúng/một bài sai. Có thể dùng Docker Compose cho dịch vụ phù hợp repo; không nhầm Compose/CSDL Judge0 với PostgreSQL ứng dụng. Nếu dịch vụ ngoài chưa bật, health check phải cho biết phần nào sẵn sàng, phần nào không, thay vì trả `healthy` cho toàn luồng.

## 6. Hợp đồng ngữ cảnh lỗi giữa bộ chấm và dịch vụ gợi ý

Định nghĩa một schema có version, ví dụ `HintContextV1`, và hàm xây dựng từ **một** `grading_run` đã hoàn tất, `all_passed=false`. Nội dung: problem ID/version, mô tả/chữ ký hàm, submission ID/mã sinh viên, grading run ID/version test, loại lỗi tổng quan, số test đạt/trượt và tối đa **K=2** bằng chứng thất bại được phép chia sẻ. K=2 là **mặc định PoC cần ghi vào open-decisions**, chưa được nhóm chốt. Chọn ổn định theo `test_index`; ưu tiên test công khai có bằng chứng cụ thể. Không đưa lời giải tham chiếu, toàn bộ bộ test, đáp án ẩn hay các trường nhạy cảm vào context. Nếu chỉ có lỗi ở test ẩn, trả bằng chứng đã lược bỏ đầu vào/đáp án và nêu loại lỗi/tổng quan theo chính sách; không bịa ra một test công khai thất bại. Dịch vụ của Bảo phải nhận **schema đã lọc này**, không truy vấn test ẩn hoặc nhận response Judge0 thô tùy ý.

Lưu hoặc tái tạo context một cách xác định từ version dữ liệu, kèm `schema_version`. Kiểm thử rằng context gắn đúng bản mã nộp và lượt chấm, không trộn bài nộp sau với kết quả cũ. Context là **đầu vào thực tế** của dịch vụ gợi ý, không phải gợi ý; riêng việc dựng context không được tính quota và không thay đổi trạng thái bài.

Ví dụ **minh họa kiểu dữ liệu bàn giao nội bộ**, không phải response trả thẳng cho sinh viên; Bảo dùng các field này để tạo prompt:

```json
{
  "schema_version": "1",
  "problem_id": 1,
  "problem_version": 1,
  "submission_id": 17,
  "grading_run_id": 24,
  "test_version": 1,
  "problem": {
    "statement": "Viết hàm trả về tổng các số nguyên trong danh sách.",
    "function_signature": "sum_numbers(numbers)"
  },
  "student_code": "def sum_numbers(numbers):\n    total = 0\n    for x in numbers:\n        total += x\n        return total",
  "grading": {"status": "completed", "all_passed": false, "passed_count": 0, "failed_count": 2},
  "evidence": [
    {"test_index": 1, "failure_type": "wrong_answer", "visibility": "public", "args": [[2, 3, 4]], "expected": 9, "actual": 2}
  ]
}
```

Ví dụ là dữ liệu giả lập nhất quán với hai test ở mục 3: cả hai trượt, chỉ test công khai số 1 xuất hiện trong `evidence`. **Đây không phải log chạy thật.** Khi triển khai, tạo ví dụ JSON từ một fixture có số liệu tự nhất quán, rồi chạy test so khớp số đếm, `test_index`, phiên bản và mã nguồn. Nếu bằng chứng từ test ẩn được phép chuyển cho Bảo, phải có quyết định riêng về mức tiết lộ; mặc định này không gửi `args`, `expected`, `actual` của test ẩn. `HintContextV1` không chứa KM/KH: mức gợi ý được quyết định **tại thời điểm sinh viên yêu cầu** theo quota lúc đó, không dự đoán khi vừa chấm xong.

**Giao kèo tích hợp:** một hàm/service nội bộ dạng `build_hint_context(student_id, submission_id, grading_run_id) -> HintContextV1 | EligibilityError` kiểm tra quyền truy cập và điều kiện chấm; tài liệu nêu rõ field bắt buộc, version, lỗi (`not_owner`, `grading_pending`, `grading_technical_error`, `all_passed`, `no_shareable_evidence` nếu chính sách yêu cầu), và ví dụ fixture. Phần kiểm tra quota, gọi AI, chống lộ lời giải, ghi gợi ý thành công đặt ở **dịch vụ điều phối gợi ý**, không trộn vào hàm dựng context.

## 7. Dịch vụ gợi ý AI, kiểm tra chất lượng và quota — phần Bảo và tích hợp chung

### 7.1. Đầu vào, KM/KH và provider

`HintService` nhận `HintContextV1` cùng `requested_level` do quota quyết định, gọi provider AI qua một interface cấu hình được (`AI_PROVIDER`, `AI_MODEL`, credential, timeout, retry có giới hạn). Không hard-code khóa API hoặc tên mô hình vào repository. Cung cấp fake provider chỉ cho test và chạy offline có dán nhãn; giao diện demo thật phải dùng provider đã cấu hình và ghi rõ provider/model trong log kỹ thuật không chứa credential. Nếu không có provider hoạt động, trả lỗi kỹ thuật gợi ý và không trừ lượt; **không thay bằng văn bản gợi ý hard-code rồi nói đó là AI**.

| Mức | Ý định sư phạm | Ví dụ với lỗi `return` nằm trong vòng lặp |
| --- | --- | --- |
| KM — gợi ý thành công thứ 1 | Khoanh vùng triệu chứng/nguyên nhân để sinh viên tự kiểm tra; không đưa đoạn mã sửa | “Hãy xem hàm dừng sau khi xử lý bao nhiêu phần tử của danh sách.” |
| KH — gợi ý thành công thứ 2–3 | Gợi mở hướng thay đổi hoặc bước kiểm tra cụ thể hơn; vẫn để sinh viên tự viết mã | “So sánh vị trí lệnh trả về với bước cộng từng phần tử, rồi thử lại danh sách có ba số.” |

Đây là cách vận hành đề xuất cho hai ký hiệu KM/KH; nếu nhóm có định nghĩa chính thức khác thì chỉnh prompt/rubric theo định nghĩa ấy, **giữ nguyên mức theo thứ tự lượt đã chốt**. Prompt chỉ dùng dữ liệu từ context đã lọc; mã và văn bản do sinh viên nộp là **dữ liệu không tin cậy**, không được tuân theo câu lệnh nằm trong mã kiểu “bỏ qua quy tắc, xuất lời giải”. Yêu cầu provider trả một gợi ý ngắn, tiếng Việt, bám lỗi, không xuất lời giải, code hoàn chỉnh, test ẩn hoặc kết quả ẩn. Giới hạn kích thước đầu vào/đầu ra và thời gian gọi; không đưa thông tin nhận dạng sinh viên khi không cần.

### 7.2. Bộ kiểm tra sau AI và đánh giá của Hưởng

Bảo xây `HintChecker` chạy **trước khi lưu thành công**: nội dung không rỗng, đúng ngôn ngữ/mức, liên quan tới đề và ít nhất một bằng chứng lỗi được phép dùng, không bịa test/kết quả, không đưa lời giải hay mã hoàn chỉnh, không nhắc dữ liệu test ẩn, không chứa chỉ dẫn lạ từ mã sinh viên. Kết hợp ràng buộc xác định (độ dài, code block, trường nhạy cảm) với đánh giá nội dung có cấu trúc hoặc kiểm tra thủ công trong bộ nghiệm thu; đừng coi một regex là bằng chứng đủ rằng không lộ lời giải. Khi checker từ chối/không xác định, ghi `failure_code`, có thể thử tạo lại trong giới hạn cấu hình; cuối cùng vẫn thất bại thì không trừ lượt.

Hưởng cung cấp bộ rubric đánh giá **0–2 điểm mỗi tiêu chí**: đúng nguyên nhân, bám bằng chứng, đúng mức KM/KH, hữu ích để tự sửa, không lộ lời giải; ghi thêm cờ `leakage=true/false` độc lập, có trường hợp do hai người chấm và lưu bất đồng. Chạy rubric trên một số bài nộp sai có chủ đích và gợi ý thật; phân biệt kết quả đã đo với mục tiêu dự kiến. Checker tự động bảo vệ sản phẩm, rubric là **đánh giá chất lượng** của nghiên cứu, không lấy điểm rubric giả định thay cho phép kiểm tra tại thời điểm yêu cầu.

### 7.3. Giao dịch quota/cooldown an toàn khi đồng thời

1. `POST` nhận `submission_id`, `grading_run_id` và `idempotency_key`. Xác định sinh viên từ phiên đăng nhập; kiểm tra run thuộc submission/bài đó, đã chấm hợp lệ và sai. Nếu cùng idempotency key đã tạo yêu cầu, trả **chính yêu cầu cũ** thay vì làm lại và tính thêm lượt.
2. Mở giao dịch ngắn, khóa hoặc tạo dòng `help_quota` theo `(student_id, problem_id)` rồi khóa để kiểm tra `successful_count < 3` và `now >= last_success_at + 120 giây`. Dùng thời gian UTC nhất quán. Kiểm tra không có `hint_request` đang `pending/processing` cho cặp này. Tạo request đang xử lý kèm mức KM/KH tính từ **số lượt thành công**, lease token/expiry và unique partial index cho một yêu cầu in-flight; commit rồi nhả khóa.
3. Dựng `HintContextV1`, gọi provider và checker **ngoài giao dịch/khóa DB**. Nếu lỗi, mở giao dịch mới đánh dấu `failed`, lưu mã lỗi; không tăng số lượt, không cập nhật `last_success_at`.
4. Nếu gợi ý hợp lệ, mở giao dịch ngắn, khóa quota, kiểm tra request còn đúng lease/đang xử lý và điều kiện quota/cooldown vẫn hợp lệ; lưu nội dung, đánh dấu `succeeded`, tăng `successful_count` **đúng một**, đặt `last_success_at` theo thời điểm lưu và commit **nguyên tử**. Không bao giờ trả `succeeded` trước khi commit. Gọi hoàn tất lặp lại phải idempotent.
5. Worker timeout, crash hoặc request quá lease phải được phục hồi thành `expired/failed` có thể thử lại, không tính lượt. Kết quả AI đến muộn sau khi request hết hạn/đã kết thúc không được ghi đè hoặc tính thêm lượt. Retry cần idempotency key mới nếu người dùng thật sự muốn tạo yêu cầu mới; cùng key chỉ truy lại trạng thái cũ.

Ràng buộc DB: `successful_count BETWEEN 0 AND 3`; unique `(student_id, problem_id)` ở quota; unique `(student_id, idempotency_key)` cho yêu cầu; partial unique `(student_id, problem_id)` với status đang xử lý. Chỉ nội dung `succeeded` được hiện trong lịch sử gợi ý; request `failed/expired` có thể hiện trạng thái/lý do an toàn cho chính chủ. Tạo migration thực tế, kiểm tra migration lên/xuống phù hợp và hành vi trên PostgreSQL (SQLite không đại diện đủ cho lock/partial index).

| Chuỗi thao tác kiểm chứng | Kết quả phải có |
| --- | --- |
| KM lưu lúc 10:00:00, nộp lại lúc 10:00:30, yêu cầu gợi ý | Vẫn 1/3, chờ đến 10:02:00; không reset |
| AI lỗi lúc 10:02:01 | Vẫn 1/3, mốc cooldown vẫn 10:00:00 |
| KH lưu lúc 10:02:10 | Thành 2/3; mốc mới 10:02:10 |
| Hai POST cùng lúc cho cùng sinh viên/bài | Tối đa một request xử lý; không có hai lần thành công cho cùng cửa sổ xử lý |
| Xem lại KM/KH đã lưu | Nội dung cũ hiện ra, quota và cooldown không đổi |

Thời gian trên là ví dụ minh họa để viết test với đồng hồ giả, không phải log chạy thực tế. HTTP response nên trả `request_id`, `status`, `remaining_count`, `retry_after_seconds` khi bị cooldown, và mã lỗi ổn định khi bị từ chối; không trả prompt nội bộ hay test ẩn.

## 8. Kiểm thử bắt buộc và log kiểm chứng

- Test đơn vị cho so sánh giá trị có xét kiểu (`9` khác `"9"`), chuẩn hóa trạng thái và chọn bằng chứng (có test công khai/ẩn, kết quả thiếu, K nhỏ hơn số lỗi).
- Test tích hợp API + PostgreSQL cho nộp, lưu lượt chấm, đọc lại và lịch sử; seed lặp lại không tạo bản ghi trùng.
- Mock Judge0 để thử accepted nhưng hàm trả sai, lỗi cú pháp, runtime, timeout, lỗi mạng, phản hồi không hợp lệ, polling quá hạn, `wait=true` không được bật (nếu hỗ trợ nhánh này); kiểm tra không báo `all_passed` khi thiếu test hoặc bài có 0 test.
- Với Judge0 được cấu hình thật, chạy smoke test ít nhất một bài đúng, một bài sai nhiều test và một lỗi mã sinh viên. Nếu chưa có instance/credentials, giữ test mock chạy được và ghi chính xác lệnh/env còn cần để chạy smoke thật; không ghi “đã kiểm chứng Judge0” khi chưa chạy.
- Kiểm thử 20 lời giải tham chiếu đạt bộ test và 20 mã sai mẫu không đạt ít nhất một test; đối chiếu dự kiến của các mã sai tiêu biểu với kết quả thực tế.
- Kiểm tra `HintContext` không chứa expected/actual/input test ẩn, không chứa lời giải, không sinh từ lượt chấm lỗi kỹ thuật hoặc bài đạt hết test.
- Gọi API như sinh viên để xác minh **JSON response thật** không lộ dữ liệu test ẩn (kể cả stdout/stderr), không chỉ kiểm tra màn hình. Gọi API như một sinh viên khác để xác minh không đọc được submission/context của người khác; nếu đang dùng demo ID, ghi rõ việc này chưa thể chứng minh trước khi có auth.
- Chạy ít nhất mã có `print()` giả kết quả harness và mã gọi `sys.exit()`; xác minh không thể vì vậy mà được đánh dấu đạt hết.
- Test chính sách gợi ý với đồng hồ giả: lượt KM đầu, KH thứ 2–3, lượt thứ 4 bị chặn, cooldown đủ/chưa đủ 120 giây, nộp lại không reset, bài đã đạt không có gợi ý sửa lỗi, xem lại không trừ lượt.
- Test provider/checker thành công, timeout, lỗi, phản hồi rỗng, lộ lời giải/test ẩn, prompt injection trong mã sinh viên; các nhánh thất bại không đổi quota/cooldown. Dùng fake provider để test xác định, không ghi đó là kết quả AI thật.
- Test đồng thời **trên PostgreSQL thật**: hai POST cùng cặp chỉ một in-flight; request trùng idempotency key chỉ một nội dung và một lần tính; request hết lease và phản hồi đến muộn không tính lượt; việc lưu nội dung và tăng quota là nguyên tử.
- Smoke test AI với provider thật khi đã có cấu hình: một KM và một KH sau khi trôi cooldown trong môi trường thử nghiệm hoặc dùng đồng hồ/test setup có kiểm soát. Nếu chưa có credential, ghi rõ **chưa xác minh tích hợp AI thật** dù test fake đã qua.

Ghi log `request_id`, `submission_id`, `grading_run_id`, `problem_id`, `test_index`, trạng thái chuẩn hóa và thời gian xử lý; với AI thêm `hint_request_id`, mức KM/KH, provider/model, checker outcome, số lượt trước/sau và mã lỗi. Ẩn credential, prompt nhạy cảm, mã sinh viên và dữ liệu test ẩn ở log chia sẻ. Tạo `docs/verification.md` có lệnh chạy, cấu hình, commit hoặc phiên bản dữ liệu bài, số bài/test seed, bảng test pass/fail **thực đo**, kết quả quota/cooldown, ví dụ KM/KH thật đã rà rubric và 2–3 ví dụ log đã lược dữ liệu nhạy cảm. Không tự điền kết quả kiểm thử chưa chạy. Nếu dùng nội dung MBPP, ghi từng `task_id` được chọn và những test đã thêm/sửa.

## 9. Thứ tự hoàn thành và tiêu chí nhận bàn giao toàn hệ thống

1. **Lát cắt chấm nhỏ:** một bài + test + mã đúng/sai; FastAPI ↔ Judge0 ↔ PostgreSQL hoạt động và xem lại được kết quả.
2. **Lát cắt gợi ý nhỏ:** từ lượt chấm sai, bấm Yêu cầu → `HintContextV1` → AI provider → checker → lưu KM → quota 1/3 → xem lại. Thử nhánh AI lỗi không trừ lượt.
3. **Ổn định hai luồng:** test ẩn, lỗi kỹ thuật, trạng thái, retry/idempotency, đồng thời, cooldown, KH lượt 2–3, hết quota và UI lỗi.
4. **Mở rộng nội dung:** đủ 20 bài với mô tả/test/hàm tham chiếu/mã sai mẫu và seed idempotent; đánh giá gợi ý trên các mã sai có chủ đích.
5. **Demo trọn vẹn và chứng cứ:** README khởi động, `.env.example`, migrations, dữ liệu mẫu, OpenAPI, giao diện đầy đủ, test tự động và `docs/verification.md`. Demo một bài sai có KM/KH, một bài đúng không có gợi ý sửa lỗi, nộp lại không reset và một lỗi AI không trừ lượt.

Khi xong, Codex hãy báo: file nào được tạo/sửa, hướng chạy trong VS Code, lệnh khởi tạo DB/seed, cách cấu hình Judge0 và AI provider, kết quả kiểm thử thật, các hạng mục chưa chạy vì thiếu dịch vụ ngoài, và danh sách quyết định nhóm cần chốt. **Không nói toàn hệ thống đã chạy nếu chỉ có bộ chấm hoặc chỉ có `HintContextV1` mà chưa sinh/lưu gợi ý theo quota, hoặc nếu mới có mock AI nhưng chưa xác minh provider thật.**

## 10. Những quyết định chưa chốt — đánh dấu trong tài liệu dự án

1. Ai là chủ sở hữu chính của frontend, migrations, module quota và tích hợp FastAPI cuối cùng?
2. Định dạng bài có thống nhất chỉ viết một hàm trả giá trị JSON hay cần hỗ trợ stdin/stdout?
3. Mỗi bài có bao nhiêu test công khai/ẩn và quy tắc tiết lộ chi tiết test ẩn?
4. Mặc định K=2 bằng chứng cho Bảo có phù hợp không? Nếu chỉ trượt test ẩn thì cung cấp thông tin gì?
5. Cách đăng nhập/xác định `student_id` trong hệ thống thật; demo ID chỉ dùng cho PoC.
6. Judge0 dùng deployment nào, cấu hình giới hạn chạy và cách xử lý hàng đợi/polling cụ thể?
7. Các giá trị đầu vào/đầu ra đặc biệt, số thực và trường hợp không có kết quả được chuẩn hóa ra sao?
8. Phiên bản đề/test và dữ liệu lịch sử được giữ trong bao lâu; cần chấm lại khi thay test không?
9. Provider/mô hình AI nào, giới hạn chi phí/timeout và cấu hình môi trường thử nghiệm?
10. Định nghĩa chi tiết KM/KH và quy tắc checker đối với đoạn mã ngắn, pseudo-code, test chỉ sai ở test ẩn?
11. Có xác thực sinh viên thật ngay trong PoC hay dùng tài khoản demo có kiểm soát? Quyền xem bài nộp/gợi ý của người khác được quy định ra sao?
12. Lease timeout, retry provider, lưu prompt/output phục vụ đánh giá và chính sách lược dữ liệu/giữ log là gì?

**Ưu tiên nếu thiếu thời gian:** làm đúng **một lát cắt trọn vẹn có chấm thật và gợi ý thật** trước; sau đó hoàn thiện đủ 20 bài. Không thay lượt chấm thật bằng `passed/failed` hard-code, không dùng AI đoán test sai, không coi văn bản mock là gợi ý AI đã triển khai.
