"""Tiny, safe JSONLogic-style evaluator for approval-workflow triggers.

Workflows can carry a declarative trigger like
    {">": [{"var": "amount"}, 1000]}
meaning "require this workflow only when amount > 1000". We evaluate it against
a context dict WITHOUT eval/exec — only an explicit allowlist of operators — so
admin-authored rules can never execute arbitrary code (injection-safe).
An empty trigger ({}) always matches.
"""

from typing import Any

_BINARY = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class InvalidCondition(ValueError):
    pass


def evaluate(rule: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    if not rule:
        return True
    return bool(_eval(rule, context))


def _eval(node: Any, ctx: dict[str, Any]) -> Any:
    # Literals pass through.
    if not isinstance(node, dict):
        return node
    if len(node) != 1:
        raise InvalidCondition(f"expected single operator, got {list(node)}")

    op, args = next(iter(node.items()))

    if op == "var":
        key = args if isinstance(args, str) else args[0]
        return ctx.get(key)

    if op in _BINARY:
        left, right = (_eval(args[0], ctx), _eval(args[1], ctx))
        try:
            return _BINARY[op](left, right)
        except TypeError:
            return False

    if op == "and":
        return all(_eval(a, ctx) for a in args)
    if op == "or":
        return any(_eval(a, ctx) for a in args)
    if op == "not":
        return not _eval(args[0] if isinstance(args, list) else args, ctx)

    raise InvalidCondition(f"unsupported operator: {op}")
