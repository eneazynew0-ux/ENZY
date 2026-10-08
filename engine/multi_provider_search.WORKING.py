from engine.wikimedia_provider import search_commons
from engine.internet_archive_provider import (
    search_archive,
    normalize_archive_asset,
    enrich_asset,
)
from engine.rights_gate import check_asset
from engine.media_filter import filter_visual_candidates
from engine.media_downloader import download_previews
from engine.candidate_ranker import rank_licensed_candidates


def search_wikimedia(query, limit=10):
    assets = search_commons(query, limit=limit)
    result = []

    for asset in assets:
        item = dict(asset)
        item["provider"] = "wikimedia"
        item["search_query"] = query
        result.append(item)

    return result


def search_internet_archive(query, limit=10):
    assets = search_archive(query, limit=limit)
    result = []

    for asset in assets:
        item = normalize_archive_asset(asset)
        item["search_query"] = query

        rights = check_asset(item)

        # Do not spend another network request on blocked/review assets.
        if rights["status"] != "ALLOWED":
            item["_precheck_rights"] = rights
            result.append(item)
            continue

        try:
            item = enrich_asset(item)
            item = normalize_archive_asset(item)
        except Exception as exc:
            item["_enrich_error"] = str(exc)

        result.append(item)

    return result


def search_all_providers(query, target, limit_per_provider=10,
                         output_dir="data/multi_provider_previews"):
    raw_assets = []

    provider_stats = {
        "wikimedia": 0,
        "internet_archive": 0,
    }

    # Wikimedia
    try:
        wikimedia = search_wikimedia(query, limit=limit_per_provider)
        provider_stats["wikimedia"] = len(wikimedia)
        raw_assets.extend(wikimedia)
    except Exception as exc:
        provider_stats["wikimedia_error"] = str(exc)

    # Internet Archive
    try:
        archive = search_internet_archive(query, limit=limit_per_provider)
        provider_stats["internet_archive"] = len(archive)
        raw_assets.extend(archive)
    except Exception as exc:
        provider_stats["internet_archive_error"] = str(exc)

    # Deduplicate without mixing IDs from different providers.
    unique = []
    seen = set()

    for asset in raw_assets:
        provider = asset.get("provider", "unknown")
        identity = (
            asset.get("pageid")
            or asset.get("identifier")
            or asset.get("description_url")
            or asset.get("original_url")
        )

        key = (provider, str(identity))

        if not identity or key in seen:
            continue

        seen.add(key)
        unique.append(asset)

    # Rights must pass BEFORE download/VLM.
    legal = []
    rights_rejected = []

    for asset in unique:
        rights = check_asset(asset)

        if rights["status"] == "ALLOWED":
            item = dict(asset)
            item["rights"] = rights
            legal.append(item)
        else:
            item = dict(asset)
            item["rights"] = rights
            rights_rejected.append(item)

    # Remove PDFs, SVGs, flags, logos, etc.
    accepted, media_rejected = filter_visual_candidates(legal)

    # Some IA assets can fail enrichment and therefore have no image URL.
    downloadable = []
    unavailable = []

    for asset in accepted:
        if asset.get("preview_url") or asset.get("original_url"):
            downloadable.append(asset)
        else:
            unavailable.append(asset)

    downloaded, download_failed = download_previews(
        downloadable,
        output_dir=output_dir,
    )

    ranked = rank_licensed_candidates(target, downloaded)

    return {
        "query": query,
        "target": target,
        "provider_stats": provider_stats,
        "stats": {
            "search_found_raw": len(raw_assets),
            "search_unique": len(unique),
            "rights_allowed": len(legal),
            "rights_rejected": len(rights_rejected),
            "media_accepted": len(accepted),
            "media_rejected": len(media_rejected),
            "unavailable": len(unavailable),
            "downloaded": len(downloaded),
            "download_failed": len(download_failed),
            "visual_matches": len(ranked["matches"]),
            "visual_rejected": len(ranked["visual_rejected"]),
        },
        "best": ranked["best"],
        "matches": ranked["matches"],
        "visual_rejected": ranked["visual_rejected"],
        "rights_rejected": rights_rejected,
        "media_rejected": media_rejected,
        "unavailable": unavailable,
        "download_failed": download_failed,
    }
