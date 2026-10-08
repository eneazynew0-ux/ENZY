import os
import subprocess
import requests


PIXABAY_IMAGE_API = "https://pixabay.com/api/"
PIXABAY_VIDEO_API = "https://pixabay.com/api/videos/"
KEYCHAIN_SERVICE = "ENZYVIDEO_PIXABAY_API_KEY"


def _get_api_key():
    key = os.environ.get("PIXABAY_API_KEY")
    if key:
        return key.strip()

    try:
        return subprocess.check_output(
            [
                "security",
                "find-generic-password",
                "-a", os.environ.get("USER", ""),
                "-s", KEYCHAIN_SERVICE,
                "-w",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _request(url, params):
    key = _get_api_key()
    if not key:
        return []

    params = dict(params)
    params["key"] = key

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json().get("hits", [])
    except Exception:
        return []


def _is_ai_generated(item):
    return bool(item.get("isAiGenerated", False))


def _photo_asset(item):
    return {
        "provider": "pixabay",
        "provider_id": str(item.get("id", "")),
        "title": item.get("name") or item.get("tags", ""),
        "source_url": item.get("pageURL", ""),
        "original_url": item.get("largeImageURL", ""),
        "preview_url": item.get("webformatURL") or item.get("previewURL", ""),
        "media_type": "BITMAP",
        "mime_type": "image/jpeg",
        "width": item.get("imageWidth"),
        "height": item.get("imageHeight"),
        "creator": item.get("user", ""),
        "creator_url": item.get("userURL", ""),
        "license_short": "Pixabay Content License",
        "license_url": "https://pixabay.com/service/license-summary/",
        "commercial_use": True,
        "attribution_required": False,
        "is_ai_generated": False,
        "tags": item.get("tags", ""),
    }


def _best_video_file(videos):
    if not isinstance(videos, dict):
        return None

    candidates = []

    for quality, info in videos.items():
        if not isinstance(info, dict):
            continue

        url = info.get("url")
        if not url:
            continue

        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)
        size = int(info.get("size") or 0)

        candidates.append({
            "quality": quality,
            "url": url,
            "width": width,
            "height": height,
            "size": size,
        })

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (x["width"] * x["height"], x["size"]),
        reverse=True,
    )
    return candidates[0]


def _video_asset(item):
    best = _best_video_file(item.get("videos", {}))
    if not best:
        return None

    return {
        "provider": "pixabay",
        "provider_id": str(item.get("id", "")),
        "title": item.get("name") or item.get("tags", ""),
        "source_url": item.get("pageURL", ""),
        "original_url": best["url"],
        "preview_url": item.get("picture_id")
        and f"https://i.vimeocdn.com/video/{item['picture_id']}_640x360.jpg"
        or "",
        "media_type": "VIDEO",
        "mime_type": "video/mp4",
        "width": best["width"],
        "height": best["height"],
        "duration": item.get("duration"),
        "creator": item.get("user", ""),
        "creator_url": item.get("userURL", ""),
        "license_short": "Pixabay Content License",
        "license_url": "https://pixabay.com/service/license-summary/",
        "commercial_use": True,
        "attribution_required": False,
        "is_ai_generated": False,
        "tags": item.get("tags", ""),
        "video_quality": best["quality"],
    }


def search_pixabay_photos(query, limit=20):
    hits = _request(
        PIXABAY_IMAGE_API,
        {
            "q": query,
            "per_page": max(3, min(int(limit), 200)),
            "safesearch": "true",
            "image_type": "photo",
            "order": "popular",
        },
    )

    results = []

    for item in hits:
        if _is_ai_generated(item):
            continue

        asset = _photo_asset(item)

        if asset["original_url"] or asset["preview_url"]:
            results.append(asset)

        if len(results) >= limit:
            break

    return results


def search_pixabay_videos(query, limit=20):
    hits = _request(
        PIXABAY_VIDEO_API,
        {
            "q": query,
            "per_page": max(3, min(int(limit), 200)),
            "safesearch": "true",
            "order": "popular",
        },
    )

    results = []

    for item in hits:
        if _is_ai_generated(item):
            continue

        asset = _video_asset(item)

        if asset:
            results.append(asset)

        if len(results) >= limit:
            break

    return results


def search_pixabay(query, limit=20, include_photos=True, include_videos=True):
    results = []

    if include_videos:
        results.extend(search_pixabay_videos(query, limit=limit))

    if include_photos:
        results.extend(search_pixabay_photos(query, limit=limit))

    return results


if __name__ == "__main__":
    print("PIXABAY KEY:", "YES" if _get_api_key() else "NO")

    photos = search_pixabay_photos("African desert", limit=3)
    videos = search_pixabay_videos("African desert", limit=3)

    print("PHOTOS:", len(photos))
    for item in photos:
        print("PHOTO:", item["provider_id"], "|", item["title"][:80])

    print("VIDEOS:", len(videos))
    for item in videos:
        print(
            "VIDEO:",
            item["provider_id"],
            "|",
            item["title"][:80],
            "|",
            item.get("width"),
            "x",
            item.get("height"),
            "|",
            item.get("duration"),
            "sec",
        )
