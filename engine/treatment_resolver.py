PHOTO_TREATMENTS_BY_PURPOSE = {
    "ESTABLISH": [
        "SLOW_PULL_OUT",
        "PAN_LEFT_TO_RIGHT",
        "PAN_RIGHT_TO_LEFT",
        "ESTABLISHING_HOLD",
    ],
    "REVEAL": [
        "SLOW_PUSH_IN",
        "DETAIL_PUSH_IN",
        "SLOW_PULL_OUT",
    ],
    "DETAIL": [
        "DETAIL_PUSH_IN",
        "SLOW_PUSH_IN",
        "PAN_LEFT_TO_RIGHT",
        "PAN_RIGHT_TO_LEFT",
    ],
    "EVIDENCE": [
        "SLOW_PUSH_IN",
        "DETAIL_PUSH_IN",
        "PAN_LEFT_TO_RIGHT",
        "PAN_RIGHT_TO_LEFT",
    ],
    "ATMOSPHERE": [
        "SLOW_PULL_OUT",
        "PAN_LEFT_TO_RIGHT",
        "PAN_RIGHT_TO_LEFT",
        "ESTABLISHING_HOLD",
    ],
    "TRANSITION": [
        "PAN_LEFT_TO_RIGHT",
        "PAN_RIGHT_TO_LEFT",
        "SLOW_PULL_OUT",
    ],
}

VIDEO_TREATMENTS_BY_PURPOSE = {
    "ESTABLISH": ["NORMAL", "GENTLE_PUSH_IN"],
    "REVEAL": ["GENTLE_PUSH_IN", "NORMAL"],
    "DETAIL": ["GENTLE_PUSH_IN", "NORMAL"],
    "EVIDENCE": ["NORMAL", "GENTLE_PUSH_IN"],
    "ATMOSPHERE": ["NORMAL"],
    "TRANSITION": ["NORMAL"],
}


def _pick_without_repeating(options, previous_treatment=None):
    for treatment in options:
        if treatment != previous_treatment:
            return treatment

    return options[0]


def resolve_treatment(
    purpose,
    media_type,
    previous_treatment=None,
    existing_treatment=None,
    visual_duration=None,
):
    """
    Convert semantic purpose into a safe render treatment.

    AI decides WHY the visual is shown.
    This resolver decides HOW it moves.

    Timing and source media are never modified.
    """

    if media_type == "VIDEO":
        if existing_treatment == "VIDEO_THEN_FREEZE":
            return "VIDEO_THEN_FREEZE"

        options = VIDEO_TREATMENTS_BY_PURPOSE.get(
            purpose,
            ["NORMAL"],
        )

        return _pick_without_repeating(
            options,
            previous_treatment,
        )

    if media_type != "PHOTO":
        return "NONE"

    options = list(
        PHOTO_TREATMENTS_BY_PURPOSE.get(
            purpose,
            ["SLOW_PUSH_IN"],
        )
    )

    duration = float(visual_duration or 0.0)

    # Static hold should be exceptional, especially on longer stills.
    if duration >= 6.0 and len(options) > 1:
        options = [
            x for x in options
            if x != "ESTABLISHING_HOLD"
        ] or options

    # Avoid immediately repeating the same movement.
    treatment = _pick_without_repeating(
        options,
        previous_treatment,
    )

    # Avoid two consecutive pans in the same direction.
    if (
        previous_treatment == "PAN_LEFT_TO_RIGHT"
        and treatment == "PAN_LEFT_TO_RIGHT"
    ):
        if "PAN_RIGHT_TO_LEFT" in options:
            treatment = "PAN_RIGHT_TO_LEFT"

    elif (
        previous_treatment == "PAN_RIGHT_TO_LEFT"
        and treatment == "PAN_RIGHT_TO_LEFT"
    ):
        if "PAN_LEFT_TO_RIGHT" in options:
            treatment = "PAN_LEFT_TO_RIGHT"

    return treatment
