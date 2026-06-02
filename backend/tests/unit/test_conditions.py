import pytest

from app.services.conditions import InvalidCondition, evaluate


def test_empty_rule_always_matches():
    assert evaluate({}, {}) is True
    assert evaluate(None, {"x": 1}) is True


@pytest.mark.parametrize(
    "rule,ctx,expected",
    [
        ({">": [{"var": "amount"}, 1000]}, {"amount": 1500}, True),
        ({">": [{"var": "amount"}, 1000]}, {"amount": 500}, False),
        ({"<=": [{"var": "n"}, 5]}, {"n": 5}, True),
        ({"==": [{"var": "cat"}, "travel"]}, {"cat": "travel"}, True),
        ({"!=": [{"var": "cat"}, "travel"]}, {"cat": "food"}, True),
    ],
)
def test_binary_operators(rule, ctx, expected):
    assert evaluate(rule, ctx) is expected


def test_and_or_not():
    rule = {"and": [{">": [{"var": "a"}, 1]}, {"<": [{"var": "a"}, 10]}]}
    assert evaluate(rule, {"a": 5}) is True
    assert evaluate(rule, {"a": 50}) is False
    assert evaluate({"or": [{"==": [{"var": "a"}, 1]}, {"==": [{"var": "a"}, 2]}]}, {"a": 2})
    assert evaluate({"not": [{"==": [{"var": "a"}, 1]}]}, {"a": 2}) is True


def test_type_mismatch_is_false_not_error():
    # Comparing None to int must not raise.
    assert evaluate({">": [{"var": "missing"}, 1]}, {}) is False


def test_unsafe_operator_rejected():
    with pytest.raises(InvalidCondition):
        evaluate({"__import__": ["os"]}, {})
