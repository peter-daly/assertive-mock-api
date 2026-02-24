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
