"""
ENZYVIDEO Live Asset Executor V1

Router request -> existing orchestrator -> normalized selected media
-> safe downstream local reuse.

MASTER timing is immutable.
Actual selected media type is authoritative.
"""

from engine.asset_execution_adapter import (
    normalize_selected_media,
    adapt_followup_phase,
)

SEARCH_UNIFIED = "SEARCH_UNIFIED"
SEARCH_VIDEO = "SEARCH_VIDEO"
SEARCH_PHOTO = "SEARCH_PHOTO"
SEARCH_ARCHIVE = "SEARCH_ARCHIVE"


def _extract_request(phase):
    return (phase or {}).get("execution_request") or {}


def _no_selection():
    return {
        "status": "NO_SELECTION",
        "media_type": None,
        "asset": None,
        "segment": None,
    }


def _normalize_video_result(result):
    if not isinstance(result, dict):
        return _no_selection()

    best = result.get("best")

    if result.get("status") != "MATCH" or not isinstance(best, dict):
        return _no_selection()

    asset = best.get("asset")
    segment = best.get("segment")

    if not asset:
        return _no_selection()

    return {
        "status": "SELECTED",
        "media_type": "VIDEO",
        "asset": asset,
        "segment": segment,
    }


def _normalize_visual_result(result):
    if not isinstance(result, dict):
        return _no_selection()

    search = result.get("search") or {}
    best = search.get("best")

    if isinstance(best, dict) and isinstance(best.get("asset"), dict):
        asset = best["asset"]
    elif isinstance(best, dict):
        asset = best
    else:
        asset = None

    if not asset:
        return _no_selection()

    return {
        "status": "SELECTED",
        "media_type": "PHOTO",
        "asset": asset,
        "segment": None,
    }


def execute_external_phase(
    beat,
    phase,
    scene_entities,
    target,
    *,
    model=None,
    tokenizer=None,
    verified_years=None,
    output_dir="data/live_asset_executor",
    unified_runner=None,
    video_runner=None,
    visual_runner=None,
):
    request = _extract_request(phase)
    action = request.get("resolver_action")

    if action == SEARCH_UNIFIED:
        if unified_runner is None:
            from engine.unified_media_orchestrator import run_unified_media_search
            unified_runner = run_unified_media_search

        raw = unified_runner(
            beat,
            scene_entities,
            target,
            model=model,
            tokenizer=tokenizer,
            verified_years=verified_years,
            output_dir=f"{output_dir}/unified",
        )
        selected = normalize_selected_media(raw)

    elif action == SEARCH_VIDEO:
        if video_runner is None:
            from engine.beat_video_orchestrator import run_beat_video_search
            video_runner = run_beat_video_search

        raw = video_runner(
            beat,
            scene_entities,
            target,
            model=model,
            tokenizer=tokenizer,
            verified_years=verified_years,
            output_dir=f"{output_dir}/video",
        )
        selected = _normalize_video_result(raw)

    elif action in {SEARCH_PHOTO, SEARCH_ARCHIVE}:
        if visual_runner is None:
            from engine.beat_search_orchestrator import run_beat_visual_search
            visual_runner = run_beat_visual_search

        branch = "archive" if action == SEARCH_ARCHIVE else "photo"

        raw = visual_runner(
            beat,
            scene_entities,
            target,
            model=model,
            tokenizer=tokenizer,
            verified_years=verified_years,
            output_dir=f"{output_dir}/{branch}",
        )
        selected = _normalize_visual_result(raw)

    else:
        raise ValueError(
            f"Unsupported external resolver action: {action}"
        )

    return {
        "status": selected["status"],
        "resolver_action": action,
        "selected_media": selected,
        "raw_result": raw,
    }


def execute_phase_group(
    beat,
    phases,
    scene_entities,
    target,
    **kwargs,
):
    if not phases:
        return {
            "status": "NO_PHASES",
            "selected_media": None,
            "phases": [],
        }

    primary = phases[0]
    request = _extract_request(primary)

    if not request.get("execute_external_search"):
        return {
            "status": "LOCAL_ONLY",
            "selected_media": None,
            "phases": phases,
        }

    execution = execute_external_phase(
        beat,
        primary,
        scene_entities,
        target,
        **kwargs,
    )

    if execution["status"] != "SELECTED":
        return {
            "status": "NO_SELECTION",
            "selected_media": execution["selected_media"],
            "phases": phases,
            "execution": execution,
        }

    selected = execution["selected_media"]

    adapted = [primary]

    for phase in phases[1:]:
        req = _extract_request(phase)

        if req.get("execute_external_search"):
            adapted.append(phase)
        else:
            adapted.append(
                adapt_followup_phase(phase, selected)
            )

    return {
        "status": "READY",
        "selected_media": selected,
        "phases": adapted,
        "execution": execution,
    }
