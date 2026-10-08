from copy import deepcopy


SEARCH_UNIFIED = "SEARCH_UNIFIED"
SEARCH_VIDEO = "SEARCH_VIDEO"
SEARCH_PHOTO = "SEARCH_PHOTO"
SEARCH_ARCHIVE = "SEARCH_ARCHIVE"

REUSE_SELECTED_VIDEO = "REUSE_SELECTED_VIDEO"
REUSE_SELECTED_PHOTO = "REUSE_SELECTED_PHOTO"
REUSE_DOCUMENT = "REUSE_DOCUMENT"
REUSE_MAP = "REUSE_MAP"
REUSE_SELECTED_ASSET = "REUSE_SELECTED_ASSET"


def resolve_requirement(requirement):
    """
    Convert Shot Asset Planner requirements into actions handled by
    the existing ENZYVIDEO media pipeline.

    This layer performs no search/download itself.
    """

    routes = {
        # Exact factual video: existing unified pipeline decides whether
        # a sufficiently verified video exists, otherwise factual fallback
        # remains possible.
        "VERIFIED_VIDEO_PRIMARY": SEARCH_UNIFIED,
        "VERIFIED_VIDEO_ESTABLISH": SEARCH_UNIFIED,

        # Detail from an already verified factual video must not create
        # another web search.
        "SAME_VERIFIED_VIDEO_DETAIL": REUSE_SELECTED_VIDEO,

        # Exact factual still.
        "EXACT_PHOTO_PRIMARY": SEARCH_PHOTO,
        "EXACT_PHOTO_DETAIL": REUSE_SELECTED_PHOTO,

        # Generic video.
        "VIDEO_PRIMARY": SEARCH_VIDEO,
        "VIDEO_ESTABLISH": SEARCH_VIDEO,

        # Try existing video first; second-video search is only a fallback
        # decision for a later execution layer.
        "SAME_VIDEO_DETAIL_OR_SECOND_VIDEO": REUSE_SELECTED_VIDEO,

        # Archive.
        "ARCHIVE_PRIMARY": SEARCH_ARCHIVE,
        "SECOND_ARCHIVE_ASSET": SEARCH_ARCHIVE,

        # Document.
        "DOCUMENT_PRIMARY": SEARCH_PHOTO,
        "DOCUMENT_EVIDENCE": SEARCH_PHOTO,
        "DOCUMENT_DETAIL": REUSE_DOCUMENT,

        # Map.
        "MAP_OVERVIEW": REUSE_MAP,
        "MAP_FOCUS": REUSE_MAP,

        # Conservative fallback.
        "SAME_ASSET": REUSE_SELECTED_ASSET,
    }

    return routes.get(requirement, REUSE_SELECTED_ASSET)


def route_phase(phase):
    result = deepcopy(phase)

    requirement = phase.get("asset_requirement")
    action = resolve_requirement(requirement)

    result["resolver_action"] = action

    result["requires_external_search"] = action in {
        SEARCH_UNIFIED,
        SEARCH_VIDEO,
        SEARCH_PHOTO,
        SEARCH_ARCHIVE,
    }

    result["reuse_existing_media"] = action in {
        REUSE_SELECTED_VIDEO,
        REUSE_SELECTED_PHOTO,
        REUSE_DOCUMENT,
        REUSE_MAP,
        REUSE_SELECTED_ASSET,
    }

    return result


def attach_resolver_plan(beat):
    result = deepcopy(beat)

    result["retention_phases"] = [
        route_phase(phase)
        for phase in beat.get("retention_phases", [])
    ]

    return result


def resolve_sequence(beats):
    return [
        attach_resolver_plan(beat)
        for beat in beats
    ]
