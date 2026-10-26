import json
import math

from app.problems.catalog import ALL_PROBLEMS


def p01(numbers: list[int]) -> int:
    return sum(numbers)


def p02(numbers: list[int]) -> int:
    return sum(number % 2 == 0 for number in numbers)


def p03(numbers: list[int]) -> int | None:
    return max(numbers) if numbers else None


def p04(text: str) -> str:
    return "".join(reversed(text))


def p05(text: str) -> bool:
    return all(text[index] == text[-index - 1] for index in range(len(text) // 2))


def p06(n: int) -> int:
    return math.prod(range(1, n + 1))


def p07(n: int) -> int:
    sequence = [0, 1]
    for _ in range(n):
        sequence.append(sequence[-1] + sequence[-2])
    return sequence[n]


def p08(n: int) -> bool:
    return n >= 2 and all(n % divisor for divisor in range(2, math.isqrt(n) + 1))


def p09(a: int, b: int) -> int:
    return math.gcd(a, b)


def p10(items: list[int]) -> list[int]:
    return list(dict.fromkeys(items))


def p11(numbers: list[int]) -> int | None:
    values = sorted(set(numbers))
    return values[-2] if len(values) >= 2 else None


def p12(left: list[int], right: list[int]) -> list[int]:
    return sorted(left + right)


def p13(items: list[int], target: int) -> int:
    return items.index(target) if target in items else -1


def p14(text: str) -> dict[str, int]:
    return {character: text.count(character) for character in dict.fromkeys(text)}


def p15(n: int) -> int:
    return sum(map(int, str(abs(n))))


def p16(text: str) -> str:
    return " ".join(text.split())


def p17(left: list[int], right: list[int]) -> list[int]:
    return list(dict.fromkeys(item for item in left if item in right))


def p18(matrix: list[list[int]]) -> int:
    return sum(row[index] for index, row in enumerate(matrix))


def p19(text: str) -> int:
    return sum(1 for part in text.split() if part)


def p20(text: str) -> bool:
    opening = "([{"
    closing = ")]}"
    stack: list[str] = []
    for character in text:
        if character in opening:
            stack.append(character)
        elif character in closing:
            if not stack or opening.index(stack.pop()) != closing.index(character):
                return False
    return not stack


ORACLES = {
    f"P{index:02}": oracle
    for index, oracle in enumerate(
        [
            p01,
            p02,
            p03,
            p04,
            p05,
            p06,
            p07,
            p08,
            p09,
            p10,
            p11,
            p12,
            p13,
            p14,
            p15,
            p16,
            p17,
            p18,
            p19,
            p20,
        ],
        start=1,
    )
}


def test_catalog_has_20_complete_unique_problems() -> None:
    assert len(ALL_PROBLEMS) == 20
    assert len({item["slug"] for item in ALL_PROBLEMS}) == 20
    assert len({item["source_key"] for item in ALL_PROBLEMS}) == 20
    assert len({item["function_name"] for item in ALL_PROBLEMS}) == 20
    assert [item["source_key"] for item in ALL_PROBLEMS] == [
        f"P{index:02}" for index in range(1, 21)
    ]


def test_every_problem_has_eight_verified_json_tests() -> None:
    for item in ALL_PROBLEMS:
        tests = item["tests"]
        assert len(tests) == 8, item["source_key"]
        assert [test["test_index"] for test in tests] == list(range(1, 9))
        assert sum(test["is_public"] for test in tests) == 3
        oracle = ORACLES[item["source_key"]]
        for test in tests:
            json.dumps(test["args"], ensure_ascii=False, allow_nan=False)
            json.dumps(test["expected"], ensure_ascii=False, allow_nan=False)
            assert oracle(*test["args"]) == test["expected"], (
                item["source_key"],
                test["test_index"],
            )


def test_reference_and_wrong_samples_are_syntactically_valid() -> None:
    for item in ALL_PROBLEMS:
        compile(item["reference_code"], f"<{item['source_key']}-reference>", "exec")
        assert item["wrong_samples"]
        for sample in item["wrong_samples"]:
            compile(sample["source_code"], f"<{item['source_key']}-wrong>", "exec")
            assert sample["expected_failed_test_indexes"]
            assert set(sample["expected_failed_test_indexes"]) <= set(range(1, 9))


if __name__ == "__main__":
    test_catalog_has_20_complete_unique_problems()
    test_every_problem_has_eight_verified_json_tests()
    test_reference_and_wrong_samples_are_syntactically_valid()
    print("PASS catalog: 20 problems, 160 independently verified tests")
