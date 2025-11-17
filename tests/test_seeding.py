from mamlarr_service.models import DownloadJob
from mamlarr_service.seeding import TorrentSeedConfiguration, build_seed_configuration
from mamlarr_service.settings import MamServiceSettings


def test_build_seed_configuration_uses_release_minimum():
    settings = MamServiceSettings(seed_target_hours=24)
    job = DownloadJob(id="job", guid="guid", release={"minimumSeedTime": 200000})

    config = build_seed_configuration(job, settings)

    assert config.required_seed_seconds == 200000
    # 200000 seconds -> 3334 minutes when rounded up
    assert config.seeding_time_limit == 3334


def test_build_seed_configuration_respects_user_share_limits():
    settings = MamServiceSettings(seed_target_hours=4, qbittorrent_seed_time=600)
    job = DownloadJob(id="job", guid="guid", release={"minimumSeedTime": 2000})

    config = build_seed_configuration(job, settings)

    # Release requirement (2000s -> 34 min) is lower than user-specified 600 minute limit.
    assert config.seeding_time_limit == 600


def test_build_seed_configuration_honors_tracker_minimums():
    settings = MamServiceSettings(seed_target_hours=24, qbittorrent_seed_time=600)
    job = DownloadJob(id="job", guid="guid", release={"minimumSeedTime": 200000})

    config = build_seed_configuration(job, settings)

    # Tracker requirement is larger than the configured share limit so it should win.
    assert config.seeding_time_limit == 3334


def test_torrent_seed_configuration_serialization_round_trip():
    config = TorrentSeedConfiguration(
        required_seed_seconds=3600, ratio_limit=1.5, seeding_time_limit=120
    )

    restored = TorrentSeedConfiguration.from_record(config.to_record())
    assert restored == config
