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
