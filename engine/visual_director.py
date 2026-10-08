PHOTO_TREATMENTS = (
    "SLOW_PUSH_IN",
    "SLOW_PULL_OUT",
    "PAN_LEFT_TO_RIGHT",
    "PAN_RIGHT_TO_LEFT",
)


def _photo_treatment(index, previous_treatment=None):
    treatment = PHOTO_TREATMENTS[index % len(PHOTO_TREATMENTS)]

    if treatment == previous_treatment:
        treatment = PHOTO_TREATMENTS[
            (index + 1) % len(PHOTO_TREATMENTS)
        ]

    return treatment


def direct_visual_timeline(media_timeline):
    """
    Assign non-destructive visual treatments to an existing media timeline.

    This layer:
    - never changes MASTER speech timing
    - never changes visual timing
    - never searches or replaces media
    - never modifies source files
    """

    source_manifest = media_timeline.get("manifest") or []
    directed = []

    previous_photo_treatment = None

    for index, source in enumerate(source_manifest):
        clip = dict(source)

        original_speech_start = clip.get("speech_start")
        original_speech_end = clip.get("speech_end")
        original_visual_start = clip.get("visual_start")
        original_visual_end = clip.get("visual_end")

        media_type = clip.get("media_type")
        existing_treatment = clip.get("visual_treatment")

        if media_type == "PHOTO":
            treatment = _photo_treatment(
                index,
                previous_photo_treatment,
            )
            previous_photo_treatment = treatment

        elif media_type == "VIDEO":
            if existing_treatment == "VIDEO_THEN_FREEZE":
                treatment = "VIDEO_THEN_FREEZE"
            else:
                treatment = "NORMAL"

            previous_photo_treatment = None

        else:
            treatment = existing_treatment or "NONE"
            previous_photo_treatment = None

        clip["director_treatment"] = treatment

        # V1 render parameters only.
        # These describe intent; FFmpeg implementation comes later.
        if treatment == "SLOW_PUSH_IN":
            clip["motion"] = {
                "type": "ZOOM",
                "start_scale": 1.00,
                "end_scale": 1.08,
            }

        elif treatment == "SLOW_PULL_OUT":
            clip["motion"] = {
                "type": "ZOOM",
                "start_scale": 1.08,
                "end_scale": 1.00,
            }

        elif treatment == "PAN_LEFT_TO_RIGHT":
            clip["motion"] = {
                "type": "PAN",
                "direction": "LEFT_TO_RIGHT",
                "scale": 1.08,
            }

        elif treatment == "PAN_RIGHT_TO_LEFT":
            clip["motion"] = {
                "type": "PAN",
                "direction": "RIGHT_TO_LEFT",
                "scale": 1.08,
            }

        else:
            clip["motion"] = {
                "type": "NONE",
            }

        # Hard invariant: Director must never alter timing.
        assert clip.get("speech_start") == original_speech_start
        assert clip.get("speech_end") == original_speech_end
        assert clip.get("visual_start") == original_visual_start
        assert clip.get("visual_end") == original_visual_end

        directed.append(clip)

    return {
        "status": media_timeline.get("status"),
        "manifest": directed,
        "clip_count": len(directed),
        "issues": list(media_timeline.get("issues") or []),
        "silence_regions": list(
            media_timeline.get("silence_regions") or []
        ),
        "timeline_start": media_timeline.get("timeline_start"),
        "timeline_end": media_timeline.get("timeline_end"),
        "timeline_duration": media_timeline.get("timeline_duration"),
    }
