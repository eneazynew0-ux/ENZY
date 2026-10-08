ALLOWED_COMPOSITIONS = {
    "SINGLE_VISUAL",
    "PRIMARY_THEN_DETAIL",
    "DETAIL_THEN_PRIMARY",
    "TWO_PHASE_VISUAL",
}

ALLOWED_PHASE_ROLES = {
    "PRIMARY",
    "DETAIL",
    "CONTEXT",
}


def build_composer_context(beat, directed_clip):
    return {
        "voice_text": beat.get("voice_text", ""),
        "visual_intent": beat.get("visual_intent", ""),
        "requirements": beat.get("requirements", []),
        "avoid": beat.get("avoid", []),
        "factual_priority": beat.get("factual_priority"),
        "semantic_purpose": directed_clip.get("semantic_purpose"),
        "media_type": directed_clip.get("media_type"),
        "visual_duration": directed_clip.get("visual_duration"),
        "director_treatment": directed_clip.get("director_treatment"),
    }


def choose_safe_composition(context):
    """
    Deterministic Visual Composer V1 baseline.

    This stage changes only the presentation structure.
    It does NOT:
    - change MASTER timing
    - change selected source media
    - search/download assets
    - invent factual content
    - add text/graphics
    """

    duration = float(context.get("visual_duration") or 0.0)
    purpose = context.get("semantic_purpose")
    media_type = context.get("media_type")

    if media_type == "VIDEO":
        return {
            "composition": "SINGLE_VISUAL",
            "phases": ["PRIMARY"],
            "reason": "Preserve continuous selected video.",
        }

    if media_type != "PHOTO":
        return {
            "composition": "SINGLE_VISUAL",
            "phases": ["PRIMARY"],
            "reason": "Unknown media type uses safest presentation.",
        }

    if duration < 7.0:
        return {
            "composition": "SINGLE_VISUAL",
            "phases": ["PRIMARY"],
            "reason": "Short still does not require structural subdivision.",
        }

    if purpose in {"DETAIL", "EVIDENCE", "REVEAL"}:
        return {
            "composition": "PRIMARY_THEN_DETAIL",
            "phases": ["PRIMARY", "DETAIL"],
            "reason": "Long factual still can benefit from a meaningful detail phase.",
        }

    if duration >= 10.0 and purpose in {"ESTABLISH", "ATMOSPHERE"}:
        return {
            "composition": "TWO_PHASE_VISUAL",
            "phases": ["CONTEXT", "PRIMARY"],
            "reason": "Long contextual still benefits from two restrained visual phases.",
        }

    return {
        "composition": "SINGLE_VISUAL",
        "phases": ["PRIMARY"],
        "reason": "Single visual remains the most restrained choice.",
    }


def apply_composition(directed_clip, composition):
    result = dict(directed_clip)

    before = {
        "speech_start": directed_clip.get("speech_start"),
        "speech_end": directed_clip.get("speech_end"),
        "visual_start": directed_clip.get("visual_start"),
        "visual_end": directed_clip.get("visual_end"),
        "visual_duration": directed_clip.get("visual_duration"),
        "media_type": directed_clip.get("media_type"),
        "local_path": directed_clip.get("local_path"),
        "provider": directed_clip.get("provider"),
        "provider_id": directed_clip.get("provider_id"),
    }

    name = composition.get("composition")
    phases = composition.get("phases") or []

    if name not in ALLOWED_COMPOSITIONS:
        name = "SINGLE_VISUAL"
        phases = ["PRIMARY"]

    phases = [
        phase for phase in phases
        if phase in ALLOWED_PHASE_ROLES
    ]

    if not phases:
        phases = ["PRIMARY"]

    result["composition"] = name
    result["composition_phases"] = phases
    result["composition_reason"] = composition.get("reason", "")

    after = {
        key: result.get(key)
        for key in before
    }

    assert before == after, "Visual Composer modified protected clip fields"

    return result


def build_visual_phases(composed_clip):
    """
    Convert composition roles into renderable visual phases.

    MASTER speech timing remains untouched.
    The phases exactly cover visual_start -> visual_end
    with no gaps and no overlaps.
    """

    visual_start = float(composed_clip["visual_start"])
    visual_end = float(composed_clip["visual_end"])
    duration = visual_end - visual_start

    if duration <= 0:
        raise ValueError("Visual duration must be positive")

    composition = composed_clip.get(
        "composition",
        "SINGLE_VISUAL",
    )

    roles = composed_clip.get(
        "composition_phases",
        ["PRIMARY"],
    )

    if composition == "SINGLE_VISUAL" or len(roles) == 1:
        return [{
            "phase_index": 0,
            "role": roles[0] if roles else "PRIMARY",
            "start": visual_start,
            "end": visual_end,
            "duration": duration,
            "source_asset": composed_clip.get("local_path"),
        }]

    if len(roles) != 2:
        raise ValueError(
            f"Unsupported phase count: {len(roles)}"
        )

    # Restrained documentary split:
    # first phase receives 60%, second receives 40%.
    split = visual_start + duration * 0.60

    phases = [
        {
            "phase_index": 0,
            "role": roles[0],
            "start": visual_start,
            "end": split,
            "duration": split - visual_start,
            "source_asset": composed_clip.get("local_path"),
        },
        {
            "phase_index": 1,
            "role": roles[1],
            "start": split,
            "end": visual_end,
            "duration": visual_end - split,
            "source_asset": composed_clip.get("local_path"),
        },
    ]

    tolerance = 1e-6

    assert abs(phases[0]["start"] - visual_start) <= tolerance
    assert abs(phases[-1]["end"] - visual_end) <= tolerance
    assert abs(phases[0]["end"] - phases[1]["start"]) <= tolerance

    covered = sum(
        phase["duration"]
        for phase in phases
    )

    assert abs(covered - duration) <= tolerance

    return phases


def attach_visual_phases(composed_clip):
    """
    Attach renderable phases without changing the parent clip.
    """

    result = dict(composed_clip)

    protected = {
        "speech_start": composed_clip.get("speech_start"),
        "speech_end": composed_clip.get("speech_end"),
        "visual_start": composed_clip.get("visual_start"),
        "visual_end": composed_clip.get("visual_end"),
        "visual_duration": composed_clip.get("visual_duration"),
        "media_type": composed_clip.get("media_type"),
        "local_path": composed_clip.get("local_path"),
        "provider": composed_clip.get("provider"),
        "provider_id": composed_clip.get("provider_id"),
    }

    result["visual_phases"] = build_visual_phases(
        composed_clip
    )

    for field, original_value in protected.items():
        assert result.get(field) == original_value, (
            f"Protected field changed: {field}"
        )

    return result
