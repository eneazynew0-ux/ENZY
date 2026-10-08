import re


# Markers that often indicate a new visual state inside one semantic scene.
# They are candidates only — never authoritative cut points.
TRANSITION_MARKERS = (
    "а потом",
    "потом",
    "затем",
    "прежде чем",
    "после этого",
    "после",
    "and then",
    "then",
    "before",
    "after",
    "followed by",
)


def _normalize_token(word):
    return re.sub(r"[^\w\-]+", "", str(word or "").lower(), flags=re.UNICODE)


def find_candidate_beat_boundaries(scene, timed_words):
    """
    Return candidate internal visual-beat boundaries for one semantic scene.

    MASTER is immutable.
    No timestamps are invented.
    Boundaries are expressed only through existing script word indices.
    """
    start = int(scene["source_word_start"])
    end = int(scene["source_word_end"])

    words = [
        w for w in timed_words
        if start <= int(w["script_index"]) <= end
    ]

    candidates = []

    # Check multi-word markers first so "а потом" is not double-counted
    # as both "а потом" and "потом".
    marker_tokens = sorted(
        [(m, m.split()) for m in TRANSITION_MARKERS],
        key=lambda x: len(x[1]),
        reverse=True,
    )

    normalized = [_normalize_token(w["word"]) for w in words]
    consumed = set()

    for marker, tokens in marker_tokens:
        n = len(tokens)

        for i in range(len(words) - n + 1):
            positions = set(range(i, i + n))

            if positions & consumed:
                continue

            if normalized[i:i + n] != tokens:
                continue

            marker_start = int(words[i]["script_index"])
            marker_end = int(words[i + n - 1]["script_index"])

            candidates.append({
                "marker": marker,
                "marker_word_start": marker_start,
                "marker_word_end": marker_end,
                "candidate_new_beat_start": marker_start,
                "time": float(words[i]["start"]),
            })

            consumed.update(positions)

    candidates.sort(key=lambda x: x["marker_word_start"])
    return candidates


if __name__ == "__main__":
    import json
    from pathlib import Path

    timed = json.loads(
        Path("data/timed_script_full_v2.json").read_text(encoding="utf-8")
    )
    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json").read_text(encoding="utf-8")
    )

    scene = next(
        s for s in plan["scenes"]
        if int(s["source_word_start"]) == 87
        and int(s["source_word_end"]) == 114
    )

    print("SCENE:", scene["source_word_start"], "->", scene["source_word_end"])
    print("CANDIDATE BEAT BOUNDARIES:")

    for item in find_candidate_beat_boundaries(scene, timed):
        print(item)
