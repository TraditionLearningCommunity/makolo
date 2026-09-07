from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from .signal_contracts import COUNT, DATETIME, DURATION, MONEY, NUMBER, NUMERIC_TYPES, RATIO, allowed_fields, field_type, uses_money_field


ALLOWED_OPS = {
    "const", "field", "param", "add", "sub", "mul", "div", "min", "max", "abs",
    "sqrt", "log1p", "pow", "clamp", "delta", "positive_delta", "relative_delta",
    "ratio", "percentage", "if", "duration_between", "days_between", "hours_between",
    "time_until", "time_since", "linear_decay", "exponential_decay",
}
ALLOWED_AGGREGATIONS = {"SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX", "DELTA", "SUM_DISTINCT_OUTCOME", "LATEST_STATE"}
ALLOWED_CURVES = {"LINEAR", "LOG", "SQRT", "POWER", "PIECEWISE"}
ALLOWED_MODULATORS = {"confidence", "scarcity", "reliability", "maturity", "anti_abuse", "temporal_factor"}
ALLOWED_ATTRIBUTION_STRATEGIES = {"signal_contributors", "profile_only", "space_only", "unattributed"}
ALLOWED_COMBINATIONS = {"additive", "exclusive", "max"}
STATEFUL_AGGREGATIONS = {"LATEST_STATE", "MAX", "MIN"}
EXPRESSION_TYPES = set(NUMERIC_TYPES) | {DATETIME}


def decimal_value(value):
    if isinstance(value, Decimal): return value
    try: result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc: raise ValidationError(f"Valeur Recognition invalide: {value!r}.") from exc
    if not result.is_finite(): raise ValidationError("Une valeur Recognition doit être finie.")
    return result


def datetime_value(value):
    if isinstance(value, datetime):
        result = value
    else:
        try: result = datetime.fromisoformat(str(value))
        except (TypeError, ValueError) as exc: raise ValidationError(f"Date Recognition invalide: {value!r}.") from exc
    if timezone.is_naive(result): result = timezone.make_aware(result, timezone.get_current_timezone())
    return result


def _collect_expression_fields(expression, result):
    if expression in ({}, None, []) or not isinstance(expression, dict): return
    if expression.get("op") == "field" and expression.get("name"): result.add(str(expression["name"]))
    for child in expression.get("args", []): _collect_expression_fields(child, result)
    for key in ("then", "else"):
        child = expression.get(key)
        if isinstance(child, dict): _collect_expression_fields(child, result)


def _declared_type(expression, default=NUMBER):
    kind = str((expression or {}).get("type") or default)
    if kind not in EXPRESSION_TYPES: raise ValidationError({"measure": f"Type Recognition inconnu: {kind!r}."})
    return kind


def _require_same(types, op):
    unique = set(types)
    if len(unique) != 1: raise ValidationError({"measure": f"{op} exige des grandeurs de même type, reçu: {', '.join(sorted(unique))}."})
    return types[0]


def _expression_type(expression, *, signal_kind):
    if not isinstance(expression, dict) or not expression: raise ValidationError("Une expression Recognition doit être déclarative.")
    op = expression.get("op")
    if op not in ALLOWED_OPS: raise ValidationError(f"Opération Recognition non autorisée: {op!r}.")
    if op in {"const", "param"}: return _declared_type(expression)
    if op == "field":
        name = str(expression.get("name") or "")
        if name not in allowed_fields(signal_kind): raise ValidationError({"measure": f"Le champ {name!r} n'est pas exposé par le contrat Signal {signal_kind}."})
        kind = field_type(signal_kind, name)
        if kind not in EXPRESSION_TYPES: raise ValidationError({"measure": f"Le champ {name!r} ne peut pas entrer dans cette formule."})
        return kind
    if op == "if":
        _validate_condition(expression.get("condition", {}), signal_kind=signal_kind)
        return _require_same((_expression_type(expression.get("then"), signal_kind=signal_kind), _expression_type(expression.get("else"), signal_kind=signal_kind)), "if")

    args = expression.get("args", [])
    if not isinstance(args, list) or not args: raise ValidationError({"measure": f"L'opération {op} exige des arguments."})
    types = [_expression_type(child, signal_kind=signal_kind) for child in args]
    if op in {"add", "sub", "min", "max", "clamp"}:
        result = _require_same(types, op)
        if result == DATETIME: raise ValidationError({"measure": f"{op} n'opère pas directement sur DATETIME ; utilisez les fonctions temporelles explicites."})
        return result
    if op == "abs":
        if types[0] == DATETIME: raise ValidationError({"measure": "abs n'accepte pas DATETIME."})
        return types[0]
    if op == "mul":
        if DATETIME in types: raise ValidationError({"measure": "Une date ne peut pas être multipliée."})
        dimensional = [kind for kind in types if kind not in {NUMBER, RATIO}]
        if len(dimensional) > 1: raise ValidationError({"measure": "Une multiplication ne peut combiner deux grandeurs dimensionnées."})
        return dimensional[0] if dimensional else NUMBER
    if op == "div":
        if len(types) != 2 or DATETIME in types: raise ValidationError({"measure": "div exige deux grandeurs numériques compatibles."})
        left, right = types
        if right in {NUMBER, RATIO}: return left
        if left == right: return NUMBER
        raise ValidationError({"measure": f"Division incompatible: {left} / {right}."})
    if op in {"sqrt", "log1p", "pow"}:
        if any(kind not in {NUMBER, COUNT, RATIO} for kind in types): raise ValidationError({"measure": f"{op} n'accepte que NUMBER/COUNT/RATIO."})
        return NUMBER
    if op in {"delta", "positive_delta"}:
        result = _require_same(types, op)
        if result == DATETIME: raise ValidationError({"measure": f"{op} sur des dates doit utiliser duration_between/time_since/time_until."})
        return result
    if op in {"relative_delta", "ratio", "percentage"}:
        if len(types) != 2 or types[0] != types[1] or DATETIME in types: raise ValidationError({"measure": f"{op} exige deux grandeurs numériques de même type."})
        return RATIO
    if op in {"duration_between", "days_between", "hours_between", "time_until", "time_since"}:
        if len(types) != 2 or any(kind != DATETIME for kind in types): raise ValidationError({"measure": f"{op} exige exactement deux DATETIME explicites."})
        return DURATION if op in {"duration_between", "time_until", "time_since"} else NUMBER
    if op in {"linear_decay", "exponential_decay"}:
        if len(types) != 3 or types[0] == DATETIME or types[1] != types[2] or types[1] not in {NUMBER, DURATION}:
            raise ValidationError({"measure": f"{op} attend value, age, horizon/half_life avec des unités temporelles compatibles."})
        return types[0]
    raise ValidationError(f"Opération Recognition non supportée: {op!r}.")


def _validate_condition(condition, *, signal_kind):
    if not condition: return
    if not isinstance(condition, dict): raise ValidationError("Une condition Recognition doit être déclarative.")
    for key in ("all", "any"):
        if key in condition:
            rows = condition[key]
            if not isinstance(rows, list): raise ValidationError(f"La condition {key} attend une liste.")
            for row in rows: _validate_condition(row, signal_kind=signal_kind)
            return
    if "not" in condition:
        _validate_condition(condition["not"], signal_kind=signal_kind); return
    name = str(condition.get("field") or "")
    if name not in allowed_fields(signal_kind): raise ValidationError({"conditions": f"Le champ {name!r} n'est pas exposé par le contrat Signal {signal_kind}."})
    operator = condition.get("op", "eq")
    if operator not in {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "not_null"}: raise ValidationError(f"Condition Recognition non supportée: {operator!r}.")
    if operator in {"gt", "gte", "lt", "lte"} and field_type(signal_kind, name) not in (set(NUMERIC_TYPES) | {DATETIME}): raise ValidationError({"conditions": f"La comparaison {operator} exige un champ numérique ou DATETIME."})


def _condition_has_currency_pin(condition):
    if not isinstance(condition, dict) or not condition: return False
    if condition.get("field") == "currency" and condition.get("op", "eq") == "eq" and condition.get("value"): return True
    return any(_condition_has_currency_pin(row) for key in ("all", "any") for row in condition.get(key, []) if isinstance(row, dict))


def validate_rule_definition(rule):
    signal_kind = (rule.signal_kind or "").strip()
    if not signal_kind: raise ValidationError({"signal_kind": "Le Signal est obligatoire."})
    if not allowed_fields(signal_kind): raise ValidationError({"signal_kind": "Ce Signal n'est pas exposé au moteur Recognition."})
    if getattr(rule, "channel", "") == "utility": raise ValidationError({"channel": "utility est réservé au pool interne de l'objet et ne peut pas être configuré par une Rule."})
    _validate_condition(rule.scope or {}, signal_kind=signal_kind); _validate_condition(rule.conditions or {}, signal_kind=signal_kind)
    _expression_type(rule.measure, signal_kind=signal_kind)
    if rule.aggregation not in ALLOWED_AGGREGATIONS: raise ValidationError({"aggregation": "Agrégation Recognition non autorisée."})
    if getattr(rule, "temporal_profile", "") in {"stock", "transition"} and rule.aggregation not in STATEFUL_AGGREGATIONS: raise ValidationError({"aggregation": "STOCK/TRANSITION attend une valeur d'état (LATEST_STATE, MAX ou MIN), pas un cumul d'outcomes."})
    curve_kind = (rule.curve or {}).get("kind", "LINEAR"); normalization_kind = (rule.normalization or {}).get("kind", "LINEAR")
    if curve_kind not in ALLOWED_CURVES: raise ValidationError({"curve": "Courbe Recognition non autorisée."})
    if normalization_kind not in ALLOWED_CURVES: raise ValidationError({"normalization": "Normalisation Recognition non autorisée."})
    unknown = set(rule.modulators or []) - ALLOWED_MODULATORS
    if unknown: raise ValidationError({"modulators": f"Modulateurs inconnus: {', '.join(sorted(unknown))}."})
    if getattr(rule, "combination", "additive") not in ALLOWED_COMBINATIONS: raise ValidationError({"combination": "Mode de combinaison Recognition inconnu."})
    attribution = rule.attribution or {}; strategy = attribution.get("strategy", "signal_contributors")
    if strategy not in ALLOWED_ATTRIBUTION_STRATEGIES: raise ValidationError({"attribution": "Stratégie d'attribution Recognition inconnue."})
    recognized_fraction = decimal_value(attribution.get("recognized_fraction", 1))
    if recognized_fraction < 0 or recognized_fraction > 1: raise ValidationError({"attribution": "recognized_fraction doit être comprise entre 0 et 1."})
    identity = rule.outcome_identity or {}
    if identity and identity != {"source": "signal.outcome_identity"}: raise ValidationError({"outcome_identity": "v1 utilise uniquement l'identité canonique signal.outcome_identity."})
    fields = set(); _collect_expression_fields(rule.measure, fields)
    if uses_money_field(signal_kind, fields) and not (_condition_has_currency_pin(rule.scope or {}) or _condition_has_currency_pin(rule.conditions or {})):
        raise ValidationError({"conditions": "Une formule monétaire doit fixer explicitement currency ; aucun FX implicite n'est autorisé."})


def evaluate_condition(condition, values):
    if not condition: return True
    if "all" in condition: return all(evaluate_condition(item, values) for item in condition["all"])
    if "any" in condition: return any(evaluate_condition(item, values) for item in condition["any"])
    if "not" in condition: return not evaluate_condition(condition["not"], values)
    field = condition.get("field"); operator = condition.get("op", "eq"); expected = condition.get("value"); actual = values.get(field)
    if isinstance(actual, datetime):
        try: expected = datetime_value(expected) if expected is not None else None
        except ValidationError: return False
    elif operator in {"gt", "gte", "lt", "lte"}:
        try: actual = decimal_value(actual); expected = decimal_value(expected)
        except ValidationError: return False
    if operator == "eq": return actual == expected
    if operator == "ne": return actual != expected
    if operator == "gt": return actual > expected
    if operator == "gte": return actual >= expected
    if operator == "lt": return actual < expected
    if operator == "lte": return actual <= expected
    if operator == "in": return actual in (expected or [])
    if operator == "not_in": return actual not in (expected or [])
    if operator == "is_null": return actual is None
    if operator == "not_null": return actual is not None
    raise ValidationError(f"Condition Recognition non supportée: {operator!r}.")


def _leaf_value(expression, source):
    kind = _declared_type(expression)
    raw = source
    return datetime_value(raw) if kind == DATETIME else decimal_value(raw)


def evaluate_expression(expression, values, parameters):
    if not expression: return Decimal("0")
    op = expression.get("op")
    if op == "const": return _leaf_value(expression, expression.get("value", 0))
    if op == "field":
        raw = values.get(expression.get("name"), expression.get("default", 0)); kind = field_type(values.get("__signal_kind__", ""), expression.get("name"))
        return datetime_value(raw) if kind == DATETIME else decimal_value(raw)
    if op == "param": return _leaf_value(expression, parameters.get(expression.get("name"), expression.get("default", 0)))
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
    if op in {"duration_between", "days_between", "hours_between", "time_until", "time_since"}:
        first, second = args
        if op in {"duration_between", "days_between", "hours_between"}: seconds = Decimal(str((second - first).total_seconds()))
        elif op == "time_until": seconds = Decimal(str((first - second).total_seconds()))
        else: seconds = Decimal(str((second - first).total_seconds()))
        if op == "days_between": return seconds / Decimal("86400")
        if op == "hours_between": return seconds / Decimal("3600")
        return seconds
    if op == "linear_decay":
        value, age, horizon = args
        if horizon <= 0: return Decimal("0")
        factor = max(Decimal("0"), Decimal("1") - max(Decimal("0"), age) / horizon)
        return value * factor
    if op == "exponential_decay":
        value, age, half_life = args
        if half_life <= 0: return Decimal("0")
        factor = decimal_value(math.pow(0.5, float(max(Decimal("0"), age) / half_life)))
        return value * factor
    raise ValidationError(f"Opération Recognition non supportée: {op!r}.")


def apply_curve(value, curve):
    value = max(Decimal("0"), decimal_value(value)); curve = curve or {"kind": "LINEAR", "factor": 1}; kind = curve.get("kind", "LINEAR"); factor = decimal_value(curve.get("factor", 1))
    if kind == "LINEAR": return value * factor
    if kind == "LOG": return decimal_value(math.log1p(float(value))) * factor
    if kind == "SQRT": return decimal_value(math.sqrt(float(value))) * factor
    if kind == "POWER": return decimal_value(math.pow(float(value), float(curve.get("exponent", 1)))) * factor
    if kind == "PIECEWISE":
        result = Decimal("0"); remaining = value; previous = Decimal("0")
        for band in curve.get("bands", []):
            end = decimal_value(band.get("up_to", previous)); width = max(Decimal("0"), min(remaining, end - previous)); result += width * decimal_value(band.get("factor", 1)); remaining -= width; previous = end
            if remaining <= 0: break
        if remaining > 0: result += remaining * decimal_value(curve.get("tail_factor", 1))
        return result * factor
    raise ValidationError(f"Courbe Recognition non supportée: {kind!r}.")


def measure_value(rule, *, values, parameters):
    context = dict(values or {}); context["__signal_kind__"] = rule.signal_kind
    if not evaluate_condition(rule.scope, context) or not evaluate_condition(rule.conditions, context): return None
    return evaluate_expression(rule.measure, context, parameters)


def finalize_utility(rule, *, aggregate_value, confidence=Decimal("1"), modulator_values=None):
    normalized = apply_curve(aggregate_value, rule.normalization or {"kind": "LINEAR", "factor": 1}); result = apply_curve(normalized, rule.curve or {"kind": "LINEAR", "factor": 1})
    if "confidence" in (rule.modulators or []): result *= max(Decimal("0"), min(Decimal("1"), decimal_value(confidence)))
    modulator_values = modulator_values or {}
    for name in (rule.modulators or []):
        if name != "confidence": result *= max(Decimal("0"), decimal_value(modulator_values.get(name, 1)))
    return max(Decimal("0"), result)


def normalized_utility(rule, *, values, parameters, confidence=Decimal("1")):
    measured = measure_value(rule, values=values, parameters=parameters)
    return Decimal("0") if measured is None else finalize_utility(rule, aggregate_value=measured, confidence=confidence, modulator_values=values)
