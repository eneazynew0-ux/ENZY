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
