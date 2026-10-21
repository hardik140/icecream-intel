"""Download the pinned gosom/google-maps-scraper release binary for this OS into bin/.

Usage: python -m scripts.install_gmaps_scraper
"""
import hashlib
import json
import platform
import stat
import urllib.request
from pathlib import Path

VERSION = "v1.18.1"
BIN_DIR = Path(__file__).resolve().parents[1] / "bin"
SUFFIX = {"Windows": "windows-amd64.exe", "Linux": "linux-amd64", "Darwin": "darwin-amd64"}


def main() -> None:
    suffix = SUFFIX.get(platform.system())
    if not suffix or platform.machine().lower() not in ("amd64", "x86_64"):
        raise SystemExit(f"No prebuilt binary for {platform.system()} {platform.machine()}; use Docker instead")
    api = f"https://api.github.com/repos/gosom/google-maps-scraper/releases/tags/{VERSION}"
    with urllib.request.urlopen(api, timeout=30) as r:
        assets = json.load(r)["assets"]
    asset = next(a for a in assets if a["name"].endswith(suffix))
    BIN_DIR.mkdir(exist_ok=True)
    dest = BIN_DIR / asset["name"]
    print(f"Downloading {asset['name']} ({asset['size'] // 1_000_000} MB)...")
    urllib.request.urlretrieve(asset["browser_download_url"], dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    print(f"Saved {dest}\nsha256 {hashlib.sha256(dest.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
