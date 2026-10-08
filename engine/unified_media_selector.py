def _clamp_score(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(100.0, value))


def _photo_candidate(photo_result):
    if not isinstance(photo_result, dict):
        return None

    if photo_result.get("status") != "SEARCHED":
        return None

    search = photo_result.get("search") or {}
    best = search.get("best")

    if not isinstance(best, dict):
        return None

    asset = best.get("asset")

    if not isinstance(asset, dict):
        return None

    score = _clamp_score(best.get("score"))

    return {
        "media_type": "PHOTO",
        "score": score,
        "asset": asset,
        "visual_result": best,
        "source_result": photo_result,
    }


def _video_candidate(video_result):
    if not isinstance(video_result, dict):
        return None

    if video_result.get("status") != "MATCH":
        return None

    best = video_result.get("best")

    if not isinstance(best, dict):
        return None

    segment = best.get("segment") or {}
    coarse = best.get("coarse_segment") or {}

    if float(segment.get("duration") or 0) <= 0:
        return None

    score = _clamp_score(coarse.get("average_score"))

    return {
        "media_type": "VIDEO",
        "score": score,
        "asset": best.get("asset"),
        "segment": segment,
        "probe": best.get("probe"),
        "source_result": video_result,
    }


def select_media_for_beat(
    photo_result,
    video_result,
    factual_search=False,
    preference_margin=10.0,
):
    """
    Choose one usable media result for a visual beat.

    V1 policy:
    - Never invent a candidate when neither branch found one.
    - If only one branch succeeded, use it.
    - For factual beats, PHOTO gets a small preference because exact
      historical places/artifacts are often better represented by a
      verified still image.
    - For non-factual B-roll, VIDEO gets a small preference because
      natural motion is usually more useful for documentary editing.
    - A relevance advantage larger than the preference margin wins.
    - This is not the global 70/30 director policy. That belongs to
      sequence-level planning later.
    """
    photo = _photo_candidate(photo_result)
    video = _video_candidate(video_result)

    if photo is None and video is None:
        return {
            "status": "NO_MEDIA",
            "selected_type": None,
            "selected": None,
            "photo": None,
            "video": None,
            "reason": "Neither media branch produced a usable candidate.",
        }

    if photo is not None and video is None:
        return {
            "status": "SELECTED",
            "selected_type": "PHOTO",
            "selected": photo,
            "photo": photo,
            "video": None,
            "reason": "Only the photo branch produced usable media.",
        }

    if video is not None and photo is None:
        return {
            "status": "SELECTED",
            "selected_type": "VIDEO",
            "selected": video,
            "photo": None,
            "video": video,
            "reason": "Only the video branch produced usable media.",
        }

    photo_score = photo["score"]
    video_score = video["score"]

    if factual_search:
        if video_score >= photo_score + preference_margin:
            selected = video
            reason = (
                "Video relevance exceeded the factual-photo preference "
                "by the required margin."
            )
        else:
            selected = photo
            reason = (
                "Factual beat preferred the verified photo because video "
                "did not exceed it by the required relevance margin."
            )
    else:
        if photo_score >= video_score + preference_margin:
            selected = photo
            reason = (
                "Photo relevance exceeded the B-roll video preference "
                "by the required margin."
            )
        else:
            selected = video
            reason = (
                "Non-factual beat preferred video because photo did not "
                "exceed it by the required relevance margin."
            )

    return {
        "status": "SELECTED",
        "selected_type": selected["media_type"],
        "selected": selected,
        "photo": photo,
        "video": video,
        "reason": reason,
    }
