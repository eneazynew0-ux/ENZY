EPSILON = 0.05


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_timeline_clip(beat, media_result):
    """
    Convert one MASTER-synced beat + unified media result into one timeline clip.

    MASTER narration timing is authoritative and is never modified.
    """

    beat_start = _number(beat.get("start"))
    beat_end = _number(beat.get("end"))
    beat_duration = _number(beat.get("duration"))

    if beat_duration <= 0:
        beat_duration = beat_end - beat_start

    if beat_end <= beat_start or beat_duration <= 0:
        return {
            "status": "INVALID_BEAT_TIMING",
            "beat": beat,
        }

    selected_type = media_result.get("selected_type")
    asset = media_result.get("selected_asset")

    if media_result.get("status") != "SELECTED":
        return {
            "status": "NO_MEDIA",
            "timeline_start": beat_start,
            "timeline_end": beat_end,
            "timeline_duration": beat_duration,
            "beat": beat,
        }

    if not isinstance(asset, dict) or not asset.get("local_path"):
        return {
            "status": "INVALID_MEDIA_ASSET",
            "timeline_start": beat_start,
            "timeline_end": beat_end,
            "timeline_duration": beat_duration,
            "beat": beat,
        }

    if selected_type == "PHOTO":
        return {
            "status": "READY",
            "media_type": "PHOTO",
            "timeline_start": beat_start,
            "timeline_end": beat_end,
            "timeline_duration": beat_duration,
            "asset": asset,
            "source_start": None,
            "source_end": None,
            "source_duration": None,
            "treatment": "STILL",
            "beat": beat,
        }

    if selected_type == "VIDEO":
        segment = media_result.get("selected_segment")

        if not isinstance(segment, dict):
            return {
                "status": "VIDEO_SEGMENT_MISSING",
                "timeline_start": beat_start,
                "timeline_end": beat_end,
                "timeline_duration": beat_duration,
                "asset": asset,
                "beat": beat,
            }

        source_start = _number(segment.get("start"))
        source_end = _number(segment.get("end"))
        source_duration = _number(segment.get("duration"))

        if source_duration <= 0:
            source_duration = source_end - source_start

        if source_end <= source_start or source_duration <= 0:
            return {
                "status": "VIDEO_SEGMENT_INVALID",
                "timeline_start": beat_start,
                "timeline_end": beat_end,
                "timeline_duration": beat_duration,
                "asset": asset,
                "segment": segment,
                "beat": beat,
            }

        if source_duration + EPSILON < beat_duration:
            return {
                "status": "VIDEO_TOO_SHORT",
                "timeline_start": beat_start,
                "timeline_end": beat_end,
                "timeline_duration": beat_duration,
                "asset": asset,
                "segment": segment,
                "available_duration": source_duration,
                "required_duration": beat_duration,
                "beat": beat,
            }

        source_end_for_timeline = source_start + beat_duration

        return {
            "status": "READY",
            "media_type": "VIDEO",
            "timeline_start": beat_start,
            "timeline_end": beat_end,
            "timeline_duration": beat_duration,
            "asset": asset,
            "source_start": source_start,
            "source_end": source_end_for_timeline,
            "source_duration": beat_duration,
            "original_segment_duration": source_duration,
            "treatment": "NORMAL_SPEED",
            "beat": beat,
        }

    return {
        "status": "UNSUPPORTED_MEDIA_TYPE",
        "timeline_start": beat_start,
        "timeline_end": beat_end,
        "timeline_duration": beat_duration,
        "selected_type": selected_type,
        "beat": beat,
    }


def build_sequence_timeline(items, tolerance=0.05):
    """
    Build and validate a sequence of MASTER-synced timeline clips.

    items:
        [
            {
                "beat": {...},
                "media_result": {...},
            },
            ...
        ]

    MASTER beat timing remains authoritative.
    """

    clips = []
    issues = []

    previous_end = None

    for index, item in enumerate(items):
        beat = item.get("beat") or {}
        media_result = item.get("media_result") or {}

        clip = build_timeline_clip(beat, media_result)
        clip["sequence_index"] = index
        clips.append(clip)

        start = _number(beat.get("start"))
        end = _number(beat.get("end"))

        if previous_end is not None:
            delta = start - previous_end

            if delta > tolerance:
                issues.append({
                    "type": "GAP",
                    "index": index,
                    "previous_end": previous_end,
                    "current_start": start,
                    "duration": delta,
                })

            elif delta < -tolerance:
                issues.append({
                    "type": "OVERLAP",
                    "index": index,
                    "previous_end": previous_end,
                    "current_start": start,
                    "duration": abs(delta),
                })

        previous_end = end

        if clip.get("status") != "READY":
            issues.append({
                "type": "CLIP_NOT_READY",
                "index": index,
                "status": clip.get("status"),
            })

    ready_count = sum(
        1 for clip in clips
        if clip.get("status") == "READY"
    )

    if clips:
        timeline_start = _number(
            clips[0].get("timeline_start"),
            _number((items[0].get("beat") or {}).get("start")),
        )
        timeline_end = _number(
            (items[-1].get("beat") or {}).get("end")
        )
    else:
        timeline_start = 0.0
        timeline_end = 0.0

    return {
        "status": "READY" if not issues else "NEEDS_ATTENTION",
        "clips": clips,
        "issues": issues,
        "clip_count": len(clips),
        "ready_count": ready_count,
        "timeline_start": timeline_start,
        "timeline_end": timeline_end,
        "timeline_duration": max(0.0, timeline_end - timeline_start),
    }


def build_continuous_visual_timeline(items, tolerance=0.05):
    """
    Build continuous visual coverage over MASTER speech pauses.

    Speech timing remains untouched.
    A visual clip may continue through the silence after its beat until
    the next beat begins.

    No narration timestamps are modified.
    """

    base = build_sequence_timeline(items, tolerance=tolerance)
    clips = [dict(clip) for clip in base["clips"]]

    issues = [
        issue for issue in base["issues"]
        if issue.get("type") != "GAP"
    ]

    silence_regions = []

    for i, clip in enumerate(clips):
        beat = clip.get("beat") or {}

        speech_start = _number(beat.get("start"))
        speech_end = _number(beat.get("end"))

        clip["speech_start"] = speech_start
        clip["speech_end"] = speech_end

        visual_start = speech_start
        visual_end = speech_end

        if i + 1 < len(clips):
            next_beat = clips[i + 1].get("beat") or {}
            next_start = _number(next_beat.get("start"))

            gap = next_start - speech_end

            if gap > tolerance:
                visual_end = next_start

                silence_regions.append({
                    "start": speech_end,
                    "end": next_start,
                    "duration": gap,
                    "covered_by_clip": i,
                    "strategy": "HOLD_PREVIOUS_VISUAL",
                })

        clip["visual_start"] = visual_start
        clip["visual_end"] = visual_end
        clip["visual_duration"] = max(
            0.0,
            visual_end - visual_start,
        )

        if (
            clip.get("status") == "READY"
            and clip.get("media_type") == "VIDEO"
        ):
            source_duration = _number(
                clip.get("original_segment_duration")
            )

            if source_duration + tolerance < clip["visual_duration"]:
                speech_duration = max(
                    0.0,
                    clip["speech_end"] - clip["speech_start"],
                )

                if source_duration + tolerance >= speech_duration:
                    freeze_duration = (
                        clip["visual_duration"] - source_duration
                    )

                    clip["visual_treatment"] = "VIDEO_THEN_FREEZE"
                    clip["video_play_duration"] = source_duration
                    clip["freeze_duration"] = freeze_duration
                    clip["freeze_at_source_time"] = (
                        _number(clip.get("source_start"))
                        + source_duration
                    )
                else:
                    issues.append({
                        "type": "VIDEO_TOO_SHORT_FOR_SPEECH",
                        "index": i,
                        "available_duration": source_duration,
                        "required_duration": speech_duration,
                    })

    return {
        "status": "READY" if not issues else "NEEDS_ATTENTION",
        "clips": clips,
        "issues": issues,
        "silence_regions": silence_regions,
        "clip_count": len(clips),
        "ready_count": sum(
            1 for clip in clips
            if clip.get("status") == "READY"
        ),
        "timeline_start": base["timeline_start"],
        "timeline_end": base["timeline_end"],
        "timeline_duration": base["timeline_duration"],
    }
