from __future__ import annotations

import re
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .contracts import RequirementEvaluationResult


_EVALUATOR_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")
_METADATA_CODE_RE = re.compile(r"^[a-z][a-z0-9_.:-]*$")


class RequirementRegistryError(ValueError):
    pass


class RequirementConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluatorParameter:
    expected_type: type | tuple[type, ...]
    required: bool = True
    validator: Callable[[Any], bool] | None = None

    def __post_init__(self):
        expected = self.expected_type if isinstance(self.expected_type, tuple) else (self.expected_type,)
        if not expected or any(not isinstance(item, type) for item in expected):
            raise RequirementRegistryError("EvaluatorParameter.expected_type must contain Python types.")
        if type(self.required) is not bool:
            raise RequirementRegistryError("EvaluatorParameter.required must be a boolean.")
        if self.validator is not None and not callable(self.validator):
            raise RequirementRegistryError("EvaluatorParameter.validator must be callable.")


@dataclass(frozen=True)
class EvaluatorDefinition:
    key: str
    evaluator: Callable[[Any, Mapping[str, Any]], RequirementEvaluationResult]
    supported_subject_type: type | tuple[type, ...]
    parameter_schema: Mapping[str, EvaluatorParameter] = field(default_factory=dict)
    result_type: type = RequirementEvaluationResult
    operators: tuple[str, ...] = ()
    dependency_events: tuple[str, ...] = ()
    cache_policy: str = "none"

    def __post_init__(self):
        if not isinstance(self.key, str) or not _EVALUATOR_KEY_RE.fullmatch(self.key):
            raise RequirementRegistryError("Evaluator key must be a stable lowercase code.")
        if not callable(self.evaluator):
            raise RequirementRegistryError("Evaluator must be callable.")
        subject_types = self.supported_subject_type if isinstance(self.supported_subject_type, tuple) else (self.supported_subject_type,)
        if not subject_types or any(not isinstance(item, type) for item in subject_types):
            raise RequirementRegistryError("supported_subject_type must contain Python types.")
        if not isinstance(self.parameter_schema, Mapping):
            raise RequirementRegistryError("parameter_schema must be a mapping.")
        for name, parameter in self.parameter_schema.items():
            if not isinstance(name, str) or not _EVALUATOR_KEY_RE.fullmatch(name):
                raise RequirementRegistryError("Evaluator parameter names must be stable lowercase codes.")
            if not isinstance(parameter, EvaluatorParameter):
                raise RequirementRegistryError("parameter_schema values must be EvaluatorParameter instances.")
        if not isinstance(self.result_type, type) or not issubclass(self.result_type, RequirementEvaluationResult):
            raise RequirementRegistryError("result_type must be RequirementEvaluationResult or a subclass.")
        if len(set(self.operators)) != len(self.operators) or any(not isinstance(value, str) or not value for value in self.operators):
            raise RequirementRegistryError("operators must contain unique non-empty strings.")
        if len(set(self.dependency_events)) != len(self.dependency_events) or any(
            not isinstance(value, str) or not _METADATA_CODE_RE.fullmatch(value) for value in self.dependency_events
        ):
            raise RequirementRegistryError("dependency_events must contain unique stable event codes.")
        if not isinstance(self.cache_policy, str) or not _METADATA_CODE_RE.fullmatch(self.cache_policy):
            raise RequirementRegistryError("cache_policy must be a stable code string.")
        object.__setattr__(self, "parameter_schema", MappingProxyType(dict(self.parameter_schema)))
        object.__setattr__(self, "operators", tuple(self.operators))
        object.__setattr__(self, "dependency_events", tuple(self.dependency_events))


def _strict_type_matches(value: Any, expected: type | tuple[type, ...]) -> bool:
    expected_types = expected if isinstance(expected, tuple) else (expected,)
    for expected_type in expected_types:
        if expected_type in {bool, int, float, str}:
            if type(value) is expected_type:
                return True
        elif isinstance(value, expected_type):
            return True
    return False


class EvaluatorRegistry:
    def __init__(self):
        self._definitions: dict[str, EvaluatorDefinition] = {}
        self._lock = RLock()

    def register(self, definition: EvaluatorDefinition) -> EvaluatorDefinition:
        if not isinstance(definition, EvaluatorDefinition):
            raise RequirementRegistryError("Only EvaluatorDefinition instances can be registered.")
        with self._lock:
            if definition.key in self._definitions:
                raise RequirementRegistryError(f"Evaluator already registered: {definition.key}")
            self._definitions[definition.key] = definition
        return definition

    def get(self, key: str) -> EvaluatorDefinition:
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise RequirementRegistryError(f"Unknown evaluator: {key}") from exc

    def validate_config(self, key: str, config: Mapping[str, Any], *, subject: Any = None) -> dict[str, Any]:
        definition = self.get(key)
        if not isinstance(config, Mapping):
            raise RequirementConfigurationError("Evaluator configuration must be a mapping.")
        if subject is not None and not isinstance(subject, definition.supported_subject_type):
            raise RequirementConfigurationError("Evaluator subject type is not supported.")

        allowed_keys = set(definition.parameter_schema)
        if definition.operators:
            allowed_keys.add("operator")
        unknown = set(config) - allowed_keys
        if unknown:
            raise RequirementConfigurationError(f"Unknown evaluator configuration keys: {', '.join(sorted(unknown))}")

        if definition.operators:
            if "operator" not in config:
                raise RequirementConfigurationError("Evaluator operator is required.")
            if config["operator"] not in definition.operators:
                raise RequirementConfigurationError("Evaluator operator is not supported.")
        elif "operator" in config:
            raise RequirementConfigurationError("This evaluator does not accept an operator.")

        normalized = dict(config)
        for name, parameter in definition.parameter_schema.items():
            if name not in config:
                if parameter.required:
                    raise RequirementConfigurationError(f"Missing evaluator configuration key: {name}")
                continue
            value = config[name]
            if not _strict_type_matches(value, parameter.expected_type):
                raise RequirementConfigurationError(f"Invalid type for evaluator configuration key: {name}")
            if parameter.validator is not None and not parameter.validator(value):
                raise RequirementConfigurationError(f"Invalid value for evaluator configuration key: {name}")
        return normalized

    def evaluate(self, key: str, *, subject: Any, config: Mapping[str, Any]) -> RequirementEvaluationResult:
        definition = self.get(key)
        normalized = self.validate_config(key, config, subject=subject)
        result = definition.evaluator(subject, normalized)
        if not isinstance(result, definition.result_type):
            raise RequirementRegistryError("Evaluator returned an invalid result type.")
        return result


registry = EvaluatorRegistry()
