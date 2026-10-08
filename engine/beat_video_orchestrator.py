import math
from engine.beat_search_orchestrator import build_beat_search_plan
from engine.multi_query_video_search import search_video_candidates
from engine.video_candidate_pipeline import analyze_video_candidate
from engine.video_metadata_judge import judge_video_metadata
from engine.search_contract import visual_search_target


def _metadata_score(asset):
    width = int(asset.get("width") or 0)
    height = int(asset.get("height") or 0)
    duration = float(asset.get("duration") or 0)

    score = 0

    # Prefer landscape footage suitable for 16:9 documentary editing.
    if width >= height:
        score += 100

    if width >= 1920:
        score += 30
    elif width >= 1280:
        score += 20

    # Prefer clips with enough temporal room for an editing beat.
    if 8 <= duration <= 60:
        score += 20
    elif duration > 0:
        score += 10

    return score


def run_beat_video_search(
    beat,
    scene_entities,
    target,
    model=None,
    tokenizer=None,
    verified_years=None,
    limit_per_query=5,
    max_downloads=6,
    sample_interval=2.0,
    match_threshold=60,
    strong_segment_score=85,
    output_dir="data/beat_video_search",
):
    target = visual_search_target(beat, target)
    required_duration = float(beat.get("duration") or
                              (float(beat.get("end") or 0)-float(beat.get("start") or 0)))
    if not math.isfinite(required_duration) or required_duration <= 0:
        raise ValueError("VALID_BEAT_DURATION_REQUIRED")
    plan = build_beat_search_plan(
        beat,
        scene_entities,
        model=model,
        tokenizer=tokenizer,
        verified_years=verified_years,
    )

    query_plan = plan.get("queries") or {}

    if isinstance(query_plan, dict):
        queries = list(query_plan.get("all") or [])
    elif isinstance(query_plan, list):
        queries = list(query_plan)
    else:
        queries = []

    factual_search = bool(plan.get("factual_search"))
    search_entity = plan.get("search_entity")

    if not queries:
        return {
            "status": "NO_QUERIES",
            "plan": plan,
            "video_search": None,
            "attempts": [],
            "best": None,
        }

    if factual_search and not search_entity:
        return {
            "status": "FACTUAL_IDENTITY_UNAVAILABLE",
            "plan": plan,
            "video_search": None,
            "attempts": [],
            "best": None,
        }

    video_search = search_video_candidates(
        queries,
        limit_per_query=limit_per_query,
        factual=factual_search,
        visual_entity=search_entity if factual_search else None,
    )

    candidates = list(video_search.get("assets") or [])
    metadata_rejected = []

    # Reject metadata-incompatible videos before downloading MP4 files.
    if model is not None and tokenizer is not None:
        metadata_allowed = []

        for asset in candidates:
            decision = judge_video_metadata(
                asset,
                target,
                model,
                tokenizer,
            )

            item = dict(asset)
            item["metadata_relevance"] = decision

            if decision.get("decision") == "MATCH":
                metadata_allowed.append(item)
            else:
                metadata_rejected.append(item)

        candidates = metadata_allowed

    candidates.sort(
        key=lambda asset: (
            int(
                (asset.get("metadata_relevance") or {}).get(
                    "score",
                    0,
                )
            ),
            _metadata_score(asset),
        ),
        reverse=True,
    )

    candidates = candidates[:max_downloads]

    if not candidates:
        return {
            "status": "NO_VIDEO_CANDIDATES",
            "plan": plan,
            "video_search": video_search,
            "attempts": [],
            "metadata_rejected": metadata_rejected,
            "best": None,
        }

    attempts = []
    best = None

    for index, asset in enumerate(candidates):
        result = analyze_video_candidate(
            asset,
            target,
            output_dir=f"{output_dir}/candidate_{index + 1}",
            sample_interval=sample_interval,
            match_threshold=match_threshold,
        )

        attempts.append(result)

        if result.get("status") != "MATCH":
            continue

        segment = result.get("best_segment") or {}
        coarse = result.get("coarse_segment") or {}

        # Reject isolated frame-level hallucinations.
        # A usable video segment must have real temporal support.
        try:
            values = (float(segment.get("duration") or 0),
                      float(segment.get("end") or 0)-float(segment.get("start") or 0))
            segment_duration = min(values) if all(math.isfinite(v) for v in values) else 0
        except (ValueError, TypeError):
            segment_duration = 0
        if segment_duration < max(1.0, required_duration):
            result["selection_rejection"] = {
                "reason": "INSUFFICIENT_SEGMENT_DURATION", "required": max(1.0, required_duration),
                "available": segment_duration,
            }
            continue

        candidate_result = {
            "asset": result.get("asset"),
            "probe": result.get("probe"),
            "segment": segment,
            "coarse_segment": coarse,
        }

        if best is None:
            best = candidate_result
        else:
            current_score = float(
                coarse.get("average_score") or 0
            )
            best_score = float(
                best.get("coarse_segment", {}).get("average_score") or 0
            )

            current_duration = float(
                segment.get("duration") or 0
            )
            best_duration = float(
                best.get("segment", {}).get("duration") or 0
            )

            if (
                current_score > best_score
                or (
                    current_score == best_score
                    and current_duration > best_duration
                )
            ):
                best = candidate_result


    if best is None:
        return {
            "status": "NO_RELEVANT_VIDEO_SEGMENT",
            "plan": plan,
            "video_search": video_search,
            "attempts": attempts,
            "metadata_rejected": metadata_rejected,
            "best": None,
        }

    return {
        "status": "MATCH",
        "plan": plan,
        "video_search": video_search,
        "attempts": attempts,
        "metadata_rejected": metadata_rejected,
        "best": best,
    }
