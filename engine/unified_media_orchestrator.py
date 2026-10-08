from engine.beat_search_orchestrator import run_beat_visual_search
from engine.beat_video_orchestrator import run_beat_video_search
from engine.unified_media_selector import select_media_for_beat
from engine.search_contract import visual_search_target, bound_contextual_identity


def run_unified_media_search(
    beat,
    scene_entities,
    target,
    model=None,
    tokenizer=None,
    verified_years=None,
    photo_limit_per_provider=10,
    video_limit_per_query=3,
    video_max_downloads=6,
    video_sample_interval=2.0,
    video_match_threshold=60,
    video_strong_segment_score=85,
    preference_margin=10.0,
    output_dir="data/unified_media_search",
):
    """
    Run the complete real-media search path for one visual beat.

    Flow:
        beat + grounding
        -> photo branch
        -> video branch
        -> unified media selection

    This layer does not modify the closed photo/video pipelines.
    """

    bound_contextual_identity(beat, scene_entities)
    target = visual_search_target(beat, target)
    photo_result = run_beat_visual_search(
        beat,
        scene_entities,
        target,
        model=model,
        tokenizer=tokenizer,
        verified_years=verified_years,
        limit_per_provider=photo_limit_per_provider,
        output_dir=f"{output_dir}/photo",
    )

    video_result = run_beat_video_search(
        beat,
        scene_entities,
        target,
        model=model,
        tokenizer=tokenizer,
        verified_years=verified_years,
        limit_per_query=video_limit_per_query,
        max_downloads=video_max_downloads,
        sample_interval=video_sample_interval,
        match_threshold=video_match_threshold,
        strong_segment_score=video_strong_segment_score,
        output_dir=f"{output_dir}/video",
    )

    photo_plan = photo_result.get("plan") or {}
    video_plan = video_result.get("plan") or {}

    factual_search = bool(
        photo_plan.get("factual_search")
        or video_plan.get("factual_search")
    )

    selection = select_media_for_beat(
        photo_result,
        video_result,
        factual_search=factual_search,
        preference_margin=preference_margin,
    )

    contextual_fallback = None

    if selection.get("status") != "SELECTED" and factual_search and not beat.get("visual_contract"):
        from engine.contextual_photo_fallback import search_contextual_photo

        excluded_subjects = []
        for plan in (photo_plan, video_plan):
            identity = plan.get("search_entity") or {}
            excluded_subjects.extend([
                identity.get("_source_canonical_subject"),
                identity.get("canonical_subject"),
            ])

        contextual_fallback = search_contextual_photo(
            beat,
            scene_entities,
            excluded_subjects,
            model,
            tokenizer,
            output_dir=f"{output_dir}/contextual_photo",
            limit_per_provider=photo_limit_per_provider,
        )
        if contextual_fallback.get("status") == "MATCH":
            selection = select_media_for_beat(
                contextual_fallback["photo_result"],
                {},
                factual_search=True,
                preference_margin=preference_margin,
            )
            selection["reason"] = (
                "Verified contextual cutaway; not footage of the original event."
            )

    selected = selection.get("selected")
    selected_asset = None
    selected_segment = None

    if selected:
        selected_asset = selected.get("asset")
        if selected_asset and beat.get("visual_contract"):
            selected_asset = dict(selected_asset)
            selected_asset["representation"] = {
                "mode": beat["visual_contract"]["mode"],
                "identity_scope": beat["visual_contract"]["identity_scope"],
                "depicts_original_event": False,
                "contextual_subject": beat["visual_contract"]["subject"],
            }

        if selected.get("media_type") == "VIDEO":
            selected_segment = selected.get("segment")

    return {
        "status": selection.get("status"),
        "beat": beat,
        "target": target,
        "scene_entities": scene_entities,
        "factual_search": factual_search,
        "photo_result": photo_result,
        "video_result": video_result,
        "selection": selection,
        "contextual_fallback": contextual_fallback,
        "selected_type": selection.get("selected_type"),
        "selected_asset": selected_asset,
        "selected_segment": selected_segment,
    }
