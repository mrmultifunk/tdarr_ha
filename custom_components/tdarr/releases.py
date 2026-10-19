"""Read stable releases from Tdarr's official updater manifest."""

import re
import requests

VERSIONS_URL = "https://storage.tdarr.io/versions.json"
RELEASE_URL = "https://docs.tdarr.io/docs/releases/changing-version/"


def version_key(version):
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return None
    return tuple(int(part) for part in version.split("."))


def latest_stable(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid version manifest")
    versions = [key for key, platforms in data.items() if version_key(key) is not None
                and isinstance(platforms, dict)
                and any(isinstance(package, dict) and package.get("Tdarr_Server")
                        for package in platforms.values())]
    if not versions:
        raise ValueError("No stable server releases")
    return max(versions, key=version_key)


def fetch_latest():
    # Deliberately separate from the local API client: never send its API key.
    response = requests.get(VERSIONS_URL, timeout=10)
    response.raise_for_status()
    return latest_stable(response.json())
