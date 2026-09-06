import httpx
import pytest

from ran2wiki.sync import client as client_module
from ran2wiki.sync.client import RepositoryClient


class FakeHTTP:
    def __init__(self, statuses: list[int]) -> None:
        self.statuses = statuses
        self.calls = 0

    def get(self, url: str) -> httpx.Response:
        status = self.statuses[min(self.calls, len(self.statuses) - 1)]
        self.calls += 1
        return httpx.Response(status, content=b"ok", request=httpx.Request("GET", url))


def test_fetch_retries_server_error(monkeypatch) -> None:
    client = RepositoryClient()
    fake = FakeHTTP([522, 200])
    client.http.close()
    client.http = fake  # type: ignore[assignment]
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    assert client.fetch("https://example.test/file") == b"ok"
    assert fake.calls == 2


def test_fetch_does_not_retry_not_found(monkeypatch) -> None:
    client = RepositoryClient()
    fake = FakeHTTP([404])
    client.http.close()
    client.http = fake  # type: ignore[assignment]
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch("https://example.test/missing")
    assert fake.calls == 1


def test_fetch_retries_incomplete_transport_response(monkeypatch) -> None:
    client = RepositoryClient()
    calls = 0

    def get(url: str) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.RemoteProtocolError("incomplete body")
        return httpx.Response(200, content=b"complete", request=httpx.Request("GET", url))

    client.http.get = get  # type: ignore[method-assign]
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    assert client.fetch("https://example.test/file") == b"complete"
    assert calls == 2
    client.close()
