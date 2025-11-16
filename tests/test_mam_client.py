import json
from urllib.parse import parse_qs, urlparse

import pytest

from mamlarr_service.mam_client import MyAnonamouseClient
from mamlarr_service.settings import MamServiceSettings

from .fixtures import JACKETT_AUDIOBOOK


class _MockResponse:
    def __init__(self, url: str, payload: dict, status: int = 200):
        self.url = url
        self.status = status
        self.reason = "OK"
        self._payload = payload

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    async def text(self) -> str:
        return json.dumps(self._payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingSession:
    def __init__(self, payload: dict | None = None):
        self._payload = payload or {"data": []}
        self.calls: list[dict] = []

    def get(self, url: str, cookies: dict):
        self.calls.append({"url": url, "cookies": cookies})
        return _MockResponse(url, self._payload)


@pytest.mark.asyncio
async def test_search_builds_query_params(monkeypatch):
    session = RecordingSession({"data": []})
    settings = MamServiceSettings(
        mam_base_url="https://mam.test",
        mam_session_id="abc123",
        search_in_description=True,
        search_in_series=False,
        search_in_filenames=True,
        search_languages=[99],
        use_mock_data=False,
    )
    client = MyAnonamouseClient(session, settings)

    def fake_tracker_categories(categories):
        assert categories == [3000, 7000]
        return [13, 71]

    monkeypatch.setattr(
        "mamlarr_service.mam_client.tracker_categories_for_torznab",
        fake_tracker_categories,
    )

    await client.search(
        "   Example -- Query  ",
        limit=25,
        offset=50,
        categories=[3000, 7000],
        languages=[42, "invalid"],
    )

    assert len(session.calls) == 1
    captured = session.calls[0]
    assert captured["cookies"] == {"mam_id": "abc123"}

    parsed = parse_qs(urlparse(captured["url"]).query)
    assert parsed["tor[text]"] == ["Example Query"]
    assert parsed["tor[perpage]"] == ["25"]
    assert parsed["tor[startNumber]"] == ["50"]
    assert parsed["tor[srchIn][description]"] == ["true"]
    assert parsed["tor[srchIn][filenames]"] == ["true"]
    assert "tor[srchIn][series]" not in parsed
    assert parsed["tor[browse_lang][0]"] == ["42"]
    assert "tor[browse_lang][1]" not in parsed
    assert parsed["tor[cat][0]"] == ["13"]
    assert parsed["tor[cat][1]"] == ["71"]
    assert "tor[cat][]" not in parsed


@pytest.mark.asyncio
async def test_search_defaults_to_configured_category(monkeypatch):
    session = RecordingSession({"data": []})
    settings = MamServiceSettings(
        mam_base_url="https://mam.test",
        mam_session_id="cookie",
        search_category_id=77,
        use_mock_data=False,
    )
    client = MyAnonamouseClient(session, settings)

    monkeypatch.setattr(
        "mamlarr_service.mam_client.tracker_categories_for_torznab",
        lambda categories: [],
    )

    await client.search("test query", categories=[])

    parsed = parse_qs(urlparse(session.calls[0]["url"]).query)
    assert parsed["tor[cat][0]"] == ["77"]


@pytest.mark.asyncio
async def test_search_normalizes_tracker_payload():
    session = RecordingSession({"data": [JACKETT_AUDIOBOOK]})
    settings = MamServiceSettings(
        mam_base_url="https://mam.test",
        torrent_download_endpoint="/download/{id}",
        mam_session_id="cookie",
        use_mock_data=False,
    )
    client = MyAnonamouseClient(session, settings)

    results = await client.search("Example")
    assert len(results) == 1
    result = results[0]
    assert result.guid == "mam-12345"
    assert (
        result.title
        == "The Example Book - Author One, Author Two [EN][M4B][VIP][FL-VIP]"
    )
    assert result.link == "https://mam.test/download/12345"
    assert result.details == "https://mam.test/t/12345"
    assert result.size == 987654321
    assert result.seeders == 5
    assert result.leechers == 2
    assert result.peers == 7
    assert result.publish_date == "2024-03-01T10:15:00+00:00"
    assert result.download_volume_factor == 0.0
    assert result.minimum_seed_time == MyAnonamouseClient.MINIMUM_SEED_TIME
    assert result.flags == ["fl_vip", "freeleech", "personal_freeleech", "vip"]
    assert result.raw == JACKETT_AUDIOBOOK
