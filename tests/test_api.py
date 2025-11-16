from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mamlarr_service import api as api_module
from mamlarr_service.api import create_app
from mamlarr_service.mam_client import MyAnonamouseClient
from mamlarr_service.settings import MamServiceSettings
from mamlarr_service.settings_store import SettingsStore


@pytest.fixture
def test_settings(tmp_path: Path) -> MamServiceSettings:
    return MamServiceSettings(
        api_key="test-key",
        mam_session_id="session",
        mam_base_url="https://mam.test",
        use_mock_data=True,
        search_in_description=True,
        search_in_series=False,
        search_in_filenames=True,
        search_languages=[1, 2],
        download_directory=tmp_path / "downloads",
        postprocess_tmp_dir=tmp_path / "tmp",
    )


@pytest.fixture
def api_client(tmp_path: Path, test_settings: MamServiceSettings, monkeypatch: pytest.MonkeyPatch):
    store_path = tmp_path / "settings.json"

    def _store_factory(path: Path):  # noqa: ARG001 - path ignored in tests
        return SettingsStore(store_path)

    monkeypatch.setattr(api_module, "SettingsStore", _store_factory)
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client


def test_config_includes_search_filters(api_client: TestClient, test_settings: MamServiceSettings):
    response = api_client.get("/config")
    assert response.status_code == 200
    payload = response.json()
    filters = {entry["name"]: entry for entry in payload["searchFilters"]}
    assert filters["MAM_SERVICE_SEARCH_IN_DESCRIPTION"]["default"] is True
    assert filters["MAM_SERVICE_SEARCH_IN_SERIES"]["default"] is False
    assert filters["MAM_SERVICE_SEARCH_IN_FILENAMES"]["default"] is True
    assert filters["MAM_SERVICE_SEARCH_LANGUAGES"]["default"] == [1, 2]


def test_search_endpoint_passes_filters(api_client: TestClient, test_settings: MamServiceSettings, monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    async def fake_search(self, query, limit=100, offset=0, *, categories=None, languages=None):
        captured.update(
            {
                "query": query,
                "limit": limit,
                "offset": offset,
                "categories": categories,
                "languages": languages,
            }
        )
        return []

    monkeypatch.setattr(MyAnonamouseClient, "search", fake_search)
    params = [
        ("query", "Mock Query"),
        ("limit", "5"),
        ("offset", "2"),
        ("cat", "3000"),
        ("cat", "3030"),
        ("lang", "1"),
        ("lang", "2,3"),
    ]
    response = api_client.get(
        "/api/v1/search",
        params=params,
        headers={"X-Api-Key": test_settings.api_key},
    )
    assert response.status_code == 200
    assert captured["query"] == "Mock Query"
    assert captured["limit"] == 5
    assert captured["offset"] == 2
    assert captured["categories"] == [3000, 3030]
    assert captured["languages"] == [1, 2, 3]


def test_search_endpoint_returns_mock_results(api_client: TestClient, test_settings: MamServiceSettings):
    response = api_client.get(
        "/api/v1/search",
        params={"query": "mock"},
        headers={"X-Api-Key": test_settings.api_key},
    )
    assert response.status_code == 200
    releases = response.json()
    assert releases, "mock search should return built-in payload"
    release = releases[0]
    assert "[EN][M4B]" in release["title"]
    assert release["indexerFlags"] == []
    assert release["seeders"] == 15
