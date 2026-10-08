from copy import deepcopy

from engine.beat_boundary_gate import gate_beat_boundaries
from engine.semantic_boundary_validator import validate_boundary_index
from engine.semantic_boundary_judge import judge_semantic_boundary


def _reconstruct_from_starts(scene, proposed_beats, boundary_starts):
    scene_start = int(scene["source_word_start"])
    scene_end = int(scene["source_word_end"])

    starts = [scene_start] + [int(x) for x in boundary_starts]

    if starts != sorted(starts):
        raise ValueError("SEMANTIC_BOUNDARIES_NOT_ORDERED")

    if len(set(starts)) != len(starts):
        raise ValueError("SEMANTIC_BOUNDARIES_DUPLICATED")

    if len(starts) != len(proposed_beats):
        raise ValueError("SEMANTIC_BOUNDARY_COUNT_MISMATCH")

    rebuilt = []

    for i, start in enumerate(starts):
        end = (
            starts[i + 1] - 1
            if i + 1 < len(starts)
            else scene_end
        )

        beat = deepcopy(proposed_beats[i])
        beat["source_word_start"] = start
        beat["source_word_end"] = end
        rebuilt.append(beat)

    return rebuilt


def gate_beat_boundaries_v2(
    scene,
    proposed_beats,
    timed_words,
    model,
    tokenizer,
):
    # First preserve all proven deterministic V1 behavior.
    try:
        return gate_beat_boundaries(
            scene,
            proposed_beats,
            timed_words,
        )
    except ValueError as exc:
        if "AMBIGUOUS_BEAT_BOUNDARIES" not in str(exc):
            raise

    if not proposed_beats:
        raise ValueError("NO_PROPOSED_BEATS")

    if len(proposed_beats) == 1:
        return gate_beat_boundaries(
            scene,
            proposed_beats,
            timed_words,
        )

    # In the ambiguous case, only proposed START indices matter.
    # Proposed END indices are never trusted.
    boundary_starts = [
        int(beat["source_word_start"])
        for beat in proposed_beats[1:]
    ]

    if len(set(boundary_starts)) != len(boundary_starts):
        raise ValueError("SEMANTIC_BOUNDARIES_DUPLICATED")

    if boundary_starts != sorted(boundary_starts):
        raise ValueError("SEMANTIC_BOUNDARIES_NOT_ORDERED")

    decisions = []

    for boundary in boundary_starts:
        structural = validate_boundary_index(
            scene,
            boundary,
            timed_words,
        )

        if not structural["valid"]:
            raise ValueError(
                "SEMANTIC_BOUNDARY_STRUCTURAL_REJECT: "
                f"{boundary}: {structural['reason']}"
            )

        semantic = judge_semantic_boundary(
            scene,
            boundary,
            timed_words,
            model,
            tokenizer,
        )

        decisions.append(semantic)

        if not semantic["approve"]:
            # Conservative production fallback:
            # never invent a questionable cut and never fail the whole scene.
            # Return one beat spanning the complete semantic scene.
            fallback = deepcopy(proposed_beats[0])
            fallback["source_word_start"] = int(scene["source_word_start"])
            fallback["source_word_end"] = int(scene["source_word_end"])
            fallback["boundary_fallback"] = "single_beat"
            fallback["boundary_reject_index"] = int(boundary)
            fallback["boundary_reject_reason"] = semantic["reason"]
            return [fallback]

    rebuilt = _reconstruct_from_starts(
        scene,
        proposed_beats,
        boundary_starts,
    )

    return rebuilt
