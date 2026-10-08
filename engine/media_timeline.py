from engine.timeline_builder import build_continuous_visual_timeline


def build_media_timeline(items, tolerance=0.05):
    """
    Convert Beat + Unified Media results into a continuous edit timeline.

    MASTER narration timing remains authoritative and immutable.
    This layer does not search for media and does not modify source assets.
    """

    result = build_continuous_visual_timeline(
        items,
        tolerance=tolerance,
    )

    manifest = []

    for index, clip in enumerate(result["clips"]):
        beat = clip.get("beat") or {}
        asset = clip.get("asset") or {}

        entry = {
            "index": index,
            "status": clip.get("status"),
            "media_type": clip.get("media_type"),

            "speech_start": clip.get("speech_start"),
            "speech_end": clip.get("speech_end"),

            "visual_start": clip.get("visual_start"),
            "visual_end": clip.get("visual_end"),
            "visual_duration": clip.get("visual_duration"),

            "voice_text": beat.get("voice_text", ""),

            "provider": asset.get("provider"),
            "provider_id": asset.get("provider_id"),
            "local_path": asset.get("local_path"),

            "visual_treatment": clip.get(
                "visual_treatment",
                clip.get("treatment"),
            ),

            "source_start": clip.get("source_start"),
            "source_end": clip.get("source_end"),

            "video_play_duration": clip.get("video_play_duration"),
            "freeze_duration": clip.get("freeze_duration"),
            "freeze_at_source_time": clip.get("freeze_at_source_time"),
        }

        manifest.append(entry)

    return {
        "status": result["status"],
        "manifest": manifest,
        "clip_count": result["clip_count"],
        "ready_count": result["ready_count"],
        "issues": result["issues"],
        "silence_regions": result["silence_regions"],
        "timeline_start": result["timeline_start"],
        "timeline_end": result["timeline_end"],
        "timeline_duration": result["timeline_duration"],
    }
