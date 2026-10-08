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
