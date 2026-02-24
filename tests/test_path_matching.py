from assertive import is_eq

from assertive_mock_api_server.path_matching import (
    CriteriaPathMatcher,
    PatternPathMatcher,
    ensure_path_matcher,
)


def test_pattern_path_matcher_static_exact_match():
    matcher = PatternPathMatcher(pattern="/users/me")

    result = matcher.match("/users/me")

    assert result.matched is True
    assert result.params == {}
    assert result.specificity == 2


def test_pattern_path_matcher_extracts_named_params():
    matcher = PatternPathMatcher(pattern="/users/{id}")

    result = matcher.match("/users/42")

    assert result.matched is True
    assert result.params == {"id": "42"}
    assert result.specificity == 1


def test_pattern_path_matcher_rejects_segment_count_mismatch():
    matcher = PatternPathMatcher(pattern="/users/{id}")

    result = matcher.match("/users/42/details")

    assert result.matched is False


def test_pattern_path_matcher_rejects_literal_mismatch():
    matcher = PatternPathMatcher(pattern="/users/{id}")

    result = matcher.match("/orders/42")

    assert result.matched is False


def test_pattern_path_matcher_specificity_counts_literal_segments():
    matcher = PatternPathMatcher(pattern="/users/{id}/posts/{post_id}")

    result = matcher.match("/users/1/posts/9")

    assert result.matched is True
    assert result.specificity == 2


def test_ensure_path_matcher_builds_criteria_matcher_for_criteria():
    matcher = ensure_path_matcher(is_eq("/health"))

    assert isinstance(matcher, CriteriaPathMatcher)
    assert matcher.match("/health").matched is True
    assert matcher.match("/healthz").matched is False
