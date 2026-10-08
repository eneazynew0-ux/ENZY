"""
ENZYVIDEO Asset Execution Adapter V1

Normalizes actual media-search results for the execution layer.

Critical rule:
The planner expresses the desired media type.
The completed search result is authoritative for what was actually selected.

Therefore, if SEARCH_UNIFIED requested video-first media but factual selection
returns a verified/accepted PHOTO, downstream reuse must adapt to PHOTO instead
of forcing another search or pretending that a video exists.
"""

SEARCH_UNIFIED = "SEARCH_UNIFIED"
SEARCH_VIDEO = "SEARCH_VIDEO"
SEARCH_PHOTO = "SEARCH_PHOTO"
SEARCH_ARCHIVE = "SEARCH_ARCHIVE"

LOCAL_VIDEO_REUSE = "LOCAL_VIDEO_REUSE"
LOCAL_PHOTO_REUSE = "LOCAL_PHOTO_REUSE"
LOCAL_ASSET_REUSE = "LOCAL_ASSET_REUSE"


def normalize_selected_media(search_result):
    """
    Convert an orchestrator result into one stable selected-media contract.
    """

    if not isinstance(search_result, dict):
        return {
            "status": "NO_SELECTION",
            "media_type": None,
            "asset": None,
            "segment": None,
        }

    selected_type = search_result.get("selected_type")
    asset = search_result.get("selected_asset")
    segment = search_result.get("selected_segment")

    if selected_type not in {"PHOTO", "VIDEO"} or not asset:
        return {
            "status": "NO_SELECTION",
            "media_type": None,
            "asset": None,
            "segment": None,
        }

    # A photo must never carry a video segment.
    if selected_type == "PHOTO":
        segment = None

    return {
        "status": "SELECTED",
        "media_type": selected_type,
        "asset": asset,
        "segment": segment,
    }


def local_reuse_backend(selected_media):
    """
    Choose local reuse from the media that actually won selection.
    """

    media_type = (selected_media or {}).get("media_type")

    if media_type == "VIDEO":
        return LOCAL_VIDEO_REUSE

    if media_type == "PHOTO":
        return LOCAL_PHOTO_REUSE

    return LOCAL_ASSET_REUSE


def adapt_followup_phase(phase, selected_media):
    """
    Adapt a downstream reuse phase to the actual selected media.

    Does not modify timing, phase role, source asset, or MASTER coordinates.
    """

    out = dict(phase)
    request = dict(out.get("execution_request") or {})

    backend = local_reuse_backend(selected_media)

    request["execution_backend"] = backend
    request["execute_external_search"] = False
    request["execute_local_reuse"] = True
    request["execution_policy"] = "LOCAL_ONLY"
    request["resolved_media_type"] = (selected_media or {}).get("media_type")

    out["execution_request"] = request
    return out


def execute_saved_unified_result(primary_phase, followup_phases, search_result):
    """
    V1 execution bridge for an already-completed unified search.

    This deliberately does NOT perform network search.
    It proves the handoff:
        completed unified result
        -> normalized selected media
        -> safe local reuse for later retention phases
    """

    selected = normalize_selected_media(search_result)

    if selected["status"] != "SELECTED":
        return {
            "status": "NO_SELECTION",
            "selected_media": selected,
            "primary_phase": primary_phase,
            "followup_phases": followup_phases,
        }

    adapted = [
        adapt_followup_phase(phase, selected)
        for phase in followup_phases
    ]

    return {
        "status": "READY",
        "selected_media": selected,
        "primary_phase": primary_phase,
        "followup_phases": adapted,
    }
