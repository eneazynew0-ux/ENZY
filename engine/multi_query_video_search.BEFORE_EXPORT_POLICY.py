from engine.pixabay_provider import search_pixabay_videos
from engine.rights_gate import check_asset
from engine.factual_identity_gate import check_factual_identity


def _dedupe_queries(queries):
    result = []
    seen = set()

    for query in queries or []:
        query = str(query).strip()

        if not query:
            continue

        key = query.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(query)

    return result


def _asset_identity(asset):
    return (
        str(asset.get("provider", "")),
        str(
            asset.get("provider_id")
            or asset.get("identifier")
            or asset.get("pageid")
            or asset.get("source_url")
            or asset.get("original_url")
            or ""
        ),
    )


def search_video_candidates(
    queries,
    limit_per_query=5,
    factual=False,
    visual_entity=None,
):
    queries = _dedupe_queries(queries)

    raw_assets = []
    query_stats = []

    for query in queries:
        try:
            items = search_pixabay_videos(
                query,
                limit=limit_per_query,
            )
            error = None
        except Exception as exc:
            items = []
            error = str(exc)

        query_stats.append(
            {
                "query": query,
                "found": len(items),
                "error": error,
            }
        )

        for asset in items:
            item = dict(asset)
            item["matched_queries"] = [query]
            raw_assets.append(item)

    unique = {}
    duplicates_removed = 0
    missing_identity = []

    for asset in raw_assets:
        identity = _asset_identity(asset)

        if not identity[1]:
            missing_identity.append(asset)
            continue

        if identity in unique:
            duplicates_removed += 1

            existing = unique[identity]
            matched = existing.setdefault(
                "matched_queries",
                [],
            )

            for query in asset.get(
                "matched_queries",
                [],
            ):
                if query not in matched:
                    matched.append(query)

            continue

        unique[identity] = asset

    unique_assets = list(unique.values())

    rights_allowed = []
    rights_rejected = []

    for asset in unique_assets:
        decision = check_asset(asset)
        item = dict(asset)
        item["rights"] = decision

        if decision.get("status") == "ALLOWED":
            rights_allowed.append(item)
        else:
            rights_rejected.append(item)

    identity_verified = []
    identity_rejected = []

    if factual:
        if not visual_entity:
            raise ValueError(
                "factual video search requires visual_entity"
            )

        for asset in rights_allowed:
            result = check_factual_identity(
                asset,
                visual_entity,
            )

            item = dict(asset)
            item["factual_identity"] = result

            if result.get("status") == "VERIFIED":
                identity_verified.append(item)
            else:
                identity_rejected.append(item)

        final_assets = identity_verified

    else:
        final_assets = rights_allowed

    return {
        "queries": queries,
        "query_stats": query_stats,
        "stats": {
            "query_count": len(queries),
            "search_found_raw": len(raw_assets),
            "search_unique": len(unique_assets),
            "duplicates_removed": duplicates_removed,
            "missing_identity": len(missing_identity),
            "rights_allowed": len(rights_allowed),
            "rights_rejected": len(rights_rejected),
            "identity_required": bool(factual),
            "identity_verified": (
                len(identity_verified)
                if factual
                else len(rights_allowed)
            ),
            "identity_rejected": (
                len(identity_rejected)
                if factual
                else 0
            ),
            "final_candidates": len(final_assets),
        },
        "assets": final_assets,
        "rights_rejected": rights_rejected,
        "identity_rejected": identity_rejected,
        "missing_identity": missing_identity,
    }
