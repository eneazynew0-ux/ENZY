"""Live end-to-end diagnostic for a known historical location."""

import json
from pathlib import Path

from engine.multi_query_visual_pipeline import run_multi_query_visual_pipeline


def main():
    entity = {
        "canonical_subject": "Great Zimbabwe",
        "subject_type": "archaeological site",
        "location": "Masvingo Province, Zimbabwe",
        "aliases_or_descriptions": [
            "Great Zimbabwe stone ruins",
            "Great Enclosure",
            "Hill Complex",
        ],
    }
    target = (
        "A documentary photograph of the actual Great Zimbabwe archaeological "
        "site, with its dry-stone walls, Great Enclosure, or Hill Complex visibly "
        "present. Reject wildlife, generic landscapes, modern cities, flags, maps, "
        "Zimbabwe Bird artifacts, and unrelated stone ruins."
    )
    result = run_multi_query_visual_pipeline(
        ["Great Zimbabwe ruins photograph"],
        target,
        limit_per_provider=10,
        output_dir="data/great_zimbabwe_live_check",
        factual=True,
        visual_entity=entity,
    )

    trace_path = Path("/tmp/enzyvideo_great_zimbabwe_live.json")
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
