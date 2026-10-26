PROBLEM = {
    "slug": "p01-sum-numbers",
    "source_name": "self_authored",
    "source_key": "P01",
    "version": 1,
    "test_version": 1,
    "is_published": True,
    "title": "Tính tổng danh sách",
    "statement": (
        "Viết hàm sum_numbers(numbers) nhận một danh sách số nguyên và trả về "
        "tổng của tất cả phần tử. Danh sách rỗng phải trả về 0."
    ),
    "function_name": "sum_numbers",
    "function_signature": "sum_numbers(numbers)",
    "constraints_text": (
        "numbers là danh sách có tối đa 100 số nguyên, mỗi số nằm trong "
        "đoạn [-10000, 10000]. Không thay đổi danh sách đầu vào."
    ),
    "reference_code": (
        "def sum_numbers(numbers):\n"
        "    total = 0\n"
        "    for number in numbers:\n"
        "        total += number\n"
        "    return total\n"
    ),
    "wrong_samples": [
        {
            "name": "return_too_early",
            "source_code": (
                "def sum_numbers(numbers):\n"
                "    total = 0\n"
                "    for number in numbers:\n"
                "        total += number\n"
                "        return total\n"
            ),
            "expected_failed_test_indexes": [1, 2, 3, 6, 7, 8],
        }
    ],
    "tests": [
        {
            "test_index": 1,
            "args": [[2, 3, 4]],
            "expected": 9,
            "is_public": True,
            "purpose": "Danh sách nhiều số dương",
        },
        {
            "test_index": 2,
            "args": [[]],
            "expected": 0,
            "is_public": True,
            "purpose": "Danh sách rỗng",
        },
        {
            "test_index": 3,
            "args": [[-3, 1, 2]],
            "expected": 0,
            "is_public": True,
            "purpose": "Số âm và số dương triệt tiêu",
        },
        {
            "test_index": 4,
            "args": [[5]],
            "expected": 5,
            "is_public": False,
            "purpose": "Một phần tử",
        },
        {
            "test_index": 5,
            "args": [[0, 0, 0]],
            "expected": 0,
            "is_public": False,
            "purpose": "Tất cả phần tử bằng không",
        },
        {
            "test_index": 6,
            "args": [[-5, -2]],
            "expected": -7,
            "is_public": False,
            "purpose": "Chỉ có số âm",
        },
        {
            "test_index": 7,
            "args": [[100, -50, 25]],
            "expected": 75,
            "is_public": False,
            "purpose": "Giá trị khác dấu",
        },
        {
            "test_index": 8,
            "args": [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]],
            "expected": 55,
            "is_public": False,
            "purpose": "Danh sách dài hơn để phát hiện return sớm",
        },
    ],
}
