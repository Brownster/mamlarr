from mamlarr_service.providers.qbit import QbitCapabilities
from mamlarr_service.providers.qbit.add_torrent import (
    QbitAddOptions,
    QbitAddRequestBuilder,
)
from mamlarr_service.settings import QbitContentLayout


V2_CAPS = QbitCapabilities(
    api_major=2, supported_endpoints=frozenset({"/api/v2/app/webapiVersion"})
)
V1_CAPS = QbitCapabilities(
    api_major=1, supported_endpoints=frozenset({"/version/api"})
)


def test_builder_prefers_v2_without_options():
    builder = QbitAddRequestBuilder(V2_CAPS)
    request = builder.build()
    assert request.path == "api/v2/torrents/add"
    assert request.form_fields == {}


def test_builder_prefers_v1_without_options():
    builder = QbitAddRequestBuilder(V1_CAPS)
    request = builder.build()
    assert request.path == "command/upload"
    assert request.form_fields == {}


def test_builder_v2_with_options():
    options = QbitAddOptions(
        category="audiobooks",
        start_paused=True,
        force_start=True,
        sequential=True,
        content_layout=QbitContentLayout.subfolder,
        ratio_limit=1.5,
        seeding_time_limit=360,
    )
    builder = QbitAddRequestBuilder(V2_CAPS)
    request = builder.build(options)
    assert request.path == "api/v2/torrents/add"
    assert request.form_fields == {
        "category": "audiobooks",
        "stopped": "true",
        "forced": "true",
        "sequentialDownload": "true",
        "contentLayout": "Subfolder",
        "ratioLimit": "1.5",
        "seedingTimeLimit": "360",
    }


def test_builder_v1_with_options():
    options = QbitAddOptions(
        category="audiobooks",
        start_paused=False,
        force_start=True,
        sequential=True,
        content_layout=QbitContentLayout.original,
        ratio_limit=1.0,
        seeding_time_limit=120,
    )
    builder = QbitAddRequestBuilder(V1_CAPS)
    request = builder.build(options)
    assert request.path == "command/upload"
    assert request.form_fields == {
        "category": "audiobooks",
        "paused": "false",
        "forceStart": "true",
        "sequentialDownload": "true",
        "contentLayout": "Original",
        "ratioLimit": "1.0",
        "seedingTimeLimit": "120",
    }
