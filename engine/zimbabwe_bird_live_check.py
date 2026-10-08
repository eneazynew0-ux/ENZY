"""Live end-to-end diagnostic for the Zimbabwe Bird control case."""

import json
from pathlib import Path

from engine.multi_query_visual_pipeline import run_multi_query_visual_pipeline


ENTITY = {
    "canonical_subject": "Zimbabwe Bird",
    "subject_type": "soapstone sculpture",
    "location": "Great Zimbabwe",
    "aliases_or_descriptions": ["carved soapstone bird"],
    "_identity_scope": "ARTIFACT_GROUP",
}

TARGET = (
    "A documentary photograph of the actual physical Zimbabwe Bird "
    "soapstone sculpture. The main visible subject must be a carved bird "
    "artifact, not a flag, logo, emblem, stamp, drawing, or modern replica."
)


def main():
    result = run_multi_query_visual_pipeline(
        ["Zimbabwe Bird"],
        TARGET,
        limit_per_provider=10,
        output_dir="data/zimbabwe_bird_live_check",
        factual=True,
        visual_entity=ENTITY,
    )

    trace_path = Path("/tmp/enzyvideo_zimbabwe_bird_live.json")
    trace_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("STATS:", json.dumps(result["stats"], ensure_ascii=False))
    print("TRACE:", trace_path)

    for item in result["identity_verified"]:
        identity = item["factual_identity"]
        print(
            "IDENTITY VERIFIED:",
            identity["identity_label"],
            item.get("title"),
            item.get("quality_label"),
        )

    for item in result["export_rights_rejected"]:
        print(
            "EXPORT REJECTED:",
            item.get("title"),
            item["export_rights"]["reason"],
        )

    if result["best"] is None:
        print("FINAL: NO_SUITABLE_ASSET")
        return 2

    best = result["best"]
    asset = best["asset"]
    print("FINAL: MATCH")
    print("TITLE:", asset.get("title"))
    print("SOURCE:", asset.get("description_url"))
    print("LOCAL:", asset.get("local_path"))
    print("QUALITY:", asset.get("quality_label"))
    print("DESCRIPTION:", best.get("description"))
    print("SCORE:", best.get("score"))
    print("REASON:", best.get("reason"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
