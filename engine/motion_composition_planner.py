from copy import deepcopy


REAL_VIDEO_MODES = {
    "FACTUAL_VIDEO",
    "REAL_VIDEO",
    "ILLUSTRATIVE_VIDEO",
}


def plan_motion_composition(beat):
    """
    Adds motion/composition intent without modifying:
    - MASTER timing
    - selected media
    - source identity
    - factual identity requirements

    motion_strategy describes editing motion.
    real_video_preferred describes whether real video should be searched
    or preferred for the composition.
    """

    result = deepcopy(beat)

    mode = beat.get("documentary_mode")

    if mode in REAL_VIDEO_MODES:
        strategy = "REAL_VIDEO_PRIMARY"
        real_video_preferred = True
        composition = "SINGLE_OR_SEQUENCE"

    elif mode == "ARCHIVE":
        strategy = "ARCHIVE_VIDEO_OR_MOTION_STILL"
        real_video_preferred = True
        composition = "ARCHIVE_SEQUENCE"

    elif mode == "DOCUMENT":
        strategy = "DOCUMENT_WITH_MOTION_INSERT"
        real_video_preferred = True
        composition = "DOCUMENT_DETAIL_SEQUENCE"

    elif mode == "MAP":
        strategy = "ANIMATED_MAP"
        real_video_preferred = False
        composition = "MAP_SEQUENCE"

    elif mode == "FACTUAL_STILL":
        strategy = "MOTION_STILL"
        real_video_preferred = False
        composition = "FACTUAL_DETAIL_SEQUENCE"

    else:
        strategy = "SAFE_MOTION_STILL"
        real_video_preferred = False
        composition = "SINGLE_VISUAL"

    result["motion_strategy"] = strategy
    result["real_video_preferred"] = real_video_preferred
    result["composition_strategy"] = composition

    return result


def plan_motion_sequence(beats):
    return [
        plan_motion_composition(beat)
        for beat in beats
    ]
