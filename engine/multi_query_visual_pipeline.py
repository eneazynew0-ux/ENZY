from engine.multi_query_search import search_queries_raw
from engine.media_filter import filter_visual_candidates
from engine.media_downloader import download_previews
from engine.factual_identity_gate import check_factual_identity
from engine.export_rights_policy import check_export_asset


def run_multi_query_visual_pipeline(
    queries,
    target,
    limit_per_provider=10,
    output_dir="data/multi_query_previews",
    factual=False,
    visual_entity=None,
):
    search = search_queries_raw(
        queries,
        limit_per_provider=limit_per_provider,
    )

    identity_verified = []
    identity_rejected = []
    legal_assets = search["assets"]

    if factual:
        if not visual_entity:
            raise ValueError(
                "factual=True requires visual_entity"
            )

        for asset in legal_assets:
            identity = check_factual_identity(
                asset,
                visual_entity,
            )

            checked = dict(asset)
            checked["factual_identity"] = identity

            if identity["status"] == "VERIFIED":
                identity_verified.append(checked)
            else:
                identity_rejected.append(checked)

        export_input = identity_verified
    else:
        export_input = legal_assets

    # Identity and export rights are independent decisions. Check factual
    # identity first so a correct CC BY artifact is not lost as an anonymous
    # policy rejection, while flags and replicas never reach download/VLM.
    export_allowed = []
    export_rejected = []

    for asset in export_input:
        decision = check_export_asset(asset)
        item = dict(asset)
        item["export_rights"] = decision
        if decision["status"] == "EXPORT_ALLOWED":
            export_allowed.append(item)
        else:
            export_rejected.append(item)

    identity_input = export_allowed

    accepted, media_rejected = filter_visual_candidates(
        identity_input
    )

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

    if downloaded:
        # The visual judge is macOS/MLX-specific. Do not initialize it when
        # deterministic identity and rights gates already produced no work.
        from engine.candidate_ranker import rank_licensed_candidates

        ranked = rank_licensed_candidates(
            target,
            downloaded,
        )
    else:
        ranked = {
            "best": None,
            "matches": [],
            "visual_rejected": [],
        }

    return {
        "queries": search["queries"],
        "target": target,
        "provider_stats": search["provider_stats"],
        "query_stats": search["query_stats"],
        "stats": {
            **search["stats"],
            "export_rights_allowed": len(export_allowed),
            "export_rights_rejected": len(export_rejected),
            "identity_required": bool(factual),
            "identity_verified": (
                len(identity_verified)
                if factual
                else len(legal_assets)
            ),
            "identity_rejected": len(identity_rejected),
            "media_accepted": len(accepted),
            "media_rejected": len(media_rejected),
            "unavailable": len(unavailable),
            "downloaded": len(downloaded),
            "download_failed": len(download_failed),
            "visual_matches": len(ranked["matches"]),
            "visual_rejected": len(
                ranked["visual_rejected"]
            ),
        },
        "best": ranked["best"],
        "matches": ranked["matches"],
        "visual_rejected": ranked["visual_rejected"],
        "rights_rejected": search["rights_rejected"],
        "export_rights_rejected": export_rejected,
        "identity_verified": identity_verified,
        "identity_rejected": identity_rejected,
        "media_rejected": media_rejected,
        "unavailable": unavailable,
        "download_failed": download_failed,
    }


if __name__ == "__main__":
    queries = [
        "Nabta Playa",
        "Nabta Playa stone circle",
        "Nabta Playa megaliths",
        "ancient stone circle desert",
    ]

    target = (
        "The actual prehistoric stone circle and standing "
        "megaliths at Nabta Playa in the Nubian Desert of "
        "southern Egypt, archaeological site in an open "
        "arid desert landscape"
    )

    visual_entity = {
        "canonical_subject": "Nabta Playa",
        "subject_type": "archaeological site",
        "location": "southern Egypt",
        "aliases_or_descriptions": [
            "Nabta Playa stone circle",
            "Nabta Playa megaliths",
        ],
    }

    result = run_multi_query_visual_pipeline(
        queries,
        target,
        limit_per_provider=3,
        output_dir="data/multi_query_visual_test",
        factual=True,
        visual_entity=visual_entity,
    )

    print()
    print("PROVIDERS:", result["provider_stats"])
    print("STATS:", result["stats"])
    print()

    print("MATCHES:")

    for item in result["matches"]:
        asset = item.get("asset", {})

        print()
        print("SCORE:", item.get("score"))
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
        print("DESCRIPTION:", item.get("description"))
        print("LOCAL:", asset.get("local_path"))

    if result["stats"]["downloaded"] > result["stats"]["search_unique"]:
        raise SystemExit(
            "FAILED: downloaded more assets than unique search results"
        )

    if (
        result["stats"]["visual_matches"]
        + result["stats"]["visual_rejected"]
        != result["stats"]["downloaded"]
    ):
        raise SystemExit(
            "FAILED: not every downloaded preview was judged exactly once"
        )

    if not result["matches"]:
        raise SystemExit(
            "FAILED: no visual matches found"
        )

    print()
    print("MULTI-QUERY VISUAL PIPELINE BASIC TEST PASSED")
