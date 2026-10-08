import json
from pathlib import Path

from mlx_lm import load

from engine.local_visual_brain import MODEL
from engine.beat_pipeline import run_beat_pipeline


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

print("LOADING QWEN ONCE...")
model, tokenizer = load(MODEL)

results = []
failures = []

for number, scene in enumerate(scenes, 1):
    a = int(scene["source_word_start"])
    b = int(scene["source_word_end"])

    print(f"\nSCENE {number}/{len(scenes)} | {a}->{b}")

    try:
        result = run_beat_pipeline(
            scene,
            timed,
            story_map,
            model,
            tokenizer,
        )

        results.append({
            "scene_number": number,
            "result": result,
        })

        print(f"PASS | BEATS={len(result['beats'])}")

        for i, beat in enumerate(result["beats"], 1):
            print(
                f"  B{i}: "
                f"{beat['source_word_start']}->{beat['source_word_end']} | "
                f"{beat['start']:.2f}->{beat['end']:.2f}"
            )

        for d in result["diagnostics"]:
            print(
                f"  FACT {d['source_word_start']}->{d['source_word_end']} | "
                f"BEFORE={len(d['issues_before'])} | "
                f"AFTER={len(d['issues_after'])}"
            )

    except Exception as exc:
        failures.append({
            "scene_number": number,
            "source_word_start": a,
            "source_word_end": b,
            "error": str(exc),
        })

        print(
            f"FAIL | {type(exc).__name__}: {exc}"
        )

output = {
    "total_scenes": len(scenes),
    "passed": len(results),
    "failed": len(failures),
    "results": results,
    "failures": failures,
}

Path("data/beat_pipeline_90s_no_storymap_test.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("\n==============================")
print("NO-STORYMAP 90S TEST COMPLETE")
print("TOTAL:", len(scenes))
print("PASS:", len(results))
print("FAIL:", len(failures))

if failures:
    print("\nFAILURES:")
    for f in failures:
        print(
            f"SCENE {f['scene_number']} "
            f"{f['source_word_start']}->{f['source_word_end']} | "
            f"{f['error']}"
        )

print("\nSAVED: data/beat_pipeline_90s_no_storymap_test.json")
