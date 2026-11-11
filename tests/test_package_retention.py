import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts")
)

from package_retention import plan_versions, select_published_releases


def make_version(version_id, created_at, tags):
    return {
        "id": version_id,
        "name": f"sha256:{version_id}",
        "created_at": created_at,
        "metadata": {"container": {"tags": tags}},
    }


def test_selects_five_newest_published_stable_releases():
    releases = [
        {
            "tag_name": f"2026.0.{number}",
            "published_at": f"2026-01-{number:02}T00:00:00Z",
            "draft": False,
            "prerelease": False,
        }
        for number in range(1, 7)
    ]
    releases.extend(
        [
            {
                "tag_name": "draft-release",
                "published_at": "2026-12-01T00:00:00Z",
                "draft": True,
                "prerelease": False,
            },
            {
                "tag_name": "preview-release",
                "published_at": "2026-12-02T00:00:00Z",
                "draft": False,
                "prerelease": True,
            },
        ]
    )

    selected = select_published_releases(releases)

    assert [release["tag_name"] for release in selected] == [
        "2026.0.6",
        "2026.0.5",
        "2026.0.4",
        "2026.0.3",
        "2026.0.2",
    ]


def test_keeps_recent_releases_and_latest_tag():
    versions = [
        make_version(1, "2026-11-01T00:00:00Z", ["2026.10.5", "latest"]),
        make_version(2, "2026-10-01T00:00:00Z", ["2026.10.4"]),
        make_version(3, "2026-09-01T00:00:00Z", ["2025.10.0"]),
    ]
    release_tags = {"2026.10.5", "2026.10.4", "2025.10.0"}
    retained_tags = {"2026.10.5", "2026.10.4"}

    decisions = plan_versions(versions, release_tags, retained_tags, 10)

    assert {version["id"]: keep for version, keep, _ in decisions} == {
        1: True,
        2: True,
        3: False,
    }


def test_keeps_only_the_newest_nonrelease_versions():
    versions = [
        make_version(
            version_id,
            f"2026-01-{version_id:02}T00:00:00Z",
            [f"development-{version_id}"],
        )
        for version_id in range(1, 13)
    ]

    decisions = plan_versions(versions, set(), set(), 10)

    assert {
        version["id"] for version, keep, _ in decisions if keep
    } == set(range(3, 13))
