import json

from mlx_lm import load

from engine.scene_refiner import MODEL
from engine.refinement_controller import run_refinement_cycle
from engine.scene_sync import sync_plan_to_master


def flagged_scene_numbers(validation_report):
    return [
        int(item["scene"])
        for item in validation_report
        if item.get("issues")
    ]


def refine_flagged_plan(
    scenes,
    validation_report,
    timed_words,
    story_map,
    max_repairs=2,
):
    flagged = set(flagged_scene_numbers(validation_report))

    issue_map = {
        int(item["scene"]): item.get("issues", [])
        for item in validation_report
    }

    model, tokenizer = load(MODEL)

    output = []
    results = []

    for scene_number, scene in enumerate(scenes, 1):
        if scene_number not in flagged:
            output.append(scene)
            results.append({
                "scene": scene_number,
                "status": "UNCHANGED",
                "input_range": [
                    scene["source_word_start"],
                    scene["source_word_end"],
                ],
                "output_count": 1,
            })
            continue

        result = run_refinement_cycle(
            scene,
            issue_map[scene_number],
            timed_words,
            story_map,
            max_repairs=max_repairs,
            model=model,
            tokenizer=tokenizer,
        )

        refined = result["scenes"]
        output.extend(refined)

        results.append({
            "scene": scene_number,
            "status": result["status"],
            "input_range": [
                scene["source_word_start"],
                scene["source_word_end"],
            ],
            "output_ranges": [
                [
                    x["source_word_start"],
                    x["source_word_end"],
                ]
                for x in refined
            ],
            "output_count": len(refined),
            "repairs_used": result.get("repairs_used"),
            "history": result.get("history", []),
        })

    synced = sync_plan_to_master(
        output,
        timed_words,
        require_contiguous=True,
    )

    return {
        "scenes": synced,
        "results": results,
        "flagged_scenes": sorted(flagged),
    }


if __name__ == "__main__":
    print("REFINEMENT BATCH MODULE: OK")
