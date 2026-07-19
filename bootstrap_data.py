"""Download and unpack the data archive if it's not already present.

Runs before the API starts. Locally this is a no-op (data/ exists);
on a fresh deploy it fetches the private release asset from GitHub.
"""
import os
import tarfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

MARKER = Path("data/processed/controls.json")
ARCHIVE = "cis-data.tar.gz"


def main() -> None:
    if MARKER.exists():
        print("[bootstrap] data present, nothing to do")
        return

    repo = os.environ["DATA_REPO"]
    tag = os.environ.get("DATA_TAG", "v1")
    token = os.environ["DATA_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Ask the GitHub API which assets release <tag> carries
    release = httpx.get(
        f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
        headers=headers,
    )
    release.raise_for_status()
    asset = release.json()["assets"][0]
    print(f"[bootstrap] downloading {asset['name']} ({asset['size'] / 1e6:.1f} MB)")

    # 2. Stream the asset to disk (octet-stream = "give me the file itself")
    with httpx.stream(
        "GET",
        asset["url"],
        headers={**headers, "Accept": "application/octet-stream"},
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        with open(ARCHIVE, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

    # 3. Unpack and clean up
    with tarfile.open(ARCHIVE) as tar:
        tar.extractall(".", filter="data")
    os.remove(ARCHIVE)
    print("[bootstrap] data ready")


if __name__ == "__main__":
    main()