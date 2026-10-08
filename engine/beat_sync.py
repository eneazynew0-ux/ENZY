def _master_words_in_range(timed_words, start_idx, end_idx):
    words = [
        w for w in timed_words
        if start_idx <= int(w["script_index"]) <= end_idx
    ]

    if not words:
        raise ValueError(
            f"No MASTER words found for range {start_idx}->{end_idx}"
        )

    expected = list(range(start_idx, end_idx + 1))
    actual = [int(w["script_index"]) for w in words]

    if actual != expected:
        raise ValueError(
            f"MASTER word range is not contiguous: "
            f"{start_idx}->{end_idx}"
        )

    return words


def sync_beat_to_master(beat, timed_words):
    start_idx = int(beat["source_word_start"])
    end_idx = int(beat["source_word_end"])

    if start_idx > end_idx:
        raise ValueError(
            f"Invalid beat range {start_idx}->{end_idx}"
        )

    words = _master_words_in_range(
        timed_words,
        start_idx,
        end_idx,
    )

    result = dict(beat)

    # MASTER is authoritative. Model-provided timing/text is ignored.
    result["source_word_start"] = start_idx
    result["source_word_end"] = end_idx
    result["start"] = float(words[0]["start"])
    result["end"] = float(words[-1]["end"])
    result["duration"] = result["end"] - result["start"]
    result["voice_text"] = " ".join(
        str(w["word"]) for w in words
    )

    return result


def sync_beats_to_scene(scene, beats, timed_words):
    if not beats:
        raise ValueError("Beat list is empty")

    scene_start = int(scene["source_word_start"])
    scene_end = int(scene["source_word_end"])

    ordered = sorted(
        beats,
        key=lambda b: int(b["source_word_start"])
    )

    synced = []
    expected_start = scene_start

    for beat in ordered:
        beat_start = int(beat["source_word_start"])
        beat_end = int(beat["source_word_end"])

        if beat_start != expected_start:
            raise ValueError(
                f"Beat coverage gap/overlap: expected "
                f"{expected_start}, got {beat_start}"
            )

        if beat_end > scene_end:
            raise ValueError(
                f"Beat ends outside scene: "
                f"{beat_end} > {scene_end}"
            )

        synced.append(
            sync_beat_to_master(beat, timed_words)
        )

        expected_start = beat_end + 1

    if expected_start != scene_end + 1:
        raise ValueError(
            f"Beat coverage incomplete: ended at "
            f"{expected_start - 1}, scene ends at {scene_end}"
        )

    return synced


if __name__ == "__main__":
    import json
    from pathlib import Path

    timed = json.loads(
        Path("data/timed_script_full_v2.json")
        .read_text(encoding="utf-8")
    )

    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json")
        .read_text(encoding="utf-8")
    )

    scene = next(
        s for s in plan["scenes"]
        if int(s["source_word_start"]) == 87
        and int(s["source_word_end"]) == 114
    )

    test_beats = [
        {
            "source_word_start": 87,
            "source_word_end": 96,
            "visual_intent": "Terracotta head buried in soil",
        },
        {
            "source_word_start": 97,
            "source_word_end": 106,
            "visual_intent": "Terracotta head used as a field scarecrow",
        },
        {
            "source_word_start": 107,
            "source_word_end": 114,
            "visual_intent": "Discovery and recognition of the object",
        },
    ]

    synced = sync_beats_to_scene(
        scene,
        test_beats,
        timed,
    )

    print("SCENE:", scene["source_word_start"], "->", scene["source_word_end"])
    print("BEATS:", len(synced))

    for i, beat in enumerate(synced, 1):
        print(
            i,
            "|",
            beat["source_word_start"],
            "->",
            beat["source_word_end"],
            "|",
            round(beat["start"], 2),
            "->",
            round(beat["end"], 2),
            "|",
            round(beat["duration"], 2),
            "s",
        )
        print(" ", beat["voice_text"])

    print("BEAT SYNC VALID")
