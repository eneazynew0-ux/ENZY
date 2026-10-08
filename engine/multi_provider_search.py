from engine.wikimedia_provider import search_commons
from engine.pixabay_provider import search_pixabay_photos
from engine.pexels_provider import search_pexels_photos
from engine.internet_archive_provider import (
    search_archive,
    normalize_archive_asset,
    enrich_asset,
)
from engine.rights_gate import check_asset
from engine.export_rights_policy import check_export_asset
from engine.media_filter import filter_visual_candidates
from engine.media_downloader import download_previews
from engine.candidate_ranker import rank_licensed_candidates


def search_wikimedia(query, limit=10):
    # Provider-specific syntax preserves the approved subject, not every
    # descriptive word of a stock-search query. Never infer new subjects.
    variants = {
        "Zimbabwe Bird soapstone bird sculpture": '"Zimbabwe Bird"',
        "Zimbabwe Bird artifact photograph": '"Zimbabwe Bird"',
        "Harare airport photograph": '"Harare" "airport"',
        "Harare airport Zimbabwe": '"Harare" "airport"',
    }
    retrieval_query = variants.get(query, query)
    # Relevant photographic files can follow flags/symbols in Commons results.
    retrieval_limit = max(limit, 10) if query in variants else limit
    assets = search_commons(retrieval_query, limit=retrieval_limit)
    result = []

    for asset in assets:
        item = dict(asset)
        item["provider"] = "wikimedia"
        item["search_query"] = query
        item["provider_query"] = retrieval_query
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
        "pixabay": 0,
        "pexels": 0,
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

    # Pixabay photos
    try:
        pixabay = search_pixabay_photos(query, limit=limit_per_provider)
        for asset in pixabay:
            asset["search_query"] = query
        provider_stats["pixabay"] = len(pixabay)
        raw_assets.extend(pixabay)
    except Exception as exc:
        provider_stats["pixabay_error"] = str(exc)

    try:
        pexels = search_pexels_photos(query, limit=limit_per_provider)
        for asset in pexels:
            asset["search_query"] = query
        provider_stats["pexels"] = len(pexels)
        raw_assets.extend(pexels)
    except Exception as exc:
        provider_stats["pexels_error"] = str(exc)

    # Deduplicate without mixing IDs from different providers.
    unique = []
    seen = set()

    for asset in raw_assets:
        provider = asset.get("provider", "unknown")
        identity = (
            asset.get("pageid")
            or asset.get("identifier")
            or asset.get("provider_id")
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

    # Strict final-export policy.
    # Base rights approval does not automatically mean that an asset
    # is suitable for a clean render with no visible credits.
    export_legal = []
    export_rejected = []

    for asset in legal:
        export_rights = check_export_asset(asset)

        if export_rights["status"] == "EXPORT_ALLOWED":
            item = dict(asset)
            item["export_rights"] = export_rights
            export_legal.append(item)
        else:
            item = dict(asset)
            item["export_rights"] = export_rights
            export_rejected.append(item)

    # Remove PDFs, SVGs, flags, logos, etc.
    accepted, media_rejected = filter_visual_candidates(export_legal)

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
            "export_rights_allowed": len(export_legal),
            "export_rights_rejected": len(export_rejected),
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
        "export_rights_rejected": export_rejected,
        "media_rejected": media_rejected,
        "unavailable": unavailable,
        "download_failed": download_failed,
    }
