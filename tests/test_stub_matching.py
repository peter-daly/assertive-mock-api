from assertive import is_eq

from assertive_mock_api_server.core import (
    StubRepository,
    Stub,
    StubRequest,
    StubAction,
    StubResponse,
    MockApiRequest,
)


class TestStubMatching:
    def test_find_best_match_no_stubs(self):
        # Setup
        repo = StubRepository()
        request = MockApiRequest(
            path="/test",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        # Execute
        result = repo.find_best_match(request)

        # Assert
        assert result is None

    def test_find_best_match_perfect_match(self):
        # Setup
        repo = StubRepository()
        stub = Stub(
            request=StubRequest(path=is_eq("/test"), method=is_eq("GET")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="test")
            ),
        )
        repo.add(stub)
        request = MockApiRequest(
            path="/test",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        # Execute
        result = repo.find_best_match(request)

        # Assert
        assert result == stub

    def test_find_best_match_multiple_matches(self):
        # Setup
        repo = StubRepository()
        weak_stub = Stub(
            request=StubRequest(path=is_eq("/test")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="weak")
            ),
        )
        strong_stub = Stub(
            request=StubRequest(path=is_eq("/test"), method=is_eq("GET")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="strong")
            ),
        )
        repo.add(weak_stub)
        repo.add(strong_stub)
        request = MockApiRequest(
            path="/test",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        # Execute
        result = repo.find_best_match(request)

        # Assert
        assert result == strong_stub

    def test_match_count_beats_weighted_score(self):
        repo = StubRepository()
        high_weight_two_field_stub = Stub(
            request=StubRequest(path="/rank", method=is_eq("GET")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="high-weight")
            ),
        )
        high_count_three_field_stub = Stub(
            request=StubRequest(
                method=is_eq("GET"),
                headers=is_eq({"x-env": "test"}),
                query=is_eq({"page": "1"}),
            ),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="high-count")
            ),
        )
        repo.add(high_weight_two_field_stub)
        repo.add(high_count_three_field_stub)

        request = MockApiRequest(
            path="/rank",
            method="GET",
            headers={"x-env": "test"},
            body=None,
            host="localhost",
            query={"page": "1"},
        )

        result = repo.find_best_match(request)

        assert result == high_count_three_field_stub

    def test_weighted_score_breaks_tie_when_match_count_is_equal(self):
        repo = StubRepository()
        higher_weight_stub = Stub(
            request=StubRequest(path="/weights", host=is_eq("localhost")),
            action=StubAction(
                response=StubResponse(
                    status_code=200, headers={}, body="higher-weighted-score"
                )
            ),
        )
        lower_weight_stub = Stub(
            request=StubRequest(method=is_eq("GET"), body=is_eq("payload")),
            action=StubAction(
                response=StubResponse(
                    status_code=200, headers={}, body="lower-weighted-score"
                )
            ),
        )
        repo.add(higher_weight_stub)
        repo.add(lower_weight_stub)

        request = MockApiRequest(
            path="/weights",
            method="GET",
            headers={},
            body="payload",
            host="localhost",
            query={},
        )

        result = repo.find_best_match(request)

        assert result == higher_weight_stub

    def test_find_best_match_reached_max_calls(self):
        # Setup
        repo = StubRepository()
        stub = Stub(
            request=StubRequest(path=is_eq("/test")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="test")
            ),
            max_calls=1,
        )
        repo.add(stub)
        request = MockApiRequest(
            path="/test",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        # First call uses up the max_calls
        first_result = repo.find_best_match(request)

        # Execute second call
        second_result = repo.find_best_match(request)

        # Assert
        assert first_result == stub
        assert second_result is None

    def test_find_best_match_no_matching_stubs(self):
        # Setup
        repo = StubRepository()
        stub = Stub(
            request=StubRequest(path=is_eq("/other-path")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="test")
            ),
        )
        repo.add(stub)
        request = MockApiRequest(
            path="/test",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        # Execute
        result = repo.find_best_match(request)

        # Assert
        assert result is None

    def test_catch_all_is_weakest_positive_match(self):
        repo = StubRepository()
        catch_all_stub = Stub(
            request=StubRequest(),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="catch-all")
            ),
        )
        specific_stub = Stub(
            request=StubRequest(path="/only-this"),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="specific")
            ),
        )
        repo.add(catch_all_stub)
        repo.add(specific_stub)

        specific_request = MockApiRequest(
            path="/only-this",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )
        catch_all_request = MockApiRequest(
            path="/somewhere-else",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        assert repo.find_best_match(specific_request) == specific_stub
        assert repo.find_best_match(catch_all_request) == catch_all_stub

    def test_stubs_have_unique_ids(self):
        repo = StubRepository()
        stub_a = Stub(
            request=StubRequest(path=is_eq("/a")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="a")
            ),
        )
        stub_b = Stub(
            request=StubRequest(path=is_eq("/b")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="b")
            ),
        )

        repo.add(stub_a)
        repo.add(stub_b)

        assert stub_a.stub_id != stub_b.stub_id
        assert bool(stub_a.stub_id)
        assert bool(stub_b.stub_id)

    def test_delete_by_id_removes_stub(self):
        repo = StubRepository()
        stub = Stub(
            request=StubRequest(path=is_eq("/to-delete")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="gone")
            ),
        )
        repo.add(stub)

        assert repo.delete_by_id(stub.stub_id) is True
        assert (
            repo.find_best_match(
                MockApiRequest(
                    path="/to-delete",
                    method="GET",
                    headers={},
                    body=None,
                    host="localhost",
                    query={},
                )
            )
            is None
        )

    def test_delete_by_id_returns_false_for_missing_stub(self):
        repo = StubRepository()
        assert repo.delete_by_id("missing-stub-id") is False

    def test_static_path_out_ranks_parameterized_path_on_tie(self):
        repo = StubRepository()
        parameterized_stub = Stub(
            request=StubRequest(path="/users/{id}", method=is_eq("GET")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="parameterized")
            ),
        )
        static_stub = Stub(
            request=StubRequest(path="/users/me", method=is_eq("GET")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="static")
            ),
        )
        repo.add(parameterized_stub)
        repo.add(static_stub)

        request = MockApiRequest(
            path="/users/me",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        result = repo.find_best_match(request)

        assert result == static_stub

    def test_criteria_backed_path_matcher_still_matches(self):
        repo = StubRepository()
        stub = Stub(
            request=StubRequest(path=is_eq("/criteria-path")),
            action=StubAction(
                response=StubResponse(status_code=200, headers={}, body="criteria")
            ),
        )
        repo.add(stub)

        request = MockApiRequest(
            path="/criteria-path",
            method="GET",
            headers={},
            body=None,
            host="localhost",
            query={},
        )

        result = repo.find_best_match(request)

        assert result == stub
