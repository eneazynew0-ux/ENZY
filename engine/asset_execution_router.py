from copy import deepcopy


SEARCH_ACTIONS = {
    "SEARCH_UNIFIED",
    "SEARCH_VIDEO",
    "SEARCH_PHOTO",
    "SEARCH_ARCHIVE",
}

REUSE_ACTIONS = {
    "REUSE_SELECTED_VIDEO",
    "REUSE_SELECTED_PHOTO",
    "REUSE_DOCUMENT",
    "REUSE_MAP",
    "REUSE_SELECTED_ASSET",
}


def execution_backend(action):
    """
    Map resolver actions to existing ENZYVIDEO execution backends.

    This module does not perform network execution yet.
    It defines the dispatch contract only.
    """

    routes = {
        "SEARCH_UNIFIED": "UNIFIED_MEDIA_ORCHESTRATOR",
        "SEARCH_VIDEO": "BEAT_VIDEO_ORCHESTRATOR",
        "SEARCH_PHOTO": "BEAT_VISUAL_SEARCH_ORCHESTRATOR",

        # No duplicate archive search engine.
        # Archive requirements reuse the existing visual search stack;
        # archive/source preference will be supplied as execution policy.
        "SEARCH_ARCHIVE": "BEAT_VISUAL_SEARCH_ORCHESTRATOR",

        "REUSE_SELECTED_VIDEO": "LOCAL_VIDEO_REUSE",
        "REUSE_SELECTED_PHOTO": "LOCAL_PHOTO_REUSE",
        "REUSE_DOCUMENT": "LOCAL_DOCUMENT_REUSE",
        "REUSE_MAP": "LOCAL_MAP_COMPOSITION",
        "REUSE_SELECTED_ASSET": "LOCAL_ASSET_REUSE",
    }

    return routes.get(action, "LOCAL_ASSET_REUSE")


def build_execution_request(beat, phase):
    result = {
        "beat_start": beat.get("start"),
        "beat_end": beat.get("end"),
        "beat_duration": beat.get("duration"),
        "documentary_mode": beat.get("documentary_mode"),
        "identity_sensitive": bool(
            beat.get("identity_sensitive", False)
        ),
        "requires_identity_gate": bool(
            beat.get("requires_identity_gate", False)
        ),

        "phase_index": phase.get("phase_index"),
        "phase_role": phase.get("role"),
        "phase_start": phase.get("start"),
        "phase_end": phase.get("end"),
        "phase_duration": phase.get("duration"),

        "asset_requirement": phase.get("asset_requirement"),
        "resolver_action": phase.get("resolver_action"),
        "requires_identity_verification": bool(
            phase.get("requires_identity_verification", False)
        ),
    }

    action = result["resolver_action"]

    result["execution_backend"] = execution_backend(action)
    result["execute_external_search"] = action in SEARCH_ACTIONS
    result["execute_local_reuse"] = action in REUSE_ACTIONS

    if action == "SEARCH_ARCHIVE":
        result["execution_policy"] = "PREFER_ARCHIVE_SOURCES"
    elif action == "SEARCH_UNIFIED":
        result["execution_policy"] = "FACTUAL_SAFE_UNIFIED"
    elif action == "SEARCH_VIDEO":
        result["execution_policy"] = "VIDEO_PRIMARY"
    elif action == "SEARCH_PHOTO":
        result["execution_policy"] = "PHOTO_PRIMARY"
    else:
        result["execution_policy"] = "LOCAL_ONLY"

    return result


def attach_execution_requests(beat):
    result = deepcopy(beat)

    result["retention_phases"] = [
        {
            **deepcopy(phase),
            "execution_request": build_execution_request(
                beat,
                phase,
            ),
        }
        for phase in beat.get("retention_phases", [])
    ]

    return result


def build_execution_sequence(beats):
    return [
        attach_execution_requests(beat)
        for beat in beats
    ]
