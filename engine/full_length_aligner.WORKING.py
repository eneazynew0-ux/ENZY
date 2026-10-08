from engine.align_script import (
    normalize_word,
    word_similarity,
    align_token_sequences,
    build_timed_script,
    interpolate_missing_timings,
)


def align_full_length(
    script_tokens,
    whisper_words,
    min_similarity=0.72,
    script_chunk_size=450,
    whisper_margin=140,
):
    """
    Memory-bounded alignment for long narration.

    The proven DP aligner is reused on smaller sequential windows instead
    of constructing one huge matrix for the entire narration.
    """

    if not script_tokens or not whisper_words:
        return []

    total_script = len(script_tokens)
    total_whisper = len(whisper_words)

    matches = []

    script_start = 0
    whisper_start = 0

    while script_start < total_script and whisper_start < total_whisper:
        script_end = min(
            total_script,
            script_start + script_chunk_size,
        )

        remaining_script = total_script - script_start
        remaining_whisper = total_whisper - whisper_start

        ratio = remaining_whisper / max(remaining_script, 1)

        expected_whisper_count = int(
            (script_end - script_start) * ratio
        )

        whisper_end = min(
            total_whisper,
            whisper_start + expected_whisper_count + whisper_margin,
        )

        local_script = script_tokens[script_start:script_end]
        local_whisper = whisper_words[whisper_start:whisper_end]

        local_matches = align_token_sequences(
            local_script,
            local_whisper,
            min_similarity=min_similarity,
        )

        if not local_matches:
            # Conservative recovery: advance script while keeping enough
            # Whisper context for the next attempt.
            script_start = script_end
            continue

        global_matches = []

        for match in local_matches:
            global_matches.append({
                "script_index": match["script_index"] + script_start,
                "whisper_index": match["whisper_index"] + whisper_start,
                "similarity": match["similarity"],
            })

        matches.extend(global_matches)

        last = global_matches[-1]

        script_start = last["script_index"] + 1
        whisper_start = last["whisper_index"] + 1

    # Remove any accidental duplicate script/Whisper assignments.
    clean = []
    seen_script = set()
    seen_whisper = set()

    for match in matches:
        si = match["script_index"]
        wi = match["whisper_index"]

        if si in seen_script or wi in seen_whisper:
            continue

        seen_script.add(si)
        seen_whisper.add(wi)
        clean.append(match)

    clean.sort(key=lambda x: x["script_index"])

    return clean


def build_full_timed_script(
    script_tokens,
    whisper_words,
    min_similarity=0.72,
):
    matches = align_full_length(
        script_tokens,
        whisper_words,
        min_similarity=min_similarity,
    )

    timed = build_timed_script(
        script_tokens,
        whisper_words,
        matches,
    )

    timed = interpolate_missing_timings(
        timed,
        script_tokens,
    )

    return timed, matches
