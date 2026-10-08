from copy import deepcopy


def choose_asset_requirement(beat, phase):
    mode = beat.get("documentary_mode")
    strategy = beat.get("motion_strategy")
    role = phase.get("role")

    # Maps are generated/composed from one map context.
    if mode == "MAP":
        if role == "FOCUS":
            return "MAP_FOCUS"
        return "MAP_OVERVIEW"

    # Documents: establish document, then evidence/detail.
    if mode == "DOCUMENT":
        if role == "CONTEXT":
            return "DOCUMENT_PRIMARY"
        if role == "EVIDENCE":
            return "DOCUMENT_EVIDENCE"
        if role == "DETAIL":
            return "DOCUMENT_DETAIL"
        return "DOCUMENT_PRIMARY"

    # Archive sequence may benefit from a second archive asset,
    # but only when the phase actually changes semantic role.
    if mode == "ARCHIVE":
        if role == "EVIDENCE":
            return "SECOND_ARCHIVE_ASSET"
        return "ARCHIVE_PRIMARY"

    # Exact factual still: never invent video merely for motion.
    if mode == "FACTUAL_STILL":
        if role == "DETAIL":
            return "EXACT_PHOTO_DETAIL"
        return "EXACT_PHOTO_PRIMARY"

    # Identity-sensitive factual video.
    # PRIMARY keeps the verified video.
    # DETAIL first reuses another segment/detail from the same
    # verified source instead of automatically searching again.
    if mode == "FACTUAL_VIDEO":
        if role == "DETAIL":
            return "SAME_VERIFIED_VIDEO_DETAIL"
        if role == "ESTABLISH":
            return "VERIFIED_VIDEO_ESTABLISH"
        return "VERIFIED_VIDEO_PRIMARY"

    # Generic / illustrative video.
    if mode in {"REAL_VIDEO", "ILLUSTRATIVE_VIDEO"}:
        if role == "DETAIL":
            return "SAME_VIDEO_DETAIL_OR_SECOND_VIDEO"
        if role == "ESTABLISH":
            return "VIDEO_ESTABLISH"
        return "VIDEO_PRIMARY"

    # Conservative fallback.
    if strategy == "REAL_VIDEO_PRIMARY":
        return "VIDEO_PRIMARY"

    return "SAME_ASSET"


def requires_new_asset(requirement):
    """
    True means the phase should normally request another asset.
    False means reuse/composition from an existing asset is preferred.
    """
    return requirement in {
        "SECOND_ARCHIVE_ASSET",
        "DOCUMENT_EVIDENCE",
    }


def requires_identity_verification(beat, requirement):
    if not beat.get("identity_sensitive"):
        return False

    return requirement in {
        "VERIFIED_VIDEO_PRIMARY",
        "VERIFIED_VIDEO_ESTABLISH",
        "SAME_VERIFIED_VIDEO_DETAIL",
        "EXACT_PHOTO_PRIMARY",
        "EXACT_PHOTO_DETAIL",
    }


def plan_phase_asset(beat, phase):
    result = deepcopy(phase)

    requirement = choose_asset_requirement(beat, phase)

    result["asset_requirement"] = requirement
    result["requires_new_asset"] = requires_new_asset(requirement)
    result["requires_identity_verification"] = (
        requires_identity_verification(beat, requirement)
    )

    return result


def attach_asset_plan(beat):
    result = deepcopy(beat)

    phases = beat.get("retention_phases", [])

    result["retention_phases"] = [
        plan_phase_asset(beat, phase)
        for phase in phases
    ]

    return result


def plan_asset_sequence(beats):
    return [
        attach_asset_plan(beat)
        for beat in beats
    ]
