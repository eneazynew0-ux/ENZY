from copy import deepcopy

from engine.semantic_reframe import (
    apply_reframe_to_phase,
    full_frame,
    region_to_crop,
)


def choose_phase_crop(phase, semantic_region=None):
    """
    Deterministic crop policy.

    PRIMARY / CONTEXT:
        preserve the full source frame.

    DETAIL:
        use the semantic region when available.
        otherwise fail safely to full frame.
    """
    role = str(phase.get("role", "")).upper()

    if role != "DETAIL":
        return full_frame()

    if not semantic_region:
        return full_frame()

    return region_to_crop(semantic_region)


def apply_reframes_to_composed_clip(composed_clip, semantic_region=None):
    """
    Attach safe crop instructions to all visual phases without changing
    MASTER timing, media identity, or source asset.
    """
    result = deepcopy(composed_clip)

    phases = result.get("visual_phases", [])
    reframed = []

    for phase in phases:
        crop = choose_phase_crop(
            phase,
            semantic_region=semantic_region,
        )
        reframed.append(
            apply_reframe_to_phase(phase, crop)
        )

    result["visual_phases"] = reframed
    result["semantic_reframe_region"] = semantic_region

    return result
