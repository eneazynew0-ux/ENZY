from engine.wikimedia_provider import search_commons
from engine.rights_gate import filter_allowed
from engine.media_filter import filter_visual_candidates
from engine.media_downloader import download_previews
from engine.candidate_ranker import rank_licensed_candidates


def search_and_rank(query, target, limit=20, output_dir="data/search_previews"):
    assets = search_commons(query, limit=limit)

    legal = filter_allowed(assets)
    accepted, media_rejected = filter_visual_candidates(legal)

    downloaded, download_failed = download_previews(
        accepted,
        output_dir=output_dir,
    )

    ranked = rank_licensed_candidates(target, downloaded)

    return {
        "query": query,
        "target": target,
        "stats": {
            "search_found": len(assets),
            "rights_allowed": len(legal),
            "media_accepted": len(accepted),
            "media_rejected": len(media_rejected),
            "downloaded": len(downloaded),
            "download_failed": len(download_failed),
            "visual_matches": len(ranked["matches"]),
            "visual_rejected": len(ranked["visual_rejected"]),
        },
        "best": ranked["best"],
        "matches": ranked["matches"],
        "visual_rejected": ranked["visual_rejected"],
        "media_rejected": media_rejected,
        "download_failed": download_failed,
    }


def multi_search_and_rank(queries, target, limit_per_query=10, output_dir="data/search_previews"):
    all_assets = []
    seen = set()
    query_stats = {}

    for query in queries:
        assets = search_commons(query, limit=limit_per_query)
        query_stats[query] = len(assets)

        for asset in assets:
            identity = asset.get("pageid") or asset.get("description_url") or asset.get("original_url")

            if not identity or identity in seen:
                continue

            seen.add(identity)

            item = dict(asset)
            item["search_query"] = query
            all_assets.append(item)

    legal = filter_allowed(all_assets)
    accepted, media_rejected = filter_visual_candidates(legal)

    downloaded, download_failed = download_previews(
        accepted,
        output_dir=output_dir,
    )

    ranked = rank_licensed_candidates(target, downloaded)

    return {
        "queries": queries,
        "target": target,
        "query_stats": query_stats,
        "stats": {
            "search_found_raw": sum(query_stats.values()),
            "search_unique": len(all_assets),
            "duplicates_removed": sum(query_stats.values()) - len(all_assets),
            "rights_allowed": len(legal),
            "media_accepted": len(accepted),
            "media_rejected": len(media_rejected),
            "downloaded": len(downloaded),
            "download_failed": len(download_failed),
            "visual_matches": len(ranked["matches"]),
            "visual_rejected": len(ranked["visual_rejected"]),
        },
        "best": ranked["best"],
        "matches": ranked["matches"],
        "visual_rejected": ranked["visual_rejected"],
        "media_rejected": media_rejected,
        "download_failed": download_failed,
    }
