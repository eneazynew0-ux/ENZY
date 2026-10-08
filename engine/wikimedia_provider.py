from html.parser import HTMLParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "ENZYVIDEO/0.1 (local documentary editor)"
}

SESSION = requests.Session()

RETRY = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

SESSION.mount("https://", HTTPAdapter(max_retries=RETRY))

class _MetadataText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        self.parts.append(" ")

    def handle_endtag(self, tag):
        self.parts.append(" ")


def _plain_metadata(value):
    parser = _MetadataText()
    parser.feed(str(value or ""))
    parser.close()
    return " ".join("".join(parser.parts).split())


def search_commons(query, limit=20):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|mime|mediatype|size|sha1|extmetadata",
        "iiurlwidth": 800,
        "format": "json",
        "formatversion": 2,
    }

    response = SESSION.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    results = []

    for page in data.get("query", {}).get("pages", []):
        info_list = page.get("imageinfo", [])
        if not info_list:
            continue

        info = info_list[0]
        meta = info.get("extmetadata", {})

        mime = (info.get("mime") or "").lower()
        media_type = (info.get("mediatype") or "").upper()
        title = (page.get("title") or "").lower()

        # Commons namespace 6 also contains PDFs, DjVu documents,
        # audio and other non-visual files. Search provider should
        # return only material useful as documentary visuals.
        blocked_extensions = (
            ".pdf", ".djvu", ".djv", ".ogg", ".oga",
            ".opus", ".flac", ".wav", ".mp3"
        )

        if title.endswith(blocked_extensions):
            continue

        if mime and not (
            mime.startswith("image/")
            or mime.startswith("video/")
        ):
            continue

        if media_type and media_type not in (
            "BITMAP", "DRAWING", "VIDEO"
        ):
            continue

        def value(name):
            return meta.get(name, {}).get("value", "")

        results.append({
            "pageid": page.get("pageid"),
            "title": page.get("title", ""),
            "description": _plain_metadata(value("ImageDescription")),
            "description_html": value("ImageDescription"),
            "source_date": _plain_metadata(value("DateTimeOriginal")),
            "width": info.get("width"),
            "height": info.get("height"),
            "quality_label": (
                "HD_OR_BETTER"
                if min(info.get("width") or 0, info.get("height") or 0) >= 720
                and max(info.get("width") or 0, info.get("height") or 0) >= 1280
                else "LOW_RESOLUTION"
            ),
            "quality_warning": (
                ""
                if min(info.get("width") or 0, info.get("height") or 0) >= 720
                and max(info.get("width") or 0, info.get("height") or 0) >= 1280
                else "Source is below HD and must not be presented as high-resolution footage"
            ),
            "source_metadata": meta,
            "categories": _plain_metadata(value("Categories")),
            "sha1": info.get("sha1", ""),
            "original_url": info.get("url", ""),
            "preview_url": info.get("thumburl", info.get("url", "")),
            "description_url": info.get("descriptionurl", ""),
            "media_type": info.get("mediatype", ""),
            "mime": info.get("mime", ""),
            "license_short": value("LicenseShortName"),
            "license_url": value("LicenseUrl"),
            "artist": value("Artist"),
            "credit": value("Credit"),
            "attribution_required": _plain_metadata(
                value("AttributionRequired")
            ),
            "usage_terms": value("UsageTerms"),
            "copyrighted": value("Copyrighted"),
            "restrictions": value("Restrictions"),
        })

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect Wikimedia Commons file-search results",
    )
    parser.add_argument("query", nargs="?", default="Zimbabwe Bird")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    items = search_commons(args.query, limit=args.limit)

    print("RESULTS:", len(items))

    for i, item in enumerate(items, 1):
        print()
        print(i, item["title"])
        print("LICENSE:", item["license_short"])
        print("MIME:", item["mime"])
        print("SIZE:", f"{item['width']}x{item['height']}")
        print("IDENTITY CATEGORIES:", item["categories"])
        print("SOURCE:", item["description_url"])
