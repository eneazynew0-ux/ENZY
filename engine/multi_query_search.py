from engine.multi_provider_search import (
    search_wikimedia,
    search_internet_archive,
)
from engine.pixabay_provider import search_pixabay_photos
from engine.pexels_provider import search_pexels_photos
from engine.rights_gate import check_asset


def _identity(asset):
    provider = asset.get("provider", "unknown")

    identity = (
        asset.get("pageid")
        or asset.get("identifier")
        or asset.get("provider_id")
        or asset.get("description_url")
        or asset.get("original_url")
    )

    if not identity:
        return None

    return provider, str(identity)


def search_queries_raw(queries, limit_per_provider=10):
    """
    Search all providers for multiple query variants.

    No downloads and no VLM work happen here.
    Duplicate assets are merged before expensive stages.
    """

    unique_queries = []
    seen_queries = set()

    for query in queries:
        query = " ".join(str(query or "").split())

        if not query:
            continue

        key = query.casefold()

        if key in seen_queries:
            continue

        seen_queries.add(key)
        unique_queries.append(query)

    provider_stats = {
        "wikimedia": 0,
        "internet_archive": 0,
        "pixabay": 0,
        "pexels": 0,
    }

    query_stats = {}
    raw_assets = []

    for query in unique_queries:
        query_stats[query] = {
            "wikimedia": 0,
            "internet_archive": 0,
            "pixabay": 0,
            "pexels": 0,
        }

        try:
            assets = search_wikimedia(
                query,
                limit=limit_per_provider,
            )
            query_stats[query]["wikimedia"] = len(assets)
            provider_stats["wikimedia"] += len(assets)
            raw_assets.extend(assets)
        except Exception as exc:
            query_stats[query]["wikimedia_error"] = str(exc)

        try:
            assets = search_internet_archive(
                query,
                limit=limit_per_provider,
            )
            query_stats[query]["internet_archive"] = len(assets)
            provider_stats["internet_archive"] += len(assets)
            raw_assets.extend(assets)
        except Exception as exc:
            query_stats[query]["internet_archive_error"] = str(exc)

        try:
            assets = search_pixabay_photos(
                query,
                limit=limit_per_provider,
            )

            for asset in assets:
                asset["search_query"] = query

            query_stats[query]["pixabay"] = len(assets)
            provider_stats["pixabay"] += len(assets)
            raw_assets.extend(assets)
        except Exception as exc:
            query_stats[query]["pixabay_error"] = str(exc)

        try:
            assets = search_pexels_photos(
                query,
                limit=limit_per_provider,
            )

            for asset in assets:
                asset["search_query"] = query

            query_stats[query]["pexels"] = len(assets)
            provider_stats["pexels"] += len(assets)
            raw_assets.extend(assets)
        except Exception as exc:
            query_stats[query]["pexels_error"] = str(exc)

    merged = {}
    no_identity = []

    for asset in raw_assets:
        key = _identity(asset)

        if key is None:
            no_identity.append(asset)
            continue

        query = asset.get("search_query")

        if key not in merged:
            item = dict(asset)
            item["matched_queries"] = []
            merged[key] = item

        if (
            query
            and query not in merged[key]["matched_queries"]
        ):
            merged[key]["matched_queries"].append(query)

    unique_assets = list(merged.values())

    legal = []
    rights_rejected = []

    for asset in unique_assets:
        rights = check_asset(asset)
        item = dict(asset)
        item["rights"] = rights

        if rights.get("status") == "ALLOWED":
            legal.append(item)
        else:
            rights_rejected.append(item)

    return {
        "queries": unique_queries,
        "provider_stats": provider_stats,
        "query_stats": query_stats,
        "stats": {
            "query_count": len(unique_queries),
            "search_found_raw": len(raw_assets),
            "search_unique": len(unique_assets),
            "duplicates_removed": (
                len(raw_assets) - len(unique_assets)
            ),
            "missing_identity": len(no_identity),
            "rights_allowed": len(legal),
            "rights_rejected": len(rights_rejected),
        },
        "assets": legal,
        "rights_rejected": rights_rejected,
        "missing_identity": no_identity,
    }


if __name__ == "__main__":
    queries = [
        "Nabta Playa",
        "Nabta Playa stone circle",
        "Nabta Playa megaliths",
        "ancient stone circle desert",
        "Nabta Playa",
    ]

    result = search_queries_raw(
        queries,
        limit_per_provider=3,
    )

    print("QUERIES:", len(result["queries"]))
    print("PROVIDERS:", result["provider_stats"])
    print("STATS:", result["stats"])

    duplicates_with_multiple_queries = [
        asset
        for asset in result["assets"]
        if len(asset.get("matched_queries", [])) > 1
    ]

    print(
        "MULTI-QUERY MATCHES:",
        len(duplicates_with_multiple_queries),
    )

    for asset in duplicates_with_multiple_queries[:5]:
        print()
        print("PROVIDER:", asset.get("provider"))
        print(
            "ID:",
            asset.get("pageid")
            or asset.get("identifier")
            or asset.get("provider_id"),
        )
        print(
            "MATCHED QUERIES:",
            asset.get("matched_queries"),
        )

    if len(result["queries"]) != 4:
        raise SystemExit(
            "FAILED: query dedupe did not work"
        )

    if result["stats"]["search_unique"] > result["stats"]["search_found_raw"]:
        raise SystemExit(
            "FAILED: impossible dedupe statistics"
        )

    if not result["assets"]:
        raise SystemExit(
            "FAILED: no rights-approved assets"
        )

    print()
    print("MULTI-QUERY SEARCH AGGREGATION BASIC TEST PASSED")
