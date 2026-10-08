import json
import re

from engine.beat_planner import run_beat_planner
from engine.beat_boundary_gate_v2 import gate_beat_boundaries_v2
from engine.beat_sync import sync_beats_to_scene
from engine.beat_grounding import build_local_grounding_context, build_causal_grounding_context
from engine.beat_factual_gate_v2 import check_beat
from engine.beat_factual_sanitizer import sanitize_beat
from engine.beat_semantic_gate import check_beat_semantics
from engine.beat_visual_repair import repair_beat_visual
from engine.beat_sequence_gate import check_adjacent_visual_repetition


class BeatVisualValidationError(ValueError):
    """Carries diagnostics even when the scene cannot safely proceed."""
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics



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
    max_visual_repairs=2,
):
    if isinstance(max_visual_repairs, bool) or not isinstance(max_visual_repairs, int) or not 0 <= max_visual_repairs <= 2:
        raise ValueError("max_visual_repairs must be an integer from 0 to 2")
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

    gated = gate_beat_boundaries_v2(
        scene,
        proposed,
        timed_words,
        model,
        tokenizer,
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
        preceding_words = sorted(
            (word for word in timed_words
             if int(word["script_index"]) < int(beat["source_word_start"])),
            key=lambda word: int(word["script_index"]),
        )[-80:]
        preceding_text = " ".join(str(word["word"]) for word in preceding_words)
        beat_grounding = build_causal_grounding_context(
            beat["voice_text"], preceding_text, story_map,
        )
        issues_before = check_beat(
            beat,
            beat["voice_text"],
            beat_grounding,
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
            beat_grounding,
        )

        semantic_grounding = beat_grounding
        issues_after.extend(check_beat_semantics(
            resynced, semantic_grounding, preceding_text,
            model, tokenizer,
        ))
        issues_after.extend(check_adjacent_visual_repetition(
            final_beats[-1] if final_beats else None,
            resynced,
        ))

        repair_attempts = []
        for attempt in range(max_visual_repairs):
            blocking = [issue for issue in issues_after
                        if str(issue.get("severity", "")).upper() == "HIGH"]
            if not blocking or any(issue.get("type") == "SEMANTIC_AUDIT_UNAVAILABLE" for issue in blocking):
                break
            record = {"attempt": attempt + 1, "issues_before": issues_after,
                      "visual_before": {key: resynced.get(key) for key in
                                        ("visual_intent", "search_queries", "requirements", "avoid", "edit")}}
            repair_attempts.append(record)
            try:
                repaired = repair_beat_visual(
                    resynced, blocking, semantic_grounding, preceding_text,
                    model, tokenizer,
                )
                resynced = sync_beats_to_scene(
                    {"source_word_start": beat["source_word_start"],
                     "source_word_end": beat["source_word_end"]},
                    [repaired], timed_words,
                )[0]
                issues_after = check_beat(resynced, resynced["voice_text"], beat_grounding)
                issues_after.extend(check_beat_semantics(
                    resynced, semantic_grounding, preceding_text, model, tokenizer,
                ))
                issues_after.extend(check_adjacent_visual_repetition(
                    final_beats[-1] if final_beats else None,
                    resynced,
                ))
                record["issues_after"] = issues_after
            except Exception as exc:
                record["error"] = str(exc)
                issues_after = [{"type": "VISUAL_REPAIR_UNAVAILABLE",
                                 "severity": "HIGH", "detail": str(exc)}]
                break

        high_after = [
            issue for issue in issues_after
            if str(issue.get("severity", "")).upper() == "HIGH"
        ]

        diagnostics.append({
            "identity_context": beat_grounding,
            "visual_final": {key: resynced.get(key) for key in
                             ("visual_intent", "search_queries", "requirements", "avoid", "edit")},
            "source_word_start": resynced["source_word_start"],
            "source_word_end": resynced["source_word_end"],
            "issues_before": issues_before,
            "issues_after": issues_after,
            "repair_attempts": repair_attempts,
        })

        if high_after:
            raise BeatVisualValidationError(
                "BEAT_FACTUAL_GATE_FAILED: "
                f"{resynced['source_word_start']}-"
                f"{resynced['source_word_end']} "
                f"{high_after}", diagnostics,
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
