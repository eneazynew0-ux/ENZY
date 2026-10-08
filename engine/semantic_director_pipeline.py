from copy import deepcopy

from engine.semantic_director import decide_with_local_model
from engine.treatment_resolver import resolve_treatment


def direct_clip(
    beat,
    timeline_clip,
    model,
    tokenizer,
    previous_treatment=None,
):
    """
    Semantic Director Pipeline V1.

    Qwen decides WHY the visual is being shown.
    Treatment Resolver decides HOW the existing visual moves.

    The pipeline must never modify:
    - MASTER speech timing
    - visual timing
    - selected media asset
    - selected video source segment
    """

    original = deepcopy(timeline_clip)

    semantic_result = decide_with_local_model(
        beat,
        timeline_clip,
        model,
        tokenizer,
    )

    decision = semantic_result["decision"]
    purpose = decision["purpose"]

    treatment = resolve_treatment(
        purpose=purpose,
        media_type=timeline_clip.get("media_type"),
        previous_treatment=previous_treatment,
        existing_treatment=timeline_clip.get("visual_treatment"),
        visual_duration=timeline_clip.get("visual_duration"),
    )

    directed = deepcopy(timeline_clip)

    directed["semantic_purpose"] = purpose
    directed["director_treatment"] = treatment
    directed["director_reason"] = decision.get("reason", "")
    directed["semantic_director_raw"] = semantic_result.get("raw")
    directed["semantic_director_parsed"] = semantic_result.get("parsed")

    protected_fields = [
        "speech_start",
        "speech_end",
        "visual_start",
        "visual_end",
        "visual_duration",
        "media_type",
        "provider",
        "provider_id",
        "local_path",
        "source_start",
        "source_end",
        "video_play_duration",
        "freeze_duration",
        "freeze_at_source_time",
    ]

    for field in protected_fields:
        if original.get(field) != directed.get(field):
            raise AssertionError(
                f"Protected field changed: {field}: "
                f"{original.get(field)!r} -> {directed.get(field)!r}"
            )

    return {
        "clip": directed,
        "semantic_result": semantic_result,
        "purpose": purpose,
        "treatment": treatment,
    }


def direct_sequence(
    beat_clip_pairs,
    model,
    tokenizer,
):
    """
    Direct a sequence while carrying previous treatment forward,
    preventing mechanical repetition between neighboring clips.
    """

    directed_clips = []
    previous_treatment = None

    for beat, timeline_clip in beat_clip_pairs:
        result = direct_clip(
            beat=beat,
            timeline_clip=timeline_clip,
            model=model,
            tokenizer=tokenizer,
            previous_treatment=previous_treatment,
        )

        clip = result["clip"]
        directed_clips.append(clip)
        previous_treatment = clip["director_treatment"]

    return {
        "status": "READY",
        "clips": directed_clips,
        "count": len(directed_clips),
    }
