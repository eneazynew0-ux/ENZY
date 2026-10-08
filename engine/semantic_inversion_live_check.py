"""Live beat-pipeline check for a quoted false historical claim."""

import json
from pathlib import Path

from mlx_lm import load

from engine.beat_pipeline import (
    BeatVisualValidationError,
    run_beat_pipeline,
    scene_master_text,
)
from engine.local_visual_brain import MODEL


def main():
    timed = json.loads(
        Path("data/timed_script_full_v2.json").read_text(encoding="utf-8")
    )
    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json").read_text(encoding="utf-8")
    )
    story_map = json.loads(
        Path("data/story_map.json").read_text(encoding="utf-8")
    )
    scenes = plan["scenes"] if isinstance(plan, dict) else plan
    scene = next(
        item
        for item in scenes
        if "учебник скажет" in scene_master_text(item, timed).casefold()
    )

    print(
        "SCENE:",
        scene["source_word_start"],
        scene["source_word_end"],
        scene_master_text(scene, timed),
    )
    print("LOADING QWEN...")
    model, tokenizer = load(MODEL)

    try:
        result = run_beat_pipeline(
            scene,
            timed,
            story_map,
            model,
            tokenizer,
        )
    except BeatVisualValidationError as exc:
        trace = {
            "status": "BLOCKED_UNSAFE_PLAN",
            "error": str(exc),
            "diagnostics": exc.diagnostics,
        }
        Path("/tmp/enzyvideo_semantic_inversion_live.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("FINAL: BLOCKED_UNSAFE_PLAN")
        print("ERROR:", exc)
        return 2

    Path("/tmp/enzyvideo_semantic_inversion_live.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for index, beat in enumerate(result["beats"], 1):
        print("BEAT", index, beat["voice_text"])
        print("VISUAL:", beat.get("visual_intent"))
        print("QUERIES:", beat.get("search_queries"))
    for diagnostic in result["diagnostics"]:
        issue_types = [
            issue.get("type") for issue in diagnostic.get("issues_after", [])
        ]
        print("FINAL ISSUES:", issue_types)
        print("REPAIR ATTEMPTS:", len(diagnostic.get("repair_attempts", [])))
    print("TRACE: /tmp/enzyvideo_semantic_inversion_live.json")
    print("FINAL: SAFE_PLAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
