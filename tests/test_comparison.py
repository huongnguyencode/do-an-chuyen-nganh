from app.judging.comparison import values_equal


def test_comparison_checks_type_before_value() -> None:
    assert values_equal(9, 9)
    assert not values_equal(9, "9")
    assert not values_equal(1, True)


def test_comparison_is_recursive_for_json_values() -> None:
    assert values_equal({"items": [1, None, False]}, {"items": [1, None, False]})
    assert not values_equal({"items": [1]}, {"items": [True]})
