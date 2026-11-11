#!/usr/bin/env python3

import argparse
import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PACKAGES = (
    "amd64-hassio-xfinity-usage",
    "aarch64-hassio-xfinity-usage",
    "hassio-xfinity-usage",
)
KEEP_RELEASES = 5
KEEP_OTHER_VERSIONS = 10
PAGE_SIZE = 100


def select_published_releases(releases):
    published_releases = [
        release
        for release in releases
        if not release.get("draft")
        and not release.get("prerelease")
        and release.get("published_at")
    ]
    published_releases.sort(key=lambda release: release["published_at"], reverse=True)
    return published_releases[:KEEP_RELEASES]


def plan_versions(versions, all_release_tags, kept_release_tags, keep_other_versions):
    ordered_versions = sorted(
        versions, key=lambda version: version["created_at"], reverse=True
    )
    decisions = []
    other_versions_seen = 0

    for version in ordered_versions:
        tags = version.get("metadata", {}).get("container", {}).get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError(f"Invalid container tags for package version {version['id']}")

        version_release_tags = set(tags) & all_release_tags
        retained_tags = sorted(set(tags) & kept_release_tags)

        if "latest" in tags:
            keep, reason = True, "has the latest tag"
        elif retained_tags:
            keep, reason = True, f"published release {', '.join(retained_tags)}"
        elif version_release_tags:
            keep = False
            reason = f"older published release {', '.join(sorted(version_release_tags))}"
        else:
            other_versions_seen += 1
            keep = other_versions_seen <= keep_other_versions
            reason = (
                "recent non-release version"
                if keep
                else "older non-release version"
            )

        decisions.append((version, keep, reason))

    return decisions


class GitHubAPI:
    def __init__(self, token, api_url):
        self.api_url = api_url.rstrip("/")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def request(self, path, method="GET"):
        request = Request(
            f"{self.api_url}{path}",
            headers=self.headers,
            method=method,
        )
        try:
            with urlopen(request) as response:
                body = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API {method} {path} failed ({error.code}): {detail}"
            ) from error

        if not body:
            return None
        return json.loads(body)

    def get_all(self, path):
        results = []
        page = 1
        while True:
            query = urlencode({"per_page": PAGE_SIZE, "page": page})
            page_results = self.request(f"{path}?{query}")
            if not isinstance(page_results, list):
                raise RuntimeError(f"Expected a list from GitHub API {path}")
            results.extend(page_results)
            if len(page_results) < PAGE_SIZE:
                return results
            page += 1


def container_tags(version):
    tags = version.get("metadata", {}).get("container", {}).get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError(f"Invalid container tags for package version {version['id']}")
    return tags


def run(delete):
    token = os.environ.get("GH_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token:
        raise RuntimeError("GH_TOKEN is required")
    if repository.count("/") != 1:
        raise RuntimeError("GITHUB_REPOSITORY must be in owner/repository form")

    api = GitHubAPI(token, os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    owner, repo_name = repository.split("/")
    repo_data = api.request(f"/repos/{repository}")
    owner_type = repo_data.get("owner", {}).get("type")
    if owner_type not in {"User", "Organization"}:
        raise RuntimeError(f"Unsupported repository owner type: {owner_type!r}")
    package_namespace = "orgs" if owner_type == "Organization" else "users"
    package_owner = quote(owner, safe="")

    releases = api.get_all(f"/repos/{repository}/releases")
    retained_releases = select_published_releases(releases)
    if not retained_releases:
        raise RuntimeError("No published stable releases found; refusing package cleanup")

    all_release_tags = {
        release["tag_name"]
        for release in releases
        if not release.get("draft")
        and not release.get("prerelease")
        and release.get("published_at")
    }
    kept_release_tags = {release["tag_name"] for release in retained_releases}

    package_plans = []
    for package in PACKAGES:
        package_path = (
            f"/{package_namespace}/{package_owner}/packages/container/"
            f"{quote(package, safe='')}/versions"
        )
        versions = api.get_all(package_path)
        package_tags = {
            tag for version in versions for tag in container_tags(version)
        }
        missing_release_tags = kept_release_tags - package_tags
        if missing_release_tags:
            missing = ", ".join(sorted(missing_release_tags))
            raise RuntimeError(
                f"{package} has no image versions for retained release tag(s): {missing}; "
                "refusing package cleanup"
            )

        decisions = plan_versions(
            versions,
            all_release_tags,
            kept_release_tags,
            KEEP_OTHER_VERSIONS,
        )
        package_plans.append((package, decisions))

    action = "DELETE" if delete else "WOULD DELETE"
    lines = [
        f"## Package retention {'cleanup' if delete else 'preview'}",
        "",
        f"Keeping the {len(retained_releases)} newest published stable releases: "
        + ", ".join(release["tag_name"] for release in retained_releases),
        f"Also keeping the latest tag and the {KEEP_OTHER_VERSIONS} newest "
        "non-release versions per package.",
        "",
    ]

    for package, decisions in package_plans:
        lines.extend(
            [
                f"### `{package}`",
                "",
                "| Decision | Created | Version | Tags | Reason |",
                "|---|---|---|---|---|",
            ]
        )
        for version, keep, reason in decisions:
            tags = container_tags(version)
            decision = "KEEP" if keep else action
            tag_text = ", ".join(tags) if tags else "(untagged)"
            lines.append(
                f"| {decision} | {version['created_at']} | `{version['name']}` "
                f"| {tag_text} | {reason} |"
            )
        lines.append("")

    report = "\n".join(lines)
    print(report)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(report)
            summary.write("\n")

    if delete:
        for package, decisions in package_plans:
            package_path = (
                f"/{package_namespace}/{package_owner}/packages/container/"
                f"{quote(package, safe='')}/versions"
            )
            for version, keep, _ in decisions:
                if not keep:
                    api.request(f"{package_path}/{version['id']}", method="DELETE")
                    print(f"Deleted {package} package version {version['id']}")


def main():
    parser = argparse.ArgumentParser(description="Preview or apply package retention.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete versions outside the retention policy; otherwise preview only.",
    )
    arguments = parser.parse_args()
    run(delete=arguments.delete)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
