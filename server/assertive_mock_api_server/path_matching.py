from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from assertive import Criteria, ensure_criteria
from assertive.serialize import deserialize, serialize

_PARAM_SEGMENT_PATTERN = re.compile(r"^\{([^{}]+)\}$")


@dataclass(frozen=True)
class PathMatchResult:
    matched: bool
    params: dict[str, str] = field(default_factory=dict)
    specificity: int = 0

    @staticmethod
    def no_match() -> "PathMatchResult":
        return PathMatchResult(matched=False, params={}, specificity=0)


class PathMatcher(ABC):
    @abstractmethod
    def match(self, path: str) -> PathMatchResult:
        raise NotImplementedError


@dataclass(frozen=True)
class PatternPathMatcher(PathMatcher):
    pattern: str

    def match(self, path: str) -> PathMatchResult:
        pattern_segments = _split_path(self.pattern)
        path_segments = _split_path(path)

        if len(pattern_segments) != len(path_segments):
            return PathMatchResult.no_match()

        params: dict[str, str] = {}
        specificity = 0

        for pattern_segment, path_segment in zip(pattern_segments, path_segments):
            if parameter := _extract_parameter_name(pattern_segment):
                params[parameter] = path_segment
                continue

            if pattern_segment != path_segment:
                return PathMatchResult.no_match()

            if pattern_segment:
                specificity += 1

        return PathMatchResult(matched=True, params=params, specificity=specificity)


@dataclass(frozen=True)
class CriteriaPathMatcher(PathMatcher):
    criteria: Criteria

    def match(self, path: str) -> PathMatchResult:
        if path != self.criteria:
            return PathMatchResult.no_match()
        return PathMatchResult(matched=True, params={}, specificity=0)


def ensure_path_matcher(
    value: str | dict | Criteria | PathMatcher,
) -> PathMatcher:
    if isinstance(value, PathMatcher):
        return value

    if isinstance(value, str):
        return PatternPathMatcher(pattern=value)

    deserialized = deserialize(value)
    if isinstance(deserialized, str):
        return PatternPathMatcher(pattern=deserialized)

    return CriteriaPathMatcher(criteria=ensure_criteria(deserialized))


def serialize_path_matcher(path_matcher: PathMatcher) -> str | dict:
    if isinstance(path_matcher, PatternPathMatcher):
        return path_matcher.pattern
    if isinstance(path_matcher, CriteriaPathMatcher):
        return serialize(path_matcher.criteria)
    raise TypeError(f"Unsupported path matcher type: {type(path_matcher)!r}")


def _split_path(path: str) -> list[str]:
    stripped = path.strip("/")
    if not stripped:
        return []
    return stripped.split("/")


def _extract_parameter_name(segment: str) -> str | None:
    match = _PARAM_SEGMENT_PATTERN.fullmatch(segment)
    if match is None:
        return None
    return match.group(1)
