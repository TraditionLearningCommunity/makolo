from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


ALLOWED_OPS = {
    "const", "field", "param", "add", "sub", "mul", "div", "min", "max", "abs",
    "sqrt", "log1p", "pow", "clamp", "delta", "positive_delta", "relative_delta",
    "ratio", "percentage", "if",
}
ALLOWED_AGGREGATIONS = {"SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX", "DELTA", "SUM_DISTINCT_OUTCOME", "LATEST_STATE"}
ALLOWED_CURVES = {"LINEAR", "LOG", "SQRT", "POWER", "PIECEWISE"}
ALLOWED_MODULATORS = {"confidence", "scarcity", "reliability", "maturity", "anti_abuse", "temporal_factor"}


def decimal_value(value):
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"Valeur Recognition invalide: {value!r}.") from exc


def _walk(expression):
    if expression in ({}, None, []):
        return
    if not isinstance(expression, dict):
        raise ValidationError("Une expression Recognition doit être déclarative.")
    op = expression.get("op")
    if op not in ALLOWED_OPS:
        raise ValidationError(f"Opération Recognition non autorisée: {op!r}.")
    for child in expression.get("args", []):
        _walk(child)
    for key in ("then", "else"):
        child = expression.get(key)
        if isinstance(child, dict):
            _walk(child)


def validate_rule_definition(rule):
    if not (rule.signal_kind or "").strip():
        raise ValidationError({"signal_kind": "Le Signal est obligatoire."})
    _walk(rule.measure)
    if rule.aggregation not in ALLOWED_AGGREGATIONS:
        raise ValidationError({"aggregation": "Agrégation Recognition non autorisée."})
    curve_kind = (rule.curve or {}).get("kind", "LINEAR")
    if curve_kind not in ALLOWED_CURVES:
        raise ValidationError({"curve": "Courbe Recognition non autorisée."})
    unknown = set(rule.modulators or []) - ALLOWED_MODULATORS
    if unknown:
        raise ValidationError({"modulators": f"Modulateurs inconnus: {', '.join(sorted(unknown))}."})


def evaluate_condition(condition, values):
    if not condition:
        return True
    if "all" in condition:
        return all(evaluate_condition(item, values) for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(item, values) for item in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], values)
    field = condition.get("field")
    operator = condition.get("op", "eq")
    expected = condition.get("value")
    actual = values.get(field)
    if operator == "eq": return actual == expected
    if operator == "ne": return actual != expected
    if operator == "gt": return actual is not None and actual > expected
    if operator == "gte": return actual is not None and actual >= expected
    if operator == "lt": return actual is not None and actual < expected
    if operator == "lte": return actual is not None and actual <= expected
    if operator == "in": return actual in (expected or [])
    if operator == "not_in": return actual not in (expected or [])
    if operator == "is_null": return actual is None
    if operator == "not_null": return actual is not None
    raise ValidationError(f"Condition Recognition non supportée: {operator!r}.")


def evaluate_expression(expression, values, parameters):
    if not expression:
        return Decimal("0")
    op = expression.get("op")
    if op == "const": return decimal_value(expression.get("value", 0))
    if op == "field": return decimal_value(values.get(expression.get("name"), expression.get("default", 0)))
    if op == "param": return decimal_value(parameters.get(expression.get("name"), expression.get("default", 0)))
    if op == "if":
        branch = expression.get("then") if evaluate_condition(expression.get("condition", {}), values) else expression.get("else")
        return evaluate_expression(branch, values, parameters)
    args = [evaluate_expression(arg, values, parameters) for arg in expression.get("args", [])]
    if op == "add": return sum(args, Decimal("0"))
    if op == "sub": return args[0] - args[1]
    if op == "mul":
        result = Decimal("1")
        for arg in args: result *= arg
        return result
    if op == "div": return Decimal("0") if args[1] == 0 else args[0] / args[1]
    if op == "min": return min(args)
    if op == "max": return max(args)
    if op == "abs": return abs(args[0])
    if op == "sqrt": return decimal_value(math.sqrt(max(float(args[0]), 0)))
    if op == "log1p": return decimal_value(math.log1p(max(float(args[0]), 0)))
    if op == "pow": return decimal_value(math.pow(float(args[0]), float(args[1])))
    if op == "clamp": return max(args[1], min(args[0], args[2]))
    if op == "delta": return args[0] - args[1]
    if op == "positive_delta": return max(Decimal("0"), args[0] - args[1])
    if op == "relative_delta": return Decimal("0") if args[1] == 0 else (args[0] - args[1]) / abs(args[1])
    if op == "ratio": return Decimal("0") if args[1] == 0 else args[0] / args[1]
    if op == "percentage": return Decimal("0") if args[1] == 0 else (args[0] / args[1]) * Decimal("100")
    raise ValidationError(f"Opération Recognition non supportée: {op!r}.")


def apply_curve(value, curve):
    value = max(Decimal("0"), decimal_value(value))
    curve = curve or {"kind": "LINEAR", "factor": 1}
    kind = curve.get("kind", "LINEAR")
    factor = decimal_value(curve.get("factor", 1))
    if kind == "LINEAR": return value * factor
    if kind == "LOG": return decimal_value(math.log1p(float(value))) * factor
    if kind == "SQRT": return decimal_value(math.sqrt(float(value))) * factor
    if kind == "POWER": return decimal_value(math.pow(float(value), float(curve.get("exponent", 1)))) * factor
    if kind == "PIECEWISE":
        result = Decimal("0"); remaining = value; previous = Decimal("0")
        for band in curve.get("bands", []):
            end = decimal_value(band.get("up_to", previous))
            width = max(Decimal("0"), min(remaining, end - previous))
            result += width * decimal_value(band.get("factor", 1)); remaining -= width; previous = end
            if remaining <= 0: break
        if remaining > 0: result += remaining * decimal_value(curve.get("tail_factor", 1))
        return result * factor
    raise ValidationError(f"Courbe Recognition non supportée: {kind!r}.")


def normalized_utility(rule, *, values, parameters, confidence=Decimal("1")):
    if not evaluate_condition(rule.conditions, values):
        return Decimal("0")
    measured = evaluate_expression(rule.measure, values, parameters)
    normalized = apply_curve(measured, rule.normalization or {"kind": "LINEAR", "factor": 1})
    result = apply_curve(normalized, rule.curve or {"kind": "LINEAR", "factor": 1})
    if "confidence" in (rule.modulators or []):
        result *= max(Decimal("0"), min(Decimal("1"), decimal_value(confidence)))
    for name in (rule.modulators or []):
        if name == "confidence":
            continue
        result *= max(Decimal("0"), decimal_value(values.get(name, 1)))
    return max(Decimal("0"), result)
