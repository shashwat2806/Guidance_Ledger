import httpx

from core.ingestion.sec_client import SECClient


def test_caches_response_and_skips_second_request(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"cik": "0000320193"})

    client = SECClient(user_agent="Test test@example.com", transport=httpx.MockTransport(handler))
    url = "https://data.sec.gov/submissions/CIK0000320193.json"

    first = client.get(url)
    second = client.get(url)

    assert first == {"cik": "0000320193"}
    assert second == first
    assert len(calls) == 1


def test_sends_configured_user_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def handler(request):
        seen["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, json={})

    client = SECClient(
        user_agent="Shashwat Mishra test@example.com",
        transport=httpx.MockTransport(handler),
    )
    client.get("https://data.sec.gov/submissions/CIK0000320193.json")

    assert seen["user_agent"] == "Shashwat Mishra test@example.com"


def test_retries_on_429_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("core.ingestion.sec_client.time.sleep", lambda s: None)
    responses = [httpx.Response(429), httpx.Response(200, json={"ok": True})]

    def handler(request):
        return responses.pop(0)

    client = SECClient(user_agent="Test test@example.com", transport=httpx.MockTransport(handler))
    result = client.get("https://data.sec.gov/submissions/CIK0000320193.json")

    assert result == {"ok": True}
