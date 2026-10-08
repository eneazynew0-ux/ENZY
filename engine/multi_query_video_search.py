from engine.pixabay_provider import search_pixabay_videos
from engine.pexels_provider import search_pexels_videos
from engine.internet_archive_provider import (
    search_archive_videos,
    enrich_video_asset,
)
from engine.provider_registry import specialized_providers
from engine.rights_gate import check_asset
from engine.export_rights_policy import check_export_asset
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



def _apply_candidate_gates(raw_assets, factual=False, visual_entity=None):
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
            matched = existing.setdefault("matched_queries", [])

            for query in asset.get("matched_queries", []):
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

    export_allowed = []
    export_rejected = []

    for asset in rights_allowed:
        decision = check_export_asset(asset)
        item = dict(asset)
        item["export_rights"] = decision

        if decision.get("status") == "EXPORT_ALLOWED":
            export_allowed.append(item)
        else:
            export_rejected.append(item)

    identity_verified = []
    identity_rejected = []

    if factual:
        if not visual_entity:
            raise ValueError(
                "factual video search requires visual_entity"
            )

        for asset in export_allowed:
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
        final_assets = export_allowed

    return {
        "unique_assets": unique_assets,
        "duplicates_removed": duplicates_removed,
        "missing_identity": missing_identity,
        "rights_allowed": rights_allowed,
        "rights_rejected": rights_rejected,
        "export_allowed": export_allowed,
        "export_rejected": export_rejected,
        "identity_verified": identity_verified,
        "identity_rejected": identity_rejected,
        "final_assets": final_assets,
    }


def _search_internet_archive_fallback(
    queries,
    limit_per_query,
    factual=False,
    visual_entity=None,
):
    if "internet_archive" not in specialized_providers("video"):
        return {
            "raw_assets": [],
            "query_stats": [],
            "gates": _apply_candidate_gates(
                [],
                factual=factual,
                visual_entity=visual_entity,
            ),
        }

    raw_assets = []
    query_stats = []

    for query in queries:
        try:
            search_items = search_archive_videos(
                query,
                limit=limit_per_query,
            )

            items = []

            for asset in search_items:
                try:
                    enriched = enrich_video_asset(asset)
                except Exception:
                    continue

                item = dict(enriched)
                item["matched_queries"] = [query]
                items.append(item)

            error = None

        except Exception as exc:
            items = []
            error = str(exc)

        query_stats.append(
            {
                "query": query,
                "provider": "internet_archive",
                "found": len(items),
                "error": error,
            }
        )

        raw_assets.extend(items)

    gates = _apply_candidate_gates(
        raw_assets,
        factual=factual,
        visual_entity=visual_entity,
    )

    return {
        "raw_assets": raw_assets,
        "query_stats": query_stats,
        "gates": gates,
    }


def search_video_candidates(
    queries,
    limit_per_query=5,
    factual=False,
    visual_entity=None,
):
    queries = _dedupe_queries(queries)

    raw_assets = []
    query_stats = []

    # Generic video providers: Pixabay and Pexels.
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
                "provider": "pixabay",
                "found": len(items),
                "error": error,
            }
        )

        for asset in items:
            item = dict(asset)
            item["matched_queries"] = [query]
            raw_assets.append(item)

        try:
            items = search_pexels_videos(
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
                "provider": "pexels",
                "found": len(items),
                "error": error,
            }
        )

        for asset in items:
            item = dict(asset)
            item["matched_queries"] = [query]
            raw_assets.append(item)

    primary = _apply_candidate_gates(
        raw_assets,
        factual=factual,
        visual_entity=visual_entity,
    )

    fallback_used = False
    fallback_query_stats = []

    # Internet Archive is intentionally NOT part of normal generic search.
    # Archive candidates participate alongside stock candidates.
    if "internet_archive" in specialized_providers("video"):
        fallback = _search_internet_archive_fallback(
            queries,
            limit_per_query=limit_per_query,
            factual=factual,
            visual_entity=visual_entity,
        )

        fallback_used = not bool(primary["final_assets"])
        fallback_query_stats = fallback["query_stats"]

        combined_raw = raw_assets + fallback["raw_assets"]

        gates = _apply_candidate_gates(
            combined_raw,
            factual=factual,
            visual_entity=visual_entity,
        )
    else:
        gates = primary

    final_assets = gates["final_assets"]
    export_allowed = gates["export_allowed"]
    identity_verified = gates["identity_verified"]
    identity_rejected = gates["identity_rejected"]

    return {
        "queries": queries,
        "query_stats": query_stats + fallback_query_stats,
        "fallback_used": fallback_used,
        "fallback_provider": (
            "internet_archive"
            if fallback_used
            else None
        ),
        "stats": {
            "query_count": len(queries),
            "search_found_raw": (
                len(gates["unique_assets"])
                + gates["duplicates_removed"]
                + len(gates["missing_identity"])
            ),
            "search_unique": len(gates["unique_assets"]),
            "duplicates_removed": gates["duplicates_removed"],
            "missing_identity": len(gates["missing_identity"]),
            "rights_allowed": len(gates["rights_allowed"]),
            "rights_rejected": len(gates["rights_rejected"]),
            "export_rights_allowed": len(export_allowed),
            "export_rights_rejected": len(
                gates["export_rejected"]
            ),
            "identity_required": bool(factual),
            "identity_verified": (
                len(identity_verified)
                if factual
                else len(export_allowed)
            ),
            "identity_rejected": (
                len(identity_rejected)
                if factual
                else 0
            ),
            "final_candidates": len(final_assets),
            "specialized_fallback_used": fallback_used,
        },
        "assets": final_assets,
        "rights_rejected": gates["rights_rejected"],
        "export_rights_rejected": gates["export_rejected"],
        "identity_rejected": identity_rejected,
        "missing_identity": gates["missing_identity"],
    }

