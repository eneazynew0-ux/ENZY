from pathlib import Path
from urllib.parse import urlparse
import hashlib
import requests


HEADERS = {
    "User-Agent": "ENZYVIDEO/0.1 (local documentary editor)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

CHUNK_SIZE = 1024 * 1024
MAX_VIDEO_BYTES = 500 * 1024 * 1024


def download_video(asset, output_dir="data/downloaded_videos"):
    if str(asset.get("media_type", "")).upper() != "VIDEO":
        raise ValueError("Asset is not VIDEO")

    url = asset.get("original_url")
    if not url:
        raise ValueError("Video asset has no original_url")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    identity = str(
        asset.get("provider_id")
        or asset.get("identifier")
        or asset.get("pageid")
        or url
    )

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".mp4", ".mov", ".m4v", ".webm"}:
        suffix = ".mp4"

    filename = hashlib.sha1(
        (asset.get("provider", "") + ":" + identity).encode("utf-8")
    ).hexdigest()[:16] + suffix

    path = output_dir / filename

    if path.exists() and path.stat().st_size > 0:
        item = dict(asset)
        item["local_path"] = str(path)
        item["download_bytes"] = path.stat().st_size
        item["cached"] = True
        return item

    try:
        with SESSION.get(url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            content_length = response.headers.get("Content-Length")

            if content_type and not (
                content_type.startswith("video/")
                or "octet-stream" in content_type
            ):
                raise ValueError(
                    f"Unexpected video Content-Type: {content_type}"
                )

            if content_length:
                expected = int(content_length)
                if expected > MAX_VIDEO_BYTES:
                    raise ValueError(
                        f"Video too large: {expected} bytes"
                    )

            written = 0

            with path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue

                    written += len(chunk)

                    if written > MAX_VIDEO_BYTES:
                        raise ValueError(
                            f"Video exceeded {MAX_VIDEO_BYTES} byte limit"
                        )

                    f.write(chunk)

        if not path.exists() or path.stat().st_size == 0:
            raise ValueError("Downloaded video is empty")

    except Exception:
        path.unlink(missing_ok=True)
        raise

    item = dict(asset)
    item["local_path"] = str(path)
    item["download_bytes"] = path.stat().st_size
    item["content_type"] = content_type
    item["cached"] = False

    return item


def download_videos(assets, output_dir="data/downloaded_videos"):
    downloaded = []
    failed = []

    for asset in assets:
        try:
            downloaded.append(download_video(asset, output_dir))
        except Exception as exc:
            failed.append({
                "asset": asset,
                "error": str(exc),
            })

    return downloaded, failed
