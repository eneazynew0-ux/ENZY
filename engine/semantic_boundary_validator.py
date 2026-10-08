def _scene_words(scene, timed_words):
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
            "SEMANTIC_BOUNDARY_MASTER_RANGE_INVALID"
        )

    return words


def validate_boundary_index(scene, boundary_index, timed_words):
    """
    Structural MASTER validation for a proposed semantic beat boundary.

    boundary_index means:
        first MASTER word of the NEW beat.

    This function does NOT decide whether the boundary is semantically good.
    It only proves that the proposed cut is structurally legal.
    """

    words = _scene_words(scene, timed_words)

    scene_start = int(scene["source_word_start"])
    scene_end = int(scene["source_word_end"])
    boundary = int(boundary_index)

    if boundary <= scene_start:
        return {
            "valid": False,
            "reason": "BOUNDARY_AT_OR_BEFORE_SCENE_START",
        }

    if boundary > scene_end:
        return {
            "valid": False,
            "reason": "BOUNDARY_AFTER_SCENE_END",
        }

    by_index = {
        int(w["script_index"]): w
        for w in words
    }

    if boundary not in by_index:
        return {
            "valid": False,
            "reason": "BOUNDARY_NOT_IN_MASTER",
        }

    previous = boundary - 1

    if previous not in by_index:
        return {
            "valid": False,
            "reason": "PREVIOUS_MASTER_WORD_MISSING",
        }

    return {
        "valid": True,
        "reason": "STRUCTURALLY_VALID",
        "boundary_index": boundary,
        "previous_word_index": previous,
        "previous_word": str(by_index[previous]["word"]),
        "new_beat_word": str(by_index[boundary]["word"]),
        "time": float(by_index[boundary]["start"]),
    }


def build_boundary_context(
    scene,
    boundary_index,
    timed_words,
    radius=6,
):
    """
    Return a small immutable MASTER window around a structurally valid
    proposed boundary. This will later be given to the semantic judge.
    """

    check = validate_boundary_index(
        scene,
        boundary_index,
        timed_words,
    )

    if not check["valid"]:
        raise ValueError(check["reason"])

    words = _scene_words(scene, timed_words)

    boundary = int(boundary_index)

    left = [
        {
            "script_index": int(w["script_index"]),
            "word": str(w["word"]),
        }
        for w in words
        if boundary - radius <= int(w["script_index"]) < boundary
    ]

    right = [
        {
            "script_index": int(w["script_index"]),
            "word": str(w["word"]),
        }
        for w in words
        if boundary <= int(w["script_index"]) < boundary + radius
    ]

    return {
        "scene_start": int(scene["source_word_start"]),
        "scene_end": int(scene["source_word_end"]),
        "proposed_new_beat_start": boundary,
        "left_master_words": left,
        "right_master_words": right,
    }
