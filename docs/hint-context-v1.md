# Hợp đồng HintContextV1

`HintContextV1` là dữ liệu nội bộ được tạo khi sinh viên chủ động yêu cầu trợ
giúp ở giai đoạn tích hợp với Bảo. Việc dựng context không gọi AI, không sinh
KM/KH và không thay đổi quota.

## Điều kiện

- submission thuộc `student_id` đang yêu cầu;
- grading run thuộc đúng submission;
- run có trạng thái `completed`, đủ số test và `all_passed=false`;
- không có kết quả `infrastructure_error` hoặc `incomplete`;
- chọn tối đa K=2 test công khai sai theo `test_index`.

Mã lỗi: `not_owner`, `grading_run_not_found`, `grading_pending`,
`grading_technical_error`, `all_passed`.

## Fixture minh họa

```json
{
  "schema_version": "1",
  "problem_id": 1,
  "problem_version": 1,
  "submission_id": 17,
  "grading_run_id": 24,
  "test_version": 1,
  "problem": {
    "statement": "Viết hàm sum_numbers(numbers) nhận một danh sách số nguyên và trả về tổng.",
    "function_signature": "sum_numbers(numbers)"
  },
  "student_code": "def sum_numbers(numbers):\n    total = 0\n    for number in numbers:\n        total += number\n        return total",
  "grading": {
    "status": "completed",
    "all_passed": false,
    "passed_count": 2,
    "failed_count": 6
  },
  "evidence": [
    {
      "visibility": "public",
      "test_index": 1,
      "failure_type": "wrong_answer",
      "args": [[2, 3, 4]],
      "expected": 9,
      "actual": 2,
      "error_summary": null
    },
    {
      "visibility": "public",
      "test_index": 2,
      "failure_type": "wrong_answer",
      "args": [[]],
      "expected": 0,
      "actual": null,
      "error_summary": null
    }
  ]
}
```

Đây là fixture tự nhất quán, không phải log Judge0 thật. Khi chỉ trượt test ẩn,
`evidence` chứa duy nhất `visibility=hidden_summary`; schema đó không có các
trường `args`, `expected`, `actual` hoặc `test_index`.
