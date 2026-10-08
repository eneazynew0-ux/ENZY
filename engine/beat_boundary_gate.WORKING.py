from engine.visual_beats import find_candidate_beat_boundaries


def gate_beat_boundaries(scene, proposed_beats, timed_words):
    """
    Deterministically anchor LLM-proposed visual beats to semantic
    transition boundaries detected from immutable MASTER narration.

    The LLM may decide that multiple visual beats are useful.
    It does NOT control timing when MASTER candidate boundaries
    can fully define those beats.
    """
    if not proposed_beats:
        raise ValueError("No proposed beats")

    scene_start = int(scene["source_word_start"])
    scene_end = int(scene["source_word_end"])

    candidates = find_candidate_beat_boundaries(
        scene,
        timed_words,
    )

    candidate_starts = sorted({
        int(c["candidate_new_beat_start"])
        for c in candidates
        if scene_start < int(c["candidate_new_beat_start"]) <= scene_end
    })

    beat_count = len(proposed_beats)

    # One beat means the whole semantic scene.
    if beat_count == 1:
        result = [dict(proposed_beats[0])]
        result[0]["source_word_start"] = scene_start
        result[0]["source_word_end"] = scene_end
        return result

    # N beats require N-1 internal boundaries.
    #
    # If MASTER provides exactly that number of semantic candidate
    # boundaries, those boundaries are authoritative.
    if len(candidate_starts) == beat_count - 1:
        starts = [scene_start] + candidate_starts
        ends = [x - 1 for x in candidate_starts] + [scene_end]

        result = []

        for proposed, start, end in zip(
            proposed_beats,
            starts,
            ends,
        ):
            beat = dict(proposed)
            beat["source_word_start"] = start
            beat["source_word_end"] = end
            result.append(beat)

        return result

    # Ambiguous case:
    # do not silently guess which MASTER boundaries should be used.
    raise ValueError(
        "AMBIGUOUS_BEAT_BOUNDARIES: "
        f"{beat_count} proposed beats require "
        f"{beat_count - 1} boundaries, but MASTER supplied "
        f"{len(candidate_starts)} candidates: {candidate_starts}"
    )


if __name__ == "__main__":
    import json
    from pathlib import Path

    from engine.beat_sync import sync_beats_to_scene

    timed = json.loads(
        Path("data/timed_script_full_v2.json")
        .read_text(encoding="utf-8")
    )

    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json")
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

    proposed = raw["beats"]

    print("LLM PROPOSED:")
    for beat in proposed:
        print(
            beat["source_word_start"],
            "->",
            beat["source_word_end"],
        )

    gated = gate_beat_boundaries(
        scene,
        proposed,
        timed,
    )

    print("\nAFTER BOUNDARY GATE:")
    for beat in gated:
        print(
            beat["source_word_start"],
            "->",
            beat["source_word_end"],
        )

    synced = sync_beats_to_scene(
        scene,
        gated,
        timed,
    )

    print("\nMASTER SYNC:")
    for beat in synced:
        print(
            beat["source_word_start"],
            "->",
            beat["source_word_end"],
            "|",
            round(beat["start"], 2),
            "->",
            round(beat["end"], 2),
            "|",
            beat["voice_text"],
        )

    print("\nBOUNDARY GATE VALID")
