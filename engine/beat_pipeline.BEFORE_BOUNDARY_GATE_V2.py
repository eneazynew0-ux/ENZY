import json
import re

from engine.beat_planner import run_beat_planner
from engine.beat_boundary_gate import gate_beat_boundaries
from engine.beat_sync import sync_beats_to_scene
from engine.beat_grounding import build_local_grounding_context
from engine.beat_factual_gate_v2 import check_beat
from engine.beat_factual_sanitizer import sanitize_beat


def parse_planner_json(raw):
    if isinstance(raw, dict):
        return raw

    text = str(raw or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("BEAT_PLANNER_INVALID_JSON")

        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"BEAT_PLANNER_INVALID_JSON: {exc}"
            ) from exc

    if not isinstance(data, dict):
        raise ValueError("BEAT_PLANNER_ROOT_MUST_BE_OBJECT")

    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError("BEAT_PLANNER_MISSING_BEATS")

    return data


def scene_master_text(scene, timed_words):
    start = int(scene["source_word_start"])
    end = int(scene["source_word_end"])

    words = [
        w for w in timed_words
        if start <= int(w["script_index"]) <= end
    ]

    expected = list(range(start, end + 1))
    actual = [int(w["script_index"]) for w in words]

    if actual != expected:
        raise ValueError(
            f"MASTER_WORD_RANGE_INVALID: expected {start}-{end}"
        )

    return " ".join(str(w["word"]) for w in words)


def run_beat_pipeline(
    scene,
    timed_words,
    story_map,
    model,
    tokenizer,
    max_tokens=1400,
):
    raw = run_beat_planner(
        scene,
        timed_words,
        story_map,
        model,
        tokenizer,
        max_tokens=max_tokens,
    )

    planner = parse_planner_json(raw)
    proposed = planner["beats"]

    gated = gate_beat_boundaries(
        scene,
        proposed,
        timed_words,
    )

    synced = sync_beats_to_scene(
        scene,
        gated,
        timed_words,
    )

    parent_text = scene_master_text(
        scene,
        timed_words,
    )

    grounding = build_local_grounding_context(
        parent_text,
        story_map,
    )

    final_beats = []
    diagnostics = []

    for beat in synced:
        issues_before = check_beat(
            beat,
            beat["voice_text"],
            grounding,
        )

        cleaned = (
            sanitize_beat(beat, issues_before)
            if issues_before
            else dict(beat)
        )

        # Sanitizer must never gain control of MASTER boundaries.
        cleaned["source_word_start"] = beat["source_word_start"]
        cleaned["source_word_end"] = beat["source_word_end"]

        resynced = sync_beats_to_scene(
            {
                "source_word_start": beat["source_word_start"],
                "source_word_end": beat["source_word_end"],
            },
            [cleaned],
            timed_words,
        )[0]

        issues_after = check_beat(
            resynced,
            resynced["voice_text"],
            grounding,
        )

        high_after = [
            issue for issue in issues_after
            if str(issue.get("severity", "")).upper() == "HIGH"
        ]

        diagnostics.append({
            "source_word_start": resynced["source_word_start"],
            "source_word_end": resynced["source_word_end"],
            "issues_before": issues_before,
            "issues_after": issues_after,
        })

        if high_after:
            raise ValueError(
                "BEAT_FACTUAL_GATE_FAILED: "
                f"{resynced['source_word_start']}-"
                f"{resynced['source_word_end']} "
                f"{high_after}"
            )

        final_beats.append(resynced)

    # Final hard MASTER coverage check over the whole semantic scene.
    final_beats = sync_beats_to_scene(
        scene,
        final_beats,
        timed_words,
    )

    return {
        "scene": {
            "source_word_start": int(scene["source_word_start"]),
            "source_word_end": int(scene["source_word_end"]),
            "start": final_beats[0]["start"],
            "end": final_beats[-1]["end"],
        },
        "planner_reason": planner.get("reason", ""),
        "needs_multiple_beats": len(final_beats) > 1,
        "grounding_context": grounding,
        "beats": final_beats,
        "diagnostics": diagnostics,
    }
