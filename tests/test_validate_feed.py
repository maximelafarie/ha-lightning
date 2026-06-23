import pytest
import asyncio

from custom_components.ha_lightning import config_flow


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def json(self):
        # simulate async json reading
        return self._payload


class FakeRespCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, timeout=10):
        return FakeRespCtx(FakeResp(self._payload, status=self._status))


@pytest.mark.asyncio
async def test_validate_feed_success(monkeypatch):
    payload = [{"latitude": 10.0, "longitude": 20.0, "time": 1234567890}]

    def fake_client_session():
        return FakeSession(payload)

    monkeypatch.setattr(config_flow.aiohttp, "ClientSession", fake_client_session)

    # should not raise
    await config_flow.async_validate_feed(None, "http://example.invalid/feed.json")


@pytest.mark.asyncio
async def test_validate_feed_non_json(monkeypatch):
    # simulate response json raising
    class BadResp(FakeResp):
        async def json(self):
            raise Exception("not json")

    class BadRespCtx(FakeRespCtx):
        def __init__(self):
            super().__init__(BadResp(None))

    class BadSession(FakeSession):
        def get(self, url, timeout=10):
            return BadRespCtx()

    def bad_client_session():
        return BadSession(None)

    monkeypatch.setattr(config_flow.aiohttp, "ClientSession", bad_client_session)

    with pytest.raises(ValueError):
        await config_flow.async_validate_feed(None, "http://example.invalid/feed.json")


@pytest.mark.asyncio
async def test_validate_feed_missing_fields(monkeypatch):
    # payload missing lat/lon/time
    payload = [{"x": 1}]

    def fake_client_session():
        return FakeSession(payload)

    monkeypatch.setattr(config_flow.aiohttp, "ClientSession", fake_client_session)

    with pytest.raises(ValueError):
        await config_flow.async_validate_feed(None, "http://example.invalid/feed.json")
