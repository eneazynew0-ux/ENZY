"""Live end-to-end diagnostic for a second historical artifact."""

import json
from pathlib import Path

from engine.multi_query_visual_pipeline import run_multi_query_visual_pipeline


def main():
    entity = {
        "canonical_subject": "Rosetta Stone",
        "subject_type": "historical stone artifact",
        "location": "British Museum, London",
        "aliases_or_descriptions": [
            "ancient Egyptian decree stone",
            "inscribed granodiorite stele",
        ],
        "_identity_scope": "ARTIFACT_GROUP",
    }
    target = (
        "A documentary photograph of the actual physical Rosetta Stone, "
        "showing the dark inscribed stone artifact itself. Do not accept "
        "a souvenir, replica, drawing, sign, unrelated museum object, or text-only graphic."
    )
    result = run_multi_query_visual_pipeline(
        ["Rosetta Stone artifact photograph"],
        target,
        limit_per_provider=10,
        output_dir="data/rosetta_stone_live_check",
        factual=True,
        visual_entity=entity,
    )

    trace_path = Path("/tmp/enzyvideo_rosetta_stone_live.json")
    trace_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("STATS:", json.dumps(result["stats"], ensure_ascii=False))
    print("TRACE:", trace_path)
    print("IDENTITY VERIFIED:", len(result["identity_verified"]))
    print("EXPORT REJECTED:", len(result["export_rights_rejected"]))

    if result["best"] is None:
        print("FINAL: NO_SUITABLE_ASSET")
        return 2

    best = result["best"]
    asset = best["asset"]
    print("FINAL: MATCH")
    print("TITLE:", asset.get("title"))
    print("SOURCE:", asset.get("description_url"))
    print("QUALITY:", asset.get("quality_label"))
    print("DESCRIPTION:", best.get("description"))
    print("SCORE:", best.get("score"))
    print("REASON:", best.get("reason"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
