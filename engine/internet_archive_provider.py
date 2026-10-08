import requests
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{}"

HEADERS = {
    "User-Agent": "ENZYVIDEO/0.1 (local documentary editor)"
}

RETRY = Retry(
    total=5,
    connect=5,
    read=5,
    status=5,
    backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
SESSION.mount("https://", HTTPAdapter(max_retries=RETRY))
SESSION.mount("http://", HTTPAdapter(max_retries=RETRY))


def search_archive(query, limit=20):
    params = {
        "q": f'"{query}" AND mediatype:image',
        "fl[]": [
            "identifier",
            "title",
            "creator",
            "licenseurl",
            "rights",
            "mediatype",
        ],
        "rows": limit,
        "page": 1,
        "output": "json",
    }

    response = SESSION.get(SEARCH_URL, params=params, timeout=30)
    response.raise_for_status()

    docs = response.json().get("response", {}).get("docs", [])
    assets = []

    for doc in docs:
        identifier = doc.get("identifier")
        if not identifier:
            continue

        assets.append({
            "provider": "internet_archive",
            "identifier": identifier,
            "title": doc.get("title", ""),
            "creator": doc.get("creator", ""),
            "license_url": doc.get("licenseurl", ""),
            "rights_text": doc.get("rights", ""),
            "description_url": f"https://archive.org/details/{identifier}",
        })

    return assets


def enrich_asset(asset):
    identifier = asset.get("identifier")
    if not identifier:
        raise ValueError("Missing Internet Archive identifier")

    response = SESSION.get(
        METADATA_URL.format(identifier),
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    metadata = data.get("metadata", {})
    files = data.get("files", [])

    image_files = []

    for file in files:
        name = file.get("name", "")
        lower = name.lower()

        if not lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue

        format_name = str(file.get("format", "")).lower()

        if "thumb" in format_name or "_thumb." in lower or "__ia_thumb" in lower:
            continue

        image_files.append(file)

    if not image_files:
        raise ValueError("No usable image file found")

    def file_size(item):
        try:
            return int(item.get("size") or 0)
        except (TypeError, ValueError):
            return 0

    image_files.sort(key=file_size, reverse=True)
    best_file = image_files[0]
    filename = best_file["name"]

    item = dict(asset)
    item.update({
        "title": metadata.get("title") or asset.get("title", ""),
        "artist": metadata.get("creator") or asset.get("creator", ""),
        "credit": metadata.get("creator") or asset.get("creator", ""),
        "license_url": metadata.get("licenseurl") or asset.get("license_url", ""),
        "rights_text": metadata.get("rights") or asset.get("rights_text", ""),
        "original_url": f"https://archive.org/download/{identifier}/{quote(filename)}",
        "preview_url": f"https://archive.org/download/{identifier}/{quote(filename)}",
        "filename": filename,
        "file_size": file_size(best_file),
    })

    return item


def license_short_from_url(url):
    value = str(url or "").lower().rstrip("/")

    mappings = {
        "/by/4.0": "CC BY 4.0",
        "/by-sa/4.0": "CC BY-SA 4.0",
        "/by-nc/4.0": "CC BY-NC 4.0",
        "/by-nc-sa/4.0": "CC BY-NC-SA 4.0",
        "/by-nd/4.0": "CC BY-ND 4.0",
        "/by-nc-nd/4.0": "CC BY-NC-ND 4.0",
        "/publicdomain/zero/1.0": "CC0",
    }

    for marker, name in mappings.items():
        if marker in value:
            return name

    return ""


def normalize_archive_asset(asset):
    item = dict(asset)
    item["license_short"] = license_short_from_url(
        item.get("license_url")
    )
    return item


# ---------------------------------------------------------------------------
# Video path
# ---------------------------------------------------------------------------

def search_archive_videos(query, limit=20):
    """
    Search Internet Archive movie/video items.

    This is intentionally separate from search_archive(), which is the
    established image path.
    """
    params = {
        "q": f'"{query}" AND mediatype:movies',
        "fl[]": [
            "identifier",
            "title",
            "creator",
            "licenseurl",
            "rights",
            "mediatype",
        ],
        "rows": limit,
        "page": 1,
        "output": "json",
    }

    response = SESSION.get(
        SEARCH_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    docs = response.json().get(
        "response",
        {},
    ).get("docs", [])

    assets = []

    for doc in docs:
        identifier = doc.get("identifier")

        if not identifier:
            continue

        assets.append({
            "provider": "internet_archive",
            "identifier": identifier,
            "provider_id": identifier,
            "media_type": "video",
            "title": doc.get("title", ""),
            "creator": doc.get("creator", ""),
            "license_url": doc.get("licenseurl", ""),
            "rights_text": doc.get("rights", ""),
            "description_url": (
                f"https://archive.org/details/{identifier}"
            ),
            "source_url": (
                f"https://archive.org/details/{identifier}"
            ),
        })

    return assets


def enrich_video_asset(asset):
    """
    Resolve one Internet Archive item to a usable video file.

    Does not modify the established image enrichment path.
    """
    identifier = asset.get("identifier")

    if not identifier:
        raise ValueError(
            "Missing Internet Archive identifier"
        )

    response = SESSION.get(
        METADATA_URL.format(identifier),
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    metadata = data.get("metadata", {})
    files = data.get("files", [])

    video_files = []

    allowed_extensions = (
        ".mp4",
        ".m4v",
        ".mov",
        ".webm",
    )

    rejected_markers = (
        "thumb",
        "thumbnail",
        "preview",
        "sample",
    )

    for file in files:
        name = str(file.get("name") or "")
        lower = name.lower()

        if not lower.endswith(allowed_extensions):
            continue

        format_name = str(
            file.get("format") or ""
        ).lower()

        if any(
            marker in lower or marker in format_name
            for marker in rejected_markers
        ):
            continue

        video_files.append(file)

    if not video_files:
        raise ValueError(
            "No usable video file found"
        )

    def file_size(item):
        try:
            return int(item.get("size") or 0)
        except (TypeError, ValueError):
            return 0

    # Prefer MP4 for our downstream FFmpeg pipeline.
    # Within the same container type prefer the larger source.
    def video_priority(item):
        name = str(item.get("name") or "").lower()

        if name.endswith(".mp4"):
            container_priority = 4
        elif name.endswith(".m4v"):
            container_priority = 3
        elif name.endswith(".mov"):
            container_priority = 2
        elif name.endswith(".webm"):
            container_priority = 1
        else:
            container_priority = 0

        return (
            container_priority,
            file_size(item),
        )

    video_files.sort(
        key=video_priority,
        reverse=True,
    )

    best_file = video_files[0]
    filename = best_file["name"]

    direct_url = (
        f"https://archive.org/download/"
        f"{identifier}/{quote(filename)}"
    )

    item = dict(asset)

    item.update({
        "provider": "internet_archive",
        "provider_id": identifier,
        "media_type": "video",
        "title": (
            metadata.get("title")
            or asset.get("title", "")
        ),
        "artist": (
            metadata.get("creator")
            or asset.get("creator", "")
        ),
        "credit": (
            metadata.get("creator")
            or asset.get("creator", "")
        ),
        "license_url": (
            metadata.get("licenseurl")
            or asset.get("license_url", "")
        ),
        "rights_text": (
            metadata.get("rights")
            or asset.get("rights_text", "")
        ),
        "description_url": (
            f"https://archive.org/details/{identifier}"
        ),
        "source_url": (
            f"https://archive.org/details/{identifier}"
        ),
        "original_url": direct_url,
        "video_url": direct_url,
        "filename": filename,
        "file_size": file_size(best_file),
        "format": best_file.get("format", ""),
    })

    return normalize_archive_asset(item)
