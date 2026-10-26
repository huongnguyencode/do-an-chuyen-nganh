from typing import Any

from app.problems.p01_sum_numbers import PROBLEM as P01


def case(args: list[Any], expected: Any, purpose: str) -> tuple[list[Any], Any, str]:
    return args, expected, purpose


def problem(
    code: str,
    slug_name: str,
    title: str,
    function_name: str,
    signature: str,
    statement: str,
    constraints: str,
    reference_code: str,
    wrong_code: str,
    expected_failed: list[int],
    cases: list[tuple[list[Any], Any, str]],
) -> dict[str, Any]:
    assert len(cases) == 8
    return {
        "slug": f"{code.lower()}-{slug_name}",
        "source_name": "self_authored",
        "source_key": code,
        "version": 1,
        "test_version": 1,
        "is_published": True,
        "title": title,
        "statement": statement,
        "function_name": function_name,
        "function_signature": signature,
        "constraints_text": constraints,
        "reference_code": reference_code.strip() + "\n",
        "wrong_samples": [
            {
                "name": "common_mistake",
                "source_code": wrong_code.strip() + "\n",
                "expected_failed_test_indexes": expected_failed,
            }
        ],
        "tests": [
            {
                "test_index": index,
                "args": args,
                "expected": expected,
                "is_public": index <= 3,
                "purpose": purpose,
            }
            for index, (args, expected, purpose) in enumerate(cases, start=1)
        ],
    }


P02 = problem(
    "P02",
    "count-even",
    "Đếm số chẵn",
    "count_even",
    "count_even(numbers)",
    "Viết hàm trả về số lượng số chẵn trong danh sách số nguyên.",
    "Danh sách có tối đa 100 phần tử. Số 0 và số âm chia hết cho 2 đều là số chẵn.",
    """
def count_even(numbers):
    return sum(1 for number in numbers if number % 2 == 0)
""",
    """
def count_even(numbers):
    return sum(1 for number in numbers if number % 2 == 1)
""",
    [4, 5, 6, 7, 8],
    [
        case([[1, 2, 3, 4]], 2, "Có cả số chẵn và số lẻ"),
        case([[]], 0, "Danh sách rỗng"),
        case([[0, -2, -3, 5]], 2, "Số 0 và số âm chẵn"),
        case([[1, 3, 5]], 0, "Không có số chẵn"),
        case([[2]], 1, "Một số chẵn"),
        case([[-4, -6]], 2, "Chỉ có số âm chẵn"),
        case([[10, 11, 12, 13, 14]], 3, "Nhiều số chẵn xen kẽ"),
        case([[-1, 0, 1]], 1, "Số 0 giữa hai số lẻ"),
    ],
)

P03 = problem(
    "P03",
    "find-max",
    "Tìm giá trị lớn nhất",
    "find_max",
    "find_max(numbers)",
    "Trả về giá trị lớn nhất trong danh sách; nếu danh sách rỗng, trả về None.",
    "Danh sách gồm các số nguyên và có tối đa 100 phần tử.",
    """
def find_max(numbers):
    if not numbers:
        return None
    largest = numbers[0]
    for number in numbers[1:]:
        if number > largest:
            largest = number
    return largest
""",
    """
def find_max(numbers):
    largest = 0
    for number in numbers:
        if number > largest:
            largest = number
    return largest
""",
    [2, 3, 7],
    [
        case([[3, 1, 2]], 3, "Thứ tự không tăng"),
        case([[]], None, "Danh sách rỗng"),
        case([[-5, -2, -8]], -2, "Chỉ có số âm"),
        case([[7]], 7, "Một phần tử"),
        case([[4, 4, 2]], 4, "Giá trị lớn nhất lặp lại"),
        case([[0, -1]], 0, "Có số 0"),
        case([[-1, -1]], -1, "Hai số âm bằng nhau"),
        case([[100, 99, 100]], 100, "Lớn nhất ở hai vị trí"),
    ],
)

P04 = problem(
    "P04",
    "reverse-text",
    "Đảo ngược chuỗi",
    "reverse_text",
    "reverse_text(text)",
    "Trả về chuỗi mới có thứ tự ký tự đảo ngược hoàn toàn so với chuỗi đầu vào.",
    "Chuỗi có tối đa 500 ký tự Unicode; chuỗi rỗng trả về chuỗi rỗng.",
    """
def reverse_text(text):
    return text[::-1]
""",
    """
def reverse_text(text):
    return text[:-1][::-1]
""",
    [1, 3, 4, 5, 6, 7, 8],
    [
        case(["Python"], "nohtyP", "Chuỗi ASCII thông thường"),
        case([""], "", "Chuỗi rỗng"),
        case(["áβ🙂"], "🙂βá", "Ký tự Unicode"),
        case(["a"], "a", "Một ký tự"),
        case(["abba"], "abba", "Chuỗi đối xứng"),
        case(["hello world"], "dlrow olleh", "Có dấu cách"),
        case(["Aa"], "aA", "Phân biệt hoa thường"),
        case(["112233"], "332211", "Ký tự lặp"),
    ],
)

P05 = problem(
    "P05",
    "is-palindrome",
    "Kiểm tra chuỗi đối xứng",
    "is_palindrome",
    "is_palindrome(text)",
    "Trả về True nếu chuỗi đọc xuôi và ngược giống hệt nhau, ngược lại trả về False.",
    "So sánh chính xác từng ký tự, có phân biệt hoa thường và dấu cách. Chuỗi rỗng là đối xứng.",
    """
def is_palindrome(text):
    return text == text[::-1]
""",
    """
def is_palindrome(text):
    lowered = text.lower()
    return lowered == lowered[::-1]
""",
    [3],
    [
        case(["level"], True, "Độ dài lẻ và đối xứng"),
        case([""], True, "Chuỗi rỗng"),
        case(["Abba"], False, "Phân biệt chữ hoa thường"),
        case(["abba"], True, "Độ dài chẵn và đối xứng"),
        case(["abc"], False, "Không đối xứng"),
        case(["aa"], True, "Hai ký tự giống nhau"),
        case(["🙂a🙂"], True, "Unicode đối xứng"),
        case(["a "], False, "Dấu cách có ý nghĩa"),
    ],
)

P06 = problem(
    "P06",
    "factorial",
    "Tính giai thừa",
    "factorial",
    "factorial(n)",
    "Trả về n! là tích các số nguyên từ 1 đến n; quy ước 0! = 1.",
    "n là số nguyên trong đoạn [0, 12].",
    """
def factorial(n):
    result = 1
    for value in range(2, n + 1):
        result *= value
    return result
""",
    """
def factorial(n):
    result = 1
    for value in range(1, n):
        result *= value
    return result
""",
    [3, 4, 5, 6, 7, 8],
    [
        case([0], 1, "Quy ước 0 giai thừa"),
        case([1], 1, "Một giai thừa"),
        case([5], 120, "Giá trị thông thường"),
        case([2], 2, "Biên nhỏ"),
        case([3], 6, "Ba giai thừa"),
        case([7], 5040, "Giá trị trung bình"),
        case([10], 3628800, "Giá trị lớn"),
        case([12], 479001600, "Cận trên"),
    ],
)

P07 = problem(
    "P07",
    "fibonacci",
    "Số Fibonacci thứ n",
    "fibonacci",
    "fibonacci(n)",
    "Trả về số Fibonacci thứ n với F(0)=0, F(1)=1 và F(n)=F(n-1)+F(n-2).",
    "n là số nguyên trong đoạn [0, 30].",
    """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
""",
    """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return b
""",
    [1, 3, 4, 5, 6, 7, 8],
    [
        case([0], 0, "Fibonacci thứ 0"),
        case([1], 1, "Fibonacci thứ 1"),
        case([2], 1, "Giá trị bắt đầu truy hồi"),
        case([3], 2, "Giá trị nhỏ"),
        case([5], 5, "Giá trị thông thường"),
        case([8], 21, "Giá trị trung bình"),
        case([10], 55, "Fibonacci thứ 10"),
        case([20], 6765, "Giá trị lớn hơn"),
    ],
)

P08 = problem(
    "P08",
    "is-prime",
    "Kiểm tra số nguyên tố",
    "is_prime",
    "is_prime(n)",
    "Trả về True nếu n là số nguyên tố, ngược lại trả về False.",
    "n là số nguyên. Mọi n nhỏ hơn 2 không phải số nguyên tố.",
    """
def is_prime(n):
    if n < 2:
        return False
    divisor = 2
    while divisor * divisor <= n:
        if n % divisor == 0:
            return False
        divisor += 1
    return True
""",
    """
def is_prime(n):
    if n < 2:
        return False
    for divisor in range(2, int(n ** 0.5)):
        if n % divisor == 0:
            return False
    return True
""",
    [3, 7],
    [
        case([2], True, "Số nguyên tố nhỏ nhất"),
        case([1], False, "Nhỏ hơn 2"),
        case([4], False, "Số chính phương nhỏ"),
        case([3], True, "Số nguyên tố lẻ"),
        case([0], False, "Số 0"),
        case([-7], False, "Số âm"),
        case([49], False, "Bình phương của số nguyên tố"),
        case([97], True, "Số nguyên tố lớn hơn"),
    ],
)

P09 = problem(
    "P09",
    "greatest-common-divisor",
    "Ước chung lớn nhất",
    "gcd",
    "gcd(a, b)",
    "Trả về ước chung lớn nhất của hai số nguyên không âm bằng thuật toán phù hợp.",
    "a và b thuộc [0, 100000]. Quy ước gcd(0, 0) = 0.",
    """
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
""",
    """
def gcd(a, b):
    return min(a, b)
""",
    [1, 2, 5, 6, 8],
    [
        case([48, 18], 6, "Hai số thông thường"),
        case([0, 5], 5, "Một số bằng 0"),
        case([0, 0], 0, "Cả hai bằng 0"),
        case([7, 7], 7, "Hai số bằng nhau"),
        case([18, 48], 6, "Đổi thứ tự tham số"),
        case([21, 14], 7, "Có ước chung khác 1"),
        case([1, 99], 1, "Hai số nguyên tố cùng nhau"),
        case([270, 192], 6, "Giá trị lớn hơn"),
    ],
)

P10 = problem(
    "P10",
    "unique-in-order",
    "Xóa trùng và giữ thứ tự",
    "unique_in_order",
    "unique_in_order(items)",
    "Trả về danh sách chỉ giữ lần xuất hiện đầu tiên của mỗi số nguyên.",
    "items là danh sách tối đa 100 số nguyên; thứ tự kết quả theo lần xuất hiện đầu.",
    """
def unique_in_order(items):
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
""",
    """
def unique_in_order(items):
    return sorted(set(items))
""",
    [4, 5, 7],
    [
        case([[1, 2, 1, 3, 2]], [1, 2, 3], "Trùng rải rác"),
        case([[]], [], "Danh sách rỗng"),
        case([[1, 1, 1]], [1], "Một giá trị lặp lại"),
        case([[3, 2, 1]], [3, 2, 1], "Không trùng và thứ tự giảm"),
        case([[0, -1, 0, -1]], [0, -1], "Số âm và số 0"),
        case([[5]], [5], "Một phần tử"),
        case([[2, 1, 2, 1, 3]], [2, 1, 3], "Thứ tự đầu tiên quan trọng"),
        case([[-2, -2, 0, -2]], [-2, 0], "Trùng số âm"),
    ],
)

P11 = problem(
    "P11",
    "second-largest",
    "Phần tử lớn thứ hai phân biệt",
    "second_largest",
    "second_largest(numbers)",
    "Trả về giá trị lớn thứ hai phân biệt; nếu không có đủ hai giá trị, trả về None.",
    "numbers là danh sách tối đa 100 số nguyên. Các lần lặp không tạo giá trị phân biệt mới.",
    """
def second_largest(numbers):
    distinct = sorted(set(numbers), reverse=True)
    return distinct[1] if len(distinct) >= 2 else None
""",
    """
def second_largest(numbers):
    ordered = sorted(numbers, reverse=True)
    return ordered[1] if len(ordered) >= 2 else None
""",
    [2, 5, 7],
    [
        case([[1, 3, 2]], 2, "Ba giá trị phân biệt"),
        case([[5, 5, 4]], 4, "Giá trị lớn nhất lặp"),
        case([[]], None, "Danh sách rỗng"),
        case([[7]], None, "Một phần tử"),
        case([[2, 2]], None, "Chỉ một giá trị phân biệt"),
        case([[-1, -3, -2]], -2, "Chỉ có số âm"),
        case([[10, 9, 10, 8]], 9, "Lớn nhất xuất hiện hai lần"),
        case([[0, -1]], -1, "Hai giá trị gồm số 0"),
    ],
)

P12 = problem(
    "P12",
    "merge-sorted",
    "Gộp hai danh sách đã sắp",
    "merge_sorted",
    "merge_sorted(left, right)",
    "Gộp hai danh sách số nguyên đã tăng dần thành một danh sách tăng dần mới.",
    "Hai đầu vào đã sắp tăng dần, có thể rỗng và có giá trị trùng.",
    """
def merge_sorted(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    return result + left[i:] + right[j:]
""",
    """
def merge_sorted(left, right):
    return left + right
""",
    [1, 4, 6, 7, 8],
    [
        case([[1, 3], [2, 4]], [1, 2, 3, 4], "Hai danh sách xen kẽ"),
        case([[], []], [], "Cả hai rỗng"),
        case([[], [1, 2]], [1, 2], "Bên trái rỗng"),
        case([[-3, 0], [-2, 0]], [-3, -2, 0, 0], "Số âm và giá trị trùng"),
        case([[1, 1], [1]], [1, 1, 1], "Tất cả giá trị trùng"),
        case([[5], [1, 2, 6]], [1, 2, 5, 6], "Một bên có một phần tử"),
        case([[-1], [-2]], [-2, -1], "Hai số âm"),
        case([[1, 4, 7], [2, 3, 8]], [1, 2, 3, 4, 7, 8], "Nhiều lần chuyển phía"),
    ],
)

P13 = problem(
    "P13",
    "first-index",
    "Vị trí xuất hiện đầu tiên",
    "first_index",
    "first_index(items, target)",
    "Trả về chỉ số đầu tiên của target trong danh sách; nếu không thấy, trả về -1.",
    "items là danh sách số nguyên, chỉ số bắt đầu từ 0.",
    """
def first_index(items, target):
    for index, item in enumerate(items):
        if item == target:
            return index
    return -1
""",
    """
def first_index(items, target):
    found = -1
    for index, item in enumerate(items):
        if item == target:
            found = index
    return found
""",
    [3, 6],
    [
        case([[1, 2, 3], 2], 1, "Tìm thấy ở giữa"),
        case([[], 5], -1, "Danh sách rỗng"),
        case([[4, 4], 4], 0, "Mục tiêu xuất hiện nhiều lần"),
        case([[1, 2], 9], -1, "Không tìm thấy"),
        case([[5], 5], 0, "Một phần tử và tìm thấy"),
        case([[1, 2, 1], 1], 0, "Lấy vị trí đầu thay vì cuối"),
        case([[-1, 0], 0], 1, "Có số âm"),
        case([[3, 2, 1], 1], 2, "Tìm thấy ở cuối"),
    ],
)

P14 = problem(
    "P14",
    "character-counts",
    "Đếm tần suất ký tự",
    "char_counts",
    "char_counts(text)",
    "Trả về dictionary ánh xạ từng ký tự sang số lần xuất hiện trong chuỗi.",
    "Phân biệt hoa thường; dấu cách và ký tự Unicode cũng được đếm.",
    """
def char_counts(text):
    result = {}
    for character in text:
        result[character] = result.get(character, 0) + 1
    return result
""",
    """
def char_counts(text):
    result = {}
    for character in text:
        if character != " ":
            key = character.lower()
            result[key] = result.get(key, 0) + 1
    return result
""",
    [3, 4, 7, 8],
    [
        case(["aba"], {"a": 2, "b": 1}, "Ký tự lặp"),
        case([""], {}, "Chuỗi rỗng"),
        case(["a a"], {"a": 2, " ": 1}, "Đếm cả dấu cách"),
        case(["Aa"], {"A": 1, "a": 1}, "Phân biệt hoa thường"),
        case(["🙂🙂a"], {"🙂": 2, "a": 1}, "Unicode"),
        case(["hello"], {"h": 1, "e": 1, "l": 2, "o": 1}, "Nhiều ký tự"),
        case(["  "], {" ": 2}, "Chỉ có dấu cách"),
        case(["éÉé"], {"é": 2, "É": 1}, "Unicode có hoa thường"),
    ],
)

P15 = problem(
    "P15",
    "digit-sum",
    "Tổng các chữ số",
    "digit_sum",
    "digit_sum(n)",
    "Trả về tổng các chữ số thập phân của trị tuyệt đối của n.",
    "n là số nguyên; dấu âm không được tính là một chữ số.",
    """
def digit_sum(n):
    return sum(int(character) for character in str(abs(n)))
""",
    """
def digit_sum(n):
    total = 0
    while n > 0:
        total += n % 10
        n //= 10
    return total
""",
    [3, 6],
    [
        case([123], 6, "Nhiều chữ số"),
        case([0], 0, "Số 0"),
        case([-123], 6, "Số âm"),
        case([5], 5, "Một chữ số"),
        case([1001], 2, "Có chữ số 0 ở giữa"),
        case([-90], 9, "Số âm có chữ số 0"),
        case([99999], 45, "Nhiều chữ số giống nhau"),
        case([10], 1, "Kết thúc bằng 0"),
    ],
)

P16 = problem(
    "P16",
    "normalize-spaces",
    "Chuẩn hóa khoảng trắng",
    "normalize_spaces",
    "normalize_spaces(text)",
    "Loại bỏ khoảng trắng đầu cuối và thay mỗi nhóm khoảng trắng bằng một dấu cách.",
    "Khoảng trắng gồm dấu cách, tab và xuống dòng theo quy tắc str.split() của Python.",
    """
def normalize_spaces(text):
    return " ".join(text.split())
""",
    """
def normalize_spaces(text):
    return text.strip()
""",
    [1, 4, 6, 7, 8],
    [
        case(["  hello   world "], "hello world", "Thừa khoảng trắng đầu cuối và ở giữa"),
        case([""], "", "Chuỗi rỗng"),
        case(["one"], "one", "Không cần thay đổi"),
        case(["\talpha\n beta  "], "alpha beta", "Tab và xuống dòng"),
        case(["   "], "", "Chỉ có khoảng trắng"),
        case(["a  b   c"], "a b c", "Nhiều nhóm khoảng trắng"),
        case([" xin   chào "], "xin chào", "Chuỗi tiếng Việt"),
        case(["a\tb\nc"], "a b c", "Các loại khoảng trắng xen kẽ"),
    ],
)

P17 = problem(
    "P17",
    "ordered-intersection",
    "Giao hai danh sách không trùng",
    "intersection",
    "intersection(left, right)",
    "Trả về các giá trị có trong cả hai danh sách, không lặp và theo thứ tự xuất hiện đầu trong left.",
    "Hai danh sách chứa số nguyên và có tối đa 100 phần tử.",
    """
def intersection(left, right):
    right_values = set(right)
    seen = set()
    result = []
    for item in left:
        if item in right_values and item not in seen:
            seen.add(item)
            result.append(item)
    return result
""",
    """
def intersection(left, right):
    return sorted(set(left) & set(right))
""",
    [3, 7],
    [
        case([[1, 2, 2, 3], [2, 3, 4]], [2, 3], "Có trùng trong left"),
        case([[], [1]], [], "Left rỗng"),
        case([[3, 1, 2], [2, 3]], [3, 2], "Giữ thứ tự của left"),
        case([[1, 1], [1]], [1], "Loại bỏ kết quả trùng"),
        case([[1, 2], [3, 4]], [], "Không có giao"),
        case([[-1, 0, 1], [1, -1]], [-1, 1], "Số âm và thứ tự left"),
        case([[2, 3, 2, 1], [2, 1]], [2, 1], "Thứ tự khác thứ tự tăng"),
        case([[5], [5, 5]], [5], "Right có giá trị trùng"),
    ],
)

P18 = problem(
    "P18",
    "diagonal-sum",
    "Tổng đường chéo chính",
    "diagonal_sum",
    "diagonal_sum(matrix)",
    "Trả về tổng các phần tử trên đường chéo chính của ma trận vuông.",
    "matrix là ma trận vuông không rỗng kích thước tối đa 20, chứa số nguyên.",
    """
def diagonal_sum(matrix):
    return sum(matrix[index][index] for index in range(len(matrix)))
""",
    """
def diagonal_sum(matrix):
    return sum(row[0] for row in matrix)
""",
    [2, 3, 4, 6, 7],
    [
        case([[[5]]], 5, "Ma trận 1x1"),
        case([[[1, 2], [3, 4]]], 5, "Ma trận 2x2"),
        case([[[-1, 0], [2, -3]]], -4, "Giá trị âm trên đường chéo"),
        case([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], 15, "Ma trận 3x3"),
        case([[[0, 0], [0, 0]]], 0, "Ma trận toàn 0"),
        case([[[10, -1], [-1, 10]]], 20, "Hai giá trị đường chéo bằng nhau"),
        case([[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]], 34, "Ma trận 4x4"),
        case([[[-5]]], -5, "Ma trận 1x1 âm"),
    ],
)

P19 = problem(
    "P19",
    "word-count",
    "Đếm từ trong câu",
    "word_count",
    "word_count(text)",
    "Trả về số từ khi tách chuỗi theo các nhóm khoảng trắng.",
    "Dùng quy tắc tách khoảng trắng của str.split(); dấu câu vẫn thuộc từ liền kề.",
    """
def word_count(text):
    return len(text.split())
""",
    """
def word_count(text):
    return len(text.split(" "))
""",
    [2, 3, 5, 6, 8],
    [
        case(["hello world"], 2, "Hai từ"),
        case([""], 0, "Chuỗi rỗng"),
        case(["   "], 0, "Chỉ có khoảng trắng"),
        case(["one"], 1, "Một từ"),
        case(["a  b   c"], 3, "Nhiều dấu cách liên tiếp"),
        case(["\talpha\nbeta"], 2, "Tab và xuống dòng"),
        case(["xin chào bạn"], 3, "Câu tiếng Việt"),
        case([" punctuation, stays "], 2, "Dấu câu thuộc từ"),
    ],
)

P20 = problem(
    "P20",
    "balanced-brackets",
    "Kiểm tra ngoặc cân bằng",
    "balanced_brackets",
    "balanced_brackets(text)",
    "Trả về True nếu các ngoặc (), [] và {} đóng mở đúng thứ tự và lồng nhau hợp lệ.",
    "Bỏ qua mọi ký tự không phải ngoặc. Chuỗi không có ngoặc được xem là cân bằng.",
    """
def balanced_brackets(text):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for character in text:
        if character in "([{":
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                return False
    return not stack
""",
    """
def balanced_brackets(text):
    return (text.count("(") == text.count(")")
            and text.count("[") == text.count("]")
            and text.count("{") == text.count("}"))
""",
    [5, 7],
    [
        case([""], True, "Chuỗi rỗng"),
        case(["()[]{}"], True, "Ba cặp liên tiếp"),
        case(["([{}])"], True, "Ngoặc lồng nhau đúng"),
        case(["(]"], False, "Sai loại ngoặc đóng"),
        case(["([)]"], False, "Sai thứ tự lồng"),
        case(["abc(def)"], True, "Bỏ qua ký tự khác ngoặc"),
        case([")("], False, "Ngoặc đóng xuất hiện trước"),
        case(["((("], False, "Thiếu ngoặc đóng"),
    ],
)


ALL_PROBLEMS = [
    P01,
    P02,
    P03,
    P04,
    P05,
    P06,
    P07,
    P08,
    P09,
    P10,
    P11,
    P12,
    P13,
    P14,
    P15,
    P16,
    P17,
    P18,
    P19,
    P20,
]
