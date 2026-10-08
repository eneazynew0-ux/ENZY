import json
import subprocess
import urllib.parse
import urllib.request


PEXELS_PHOTO_API = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_API = "https://api.pexels.com/v1/videos/search"


def _get_api_key():
    try:
        key = subprocess.check_output(
            [
                "security",
                "find-generic-password",
                "-a",
                subprocess.check_output(
                    ["whoami"],
                    text=True,
                ).strip(),
                "-s",
                "ENZYVIDEO_PEXELS_API_KEY",
                "-w",
            ],
            text=True,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            "Pexels API key not found in macOS Keychain"
        ) from exc

    if not key:
        raise RuntimeError("Pexels API key is empty")

    return key


def _request(url, params, result_key):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "Authorization": _get_api_key(),
            "User-Agent": "ENZYVIDEO/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    return payload.get(result_key, [])


def _photo_asset(item):
    src = item.get("src") or {}

    original = (
        src.get("original")
        or src.get("large2x")
        or src.get("large")
        or ""
    )

    preview = (
        src.get("medium")
        or src.get("large")
        or src.get("small")
        or ""
    )

    return {
        "provider": "pexels",
        "provider_id": str(item.get("id", "")),
        "title": item.get("alt") or "",
        "source_url": item.get("url", ""),
        "original_url": original,
        "preview_url": preview,
        "media_type": "BITMAP",
        "mime_type": "image/jpeg",
        "width": item.get("width"),
        "height": item.get("height"),
        "creator": item.get("photographer", ""),
        "creator_url": item.get("photographer_url", ""),
        "license_short": "Pexels License",
        "license_url": "https://www.pexels.com/license/",
        "commercial_use": True,
        "attribution_required": False,
        "is_ai_generated": False,
        "tags": item.get("alt") or "",
    }


def _best_video_file(files):
    candidates = []

    for info in files or []:
        if not isinstance(info, dict):
            continue

        url = info.get("link")
        if not url:
            continue

        file_type = (info.get("file_type") or "").lower()
        if file_type and "mp4" not in file_type:
            continue

        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)

        candidates.append(
            {
                "url": url,
                "width": width,
                "height": height,
                "quality": info.get("quality") or "",
                "file_type": info.get("file_type") or "video/mp4",
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["width"] * x["height"],
        reverse=True,
    )

    return candidates[0]


def _video_asset(item):
    best = _best_video_file(item.get("video_files"))
    if not best:
        return None

    user = item.get("user") or {}

    return {
        "provider": "pexels",
        "provider_id": str(item.get("id", "")),
        "title": item.get("url", "").rstrip("/").split("/")[-1],
        "source_url": item.get("url", ""),
        "original_url": best["url"],
        "preview_url": item.get("image", ""),
        "media_type": "VIDEO",
        "mime_type": best["file_type"],
        "width": best["width"],
        "height": best["height"],
        "duration": item.get("duration"),
        "creator": user.get("name", ""),
        "creator_url": user.get("url", ""),
        "license_short": "Pexels License",
        "license_url": "https://www.pexels.com/license/",
        "commercial_use": True,
        "attribution_required": False,
        "is_ai_generated": False,
        "tags": "",
        "video_quality": best["quality"],
    }


def search_pexels_photos(query, limit=20):
    items = _request(
        PEXELS_PHOTO_API,
        {
            "query": query,
            "per_page": max(1, min(int(limit), 80)),
            "orientation": "landscape",
        },
        "photos",
    )

    results = []

    for item in items:
        asset = _photo_asset(item)

        if asset["original_url"] or asset["preview_url"]:
            results.append(asset)

        if len(results) >= limit:
            break

    return results


def search_pexels_videos(query, limit=20):
    items = _request(
        PEXELS_VIDEO_API,
        {
            "query": query,
            "per_page": max(1, min(int(limit), 80)),
            "orientation": "landscape",
        },
        "videos",
    )

    results = []

    for item in items:
        asset = _video_asset(item)

        if asset:
            results.append(asset)

        if len(results) >= limit:
            break

    return results


def search_pexels(
    query,
    limit=20,
    include_photos=True,
    include_videos=True,
):
    results = []

    if include_photos:
        results.extend(search_pexels_photos(query, limit=limit))

    if include_videos:
        results.extend(search_pexels_videos(query, limit=limit))

    return results
