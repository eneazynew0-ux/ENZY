import json
import re
from pathlib import Path


# High-risk concrete concepts that must be grounded in MASTER or Story Map.
# This list is intentionally conservative and will grow through tests.
CONCRETE_TERMS = {
    "chinese": ("chinese", "китай"),
    "china": ("china", "китай"),
    "jackfruit": ("jackfruit", "джекфрут"),
    "yam": ("yam", "yams", "ямс", "ямсов"),
    "nok": ("nok", "нок"),
    "nigeria": ("nigeria", "нигер"),
}


def normalize(text):
    text = str(text or "").lower()
    text = text.replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def supported(term_variants, evidence):
    evidence = normalize(evidence)
    return any(normalize(v) in evidence for v in term_variants)


def beat_generated_text(beat):
    parts = [
        beat.get("visual_intent", ""),
        beat.get("edit", ""),
    ]

    parts.extend(beat.get("search_queries", []) or [])
    parts.extend(beat.get("requirements", []) or [])
    parts.extend(beat.get("avoid", []) or [])

    return " ".join(str(x) for x in parts)


def factual_issues(beat, master_text, story_map):
    generated = normalize(beat_generated_text(beat))

    story_text = json.dumps(
        story_map,
        ensure_ascii=False,
    )

    evidence = normalize(master_text + " " + story_text)

    issues = []

    for canonical, variants in CONCRETE_TERMS.items():
        if not any(normalize(v) in generated for v in variants):
            continue

        if not supported(variants, evidence):
            issues.append({
                "type": "UNSUPPORTED_CONCRETE_DETAIL",
                "severity": "HIGH",
                "term": canonical,
                "detail": (
                    f"{canonical!r} appears in generated beat content "
                    "but is unsupported by MASTER + Story Map."
                ),
            })

    return issues


if __name__ == "__main__":
    from engine.beat_boundary_gate import gate_beat_boundaries
    from engine.beat_sync import sync_beats_to_scene

    timed = json.loads(
        Path("data/timed_script_full_v2.json")
        .read_text(encoding="utf-8")
    )

    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json")
        .read_text(encoding="utf-8")
    )

    story = json.loads(
        Path("data/story_map.json")
        .read_text(encoding="utf-8")
    )

    raw = json.loads(
        Path("data/beat_plan_scene7_raw.PROMPT_GATE_FAILED.json")
        .read_text(encoding="utf-8")
    )

    scene = next(
        s for s in plan["scenes"]
        if int(s["source_word_start"]) == 87
        and int(s["source_word_end"]) == 114
    )

    gated = gate_beat_boundaries(
        scene,
        raw["beats"],
        timed,
    )

    synced = sync_beats_to_scene(
        scene,
        gated,
        timed,
    )

    for i, beat in enumerate(synced, 1):
        issues = factual_issues(
            beat,
            beat["voice_text"],
            story,
        )

        print(
            f"BEAT {i}:",
            beat["source_word_start"],
            "->",
            beat["source_word_end"],
        )
        print("MASTER:", beat["voice_text"])

        if issues:
            for issue in issues:
                print(
                    issue["severity"],
                    "|",
                    issue["type"],
                    "|",
                    issue["term"],
                )
        else:
            print("FACTUAL ISSUES: []")

        print()

    print("FACTUAL GATE DIAGNOSTIC COMPLETE")
