import json

from engine.visual_judge import evaluate_image


def rank_candidates(target, image_paths):
    results = []

    for image_path in image_paths:
        try:
            result = evaluate_image(image_path, target)
        except Exception as exc:
            result = {
                "image": str(image_path),
                "target": target,
                "description": "",
                "decision": "REJECT",
                "score": 0,
                "reason": f"Visual Gate error: {exc}",
            }

        results.append(result)

    matches = [
        item for item in results
        if item.get("decision") == "MATCH"
    ]

    matches.sort(
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    rejected = [
        item for item in results
        if item.get("decision") != "MATCH"
    ]

    return {
        "target": target,
        "best": matches[0] if matches else None,
        "matches": matches,
        "rejected": rejected,
        "all": results,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise SystemExit(
            'Usage: python -m engine.candidate_ranker "TARGET" IMAGE [IMAGE ...]'
        )

    output = rank_candidates(
        sys.argv[1],
        sys.argv[2:],
    )

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )


def rank_licensed_candidates(target, assets):
    from engine.rights_gate import check_asset

    visual_candidates = []
    rights_rejected = []

    for asset in assets:
        rights = check_asset(asset)

        if rights.get("status") != "ALLOWED":
            rights_rejected.append({
                "asset": asset,
                "rights": rights,
                "decision": "REJECT",
                "score": 0,
                "reason": f"Rights Gate: {rights.get('reason', 'Not allowed')}",
            })
            continue

        image_path = asset.get("local_path")

        if not image_path:
            rights_rejected.append({
                "asset": asset,
                "rights": rights,
                "decision": "REJECT",
                "score": 0,
                "reason": "Missing local_path",
            })
            continue

        try:
            visual = evaluate_image(image_path, target)
        except Exception as exc:
            visual = {
                "image": str(image_path),
                "target": target,
                "description": "",
                "decision": "REJECT",
                "score": 0,
                "reason": f"Visual Gate error: {exc}",
            }
        visual["asset"] = asset
        visual["rights"] = rights
        visual_candidates.append(visual)

    matches = [
        item for item in visual_candidates
        if item.get("decision") == "MATCH"
    ]

    matches.sort(
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    visual_rejected = [
        item for item in visual_candidates
        if item.get("decision") != "MATCH"
    ]

    return {
        "target": target,
        "best": matches[0] if matches else None,
        "matches": matches,
        "visual_rejected": visual_rejected,
        "rights_rejected": rights_rejected,
    }
