from copy import deepcopy


DEFAULT_VIDEO_TARGET_MIN = 0.70
DEFAULT_VIDEO_TARGET_MAX = 0.80


def media_duration_stats(clips):
    video_seconds = 0.0
    photo_seconds = 0.0
    other_seconds = 0.0

    for clip in clips:
        duration = float(
            clip.get(
                "visual_duration",
                clip.get("duration", 0.0),
            ) or 0.0
        )

        media_type = str(
            clip.get("media_type", "")
        ).upper()

        if media_type == "VIDEO":
            video_seconds += duration
        elif media_type == "PHOTO":
            photo_seconds += duration
        else:
            other_seconds += duration

    total = video_seconds + photo_seconds + other_seconds

    return {
        "total_seconds": total,
        "video_seconds": video_seconds,
        "photo_seconds": photo_seconds,
        "other_seconds": other_seconds,
        "video_ratio": (
            video_seconds / total if total > 0 else 0.0
        ),
    }


def video_mix_status(
    clips,
    target_min=DEFAULT_VIDEO_TARGET_MIN,
    target_max=DEFAULT_VIDEO_TARGET_MAX,
):
    stats = media_duration_stats(clips)
    ratio = stats["video_ratio"]

    if ratio < target_min:
        status = "NEEDS_MORE_VIDEO"
    elif ratio > target_max:
        status = "VIDEO_HEAVY"
    else:
        status = "TARGET_RANGE"

    return {
        **stats,
        "target_min": target_min,
        "target_max": target_max,
        "status": status,
    }


def can_prefer_video(beat, clip):
    """
    Decide whether this beat may be targeted for a better real-video
    alternative.

    This does NOT replace media. It only marks safe opportunities for
    the search/selection layer.

    Exact factual identity must never be sacrificed merely to satisfy
    the global video-duration target.
    """
    if str(clip.get("media_type", "")).upper() == "VIDEO":
        return False

    factual = bool(
        beat.get(
            "factual_priority",
            clip.get("factual_priority", False),
        )
    )

    identity_status = str(
        clip.get("identity_status", "")
    ).upper()

    if factual and identity_status in {
        "VERIFIED",
        "EXACT",
        "IDENTITY_CRITICAL",
    }:
        return False

    return True


def mark_video_opportunities(
    beat_clip_pairs,
    target_min=DEFAULT_VIDEO_TARGET_MIN,
    target_max=DEFAULT_VIDEO_TARGET_MAX,
):
    """
    Analyze the sequence by DURATION, never by asset count.

    When the project is below the desired moving-video range, eligible
    PHOTO clips are marked as opportunities for a future real-video
    alternative.

    No media, timing, source asset, or MASTER data is modified.
    """
    pairs = deepcopy(beat_clip_pairs)
    clips = [clip for _, clip in pairs]

    mix = video_mix_status(
        clips,
        target_min=target_min,
        target_max=target_max,
    )

    need_more_video = mix["status"] == "NEEDS_MORE_VIDEO"

    output = []

    for beat, clip in pairs:
        marked = deepcopy(clip)

        eligible = (
            need_more_video
            and can_prefer_video(beat, clip)
        )

        marked["video_preference"] = (
            "SEARCH_VIDEO_ALTERNATIVE"
            if eligible
            else "KEEP_CURRENT_MEDIA"
        )

        output.append((beat, marked))

    return {
        "mix": mix,
        "items": output,
    }
