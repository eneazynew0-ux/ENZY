from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


HEADERS = {
    "User-Agent": "ENZYVIDEO/0.1 (local documentary editor)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

RETRY = Retry(
    total=5,
    connect=3,
    read=3,
    status=5,
    backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    respect_retry_after_header=True,
)

SESSION.mount("https://", HTTPAdapter(max_retries=RETRY))


def _clean_media_url(url):
    """Remove tracking parameters without changing the media identity."""
    parsed = urlparse(str(url or ""))
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    return urlunparse(parsed._replace(query=urlencode(query)))


def download_preview(asset, output_dir="data/downloaded_previews"):
    url = _clean_media_url(
        asset.get("preview_url") or asset.get("original_url")
    )

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
