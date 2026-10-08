from pathlib import Path
from urllib.parse import urlparse
import hashlib
import requests


HEADERS = {
    "User-Agent": "ENZYVIDEO/0.1 (local documentary editor)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def download_preview(asset, output_dir="data/downloaded_previews"):
    url = asset.get("preview_url") or asset.get("original_url")

    if not url:
        raise ValueError("Asset has no preview_url or original_url")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    title = asset.get("title", "")
    suffix = Path(urlparse(url).path).suffix.lower()

    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    identity = str(asset.get("pageid") or url)
    filename = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16] + suffix
    path = output_dir / filename

    if path.exists() and path.stat().st_size > 0:
        item = dict(asset)
        item["local_path"] = str(path)
        return item

    response = SESSION.get(url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if not content_type.startswith("image/"):
        raise ValueError(f"Unexpected Content-Type: {content_type}")

    if not response.content:
        raise ValueError("Downloaded image is empty")

    path.write_bytes(response.content)

    if path.stat().st_size == 0:
        path.unlink(missing_ok=True)
        raise ValueError("Downloaded image is 0 bytes")

    item = dict(asset)
    item["local_path"] = str(path)
    item["download_bytes"] = path.stat().st_size
    item["content_type"] = content_type

    return item


def download_previews(assets, output_dir="data/downloaded_previews"):
    downloaded = []
    failed = []

    for asset in assets:
        try:
            downloaded.append(download_preview(asset, output_dir))
        except Exception as exc:
            failed.append({
                "asset": asset,
                "error": str(exc),
            })

    return downloaded, failed
