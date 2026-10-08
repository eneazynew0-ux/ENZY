def sync_scene_to_master(scene, timed_words):
    """
    Validate LLM-selected word boundaries and derive authoritative
    scene timing/text exclusively from the immutable MASTER word map.
    """
    if not isinstance(scene, dict):
        raise ValueError("Scene must be a dictionary")

    if "source_word_start" not in scene or "source_word_end" not in scene:
        raise ValueError("Scene is missing source word boundaries")

    start_i = scene["source_word_start"]
    end_i = scene["source_word_end"]

    if not isinstance(start_i, int) or isinstance(start_i, bool):
        raise ValueError("source_word_start must be an integer")

    if not isinstance(end_i, int) or isinstance(end_i, bool):
        raise ValueError("source_word_end must be an integer")

    if start_i < 0 or end_i < 0:
        raise ValueError("Negative word index")

    if start_i > end_i:
        raise ValueError("Reversed word range")

    if end_i >= len(timed_words):
        raise ValueError("Word index outside MASTER")

    selected = timed_words[start_i:end_i + 1]

    start = selected[0]["start"]
    end = selected[-1]["end"]

    if start is None or end is None:
        raise ValueError("MASTER timing missing")

    if end < start:
        raise ValueError("Invalid MASTER timing")

    synced = dict(scene)

    # Never trust model-generated timing or narration text.
    synced["start"] = start
    synced["end"] = end
    synced["duration"] = end - start
    synced["voice_text"] = " ".join(
        word["word"] for word in selected
    )

    return synced


def sync_plan_to_master(scenes, timed_words, require_contiguous=True):
    """
    Sync an ordered scene plan to MASTER and reject overlaps,
    backwards ranges, and optionally narration gaps.
    """
    if not isinstance(scenes, list):
        raise ValueError("Scenes must be a list")

    synced = []
    previous_end_index = None

    for position, scene in enumerate(scenes):
        item = sync_scene_to_master(scene, timed_words)

        start_i = item["source_word_start"]
        end_i = item["source_word_end"]

        if previous_end_index is not None:
            if start_i <= previous_end_index:
                raise ValueError(
                    f"Scene {position}: overlapping/backwards word range"
                )

            if require_contiguous and start_i != previous_end_index + 1:
                raise ValueError(
                    f"Scene {position}: narration gap "
                    f"{previous_end_index + 1}-{start_i - 1}"
                )

        synced.append(item)
        previous_end_index = end_i

    return synced
