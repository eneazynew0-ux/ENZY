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
    overlap=120,
):
    """
    Memory-bounded long-form alignment using overlapping windows.

    Only the safe central portion of each window is committed.
    The overlap is re-aligned in the next window, preventing a bad
    match near a chunk boundary from skipping large parts of the script.
    """
    if not script_tokens or not whisper_words:
        return []

    total_script = len(script_tokens)
    total_whisper = len(whisper_words)

    matches = []
    script_start = 0
    whisper_anchor = 0

    while script_start < total_script and whisper_anchor < total_whisper:
        script_end = min(
            total_script,
            script_start + script_chunk_size,
        )

        remaining_script = total_script - script_start
        remaining_whisper = total_whisper - whisper_anchor
        ratio = remaining_whisper / max(remaining_script, 1)

        expected_whisper_count = int(
            (script_end - script_start) * ratio
        )

        whisper_end = min(
            total_whisper,
            whisper_anchor + expected_whisper_count + whisper_margin,
        )

        local_script = script_tokens[script_start:script_end]
        local_whisper = whisper_words[whisper_anchor:whisper_end]

        local_matches = align_token_sequences(
            local_script,
            local_whisper,
            min_similarity=min_similarity,
        )

        if not local_matches:
            # Never skip an entire chunk. Move only a small distance
            # and preserve the Whisper anchor for recovery.
            script_start += max(1, script_chunk_size - overlap)
            continue

        global_matches = [
            {
                "script_index": m["script_index"] + script_start,
                "whisper_index": m["whisper_index"] + whisper_anchor,
                "similarity": m["similarity"],
            }
            for m in local_matches
        ]

        is_last_window = script_end >= total_script

        if is_last_window:
            committed = global_matches
        else:
            safe_script_end = script_end - overlap
            committed = [
                m for m in global_matches
                if m["script_index"] < safe_script_end
            ]

        if not committed:
            # Do not jump to the last edge match.
            # Advance conservatively and try again with overlap.
            script_start += max(1, script_chunk_size - overlap)
            continue

        matches.extend(committed)

        last = committed[-1]

        # Resume immediately after the last SAFE committed match.
        # Uncommitted tail is intentionally reprocessed.
        script_start = last["script_index"] + 1
        whisper_anchor = last["whisper_index"] + 1

    clean = []
    seen_script = set()
    seen_whisper = set()

    for match in sorted(
        matches,
        key=lambda x: (x["script_index"], x["whisper_index"]),
    ):
        si = match["script_index"]
        wi = match["whisper_index"]

        if si in seen_script or wi in seen_whisper:
            continue

        seen_script.add(si)
        seen_whisper.add(wi)
        clean.append(match)

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
