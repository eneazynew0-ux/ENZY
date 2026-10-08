def build_boundary_refinement_points(
    coarse_segment,
    video_duration,
    window=2.0,
    interval=0.5,
):
    if not coarse_segment:
        return []

    video_duration = float(video_duration)
    start = float(coarse_segment["start"])
    end = float(coarse_segment["end"])

    if video_duration <= 0:
        raise ValueError("video_duration must be positive")

    if window <= 0 or interval <= 0:
        raise ValueError("window and interval must be positive")

    ranges = [
        (
            max(0.0, start - window),
            min(video_duration, start + window),
        ),
        (
            max(0.0, end - window),
            min(video_duration, end + window),
        ),
    ]

    points = set()

    for range_start, range_end in ranges:
        t = range_start

        while t <= range_end + 1e-9:
            if 0.0 <= t < video_duration:
                points.add(round(t, 3))
            t += interval

    return sorted(points)


if __name__ == "__main__":
    coarse = {
        "start": 0.0,
        "end": 15.5,
    }

    points = build_boundary_refinement_points(
        coarse,
        video_duration=15.766667,
        window=2.0,
        interval=0.5,
    )

    print("DENSE POINT COUNT:", len(points))
    print("DENSE POINTS:", points)

    if not points:
        raise SystemExit("DENSE REFINEMENT FAILED")

    if points[0] != 0.0:
        raise SystemExit(
            f"UNEXPECTED FIRST POINT: {points[0]}"
        )

    if points[-1] >= 15.766667:
        raise SystemExit(
            f"POINT OUTSIDE VIDEO: {points[-1]}"
        )

    print("BOUNDARY REFINEMENT POINTS PASSED")


def refine_segment_boundaries(
    video_path,
    coarse_segment,
    video_duration,
    target,
    window=2.0,
    interval=0.5,
    match_threshold=60,
    output_dir="data/video_dense_frames",
):
    from engine.video_segment_analyzer import extract_sample_frames
    from engine.video_visual_analyzer import describe_video_frames
    from engine.video_segment_judge import judge_video_frames

    points = build_boundary_refinement_points(
        coarse_segment,
        video_duration,
        window=window,
        interval=interval,
    )

    frames = extract_sample_frames(
        video_path,
        points,
        output_dir=output_dir,
    )

    analyzed = describe_video_frames(frames)
    judged = judge_video_frames(analyzed, target)

    relevant = [
        item for item in judged
        if item.get("decision") == "MATCH"
        and int(item.get("score", 0)) >= match_threshold
    ]

    if not relevant:
        return {
            "start": float(coarse_segment["start"]),
            "end": float(coarse_segment["end"]),
            "duration": round(
                float(coarse_segment["end"]) -
                float(coarse_segment["start"]),
                3,
            ),
            "refinement_status": "NO_DENSE_MATCHES",
            "dense_points": judged,
        }

    start_limit = float(coarse_segment["start"]) + window
    end_limit = float(coarse_segment["end"]) - window

    start_region = [
        x for x in relevant
        if float(x["timestamp"]) <= start_limit
    ]

    end_region = [
        x for x in relevant
        if float(x["timestamp"]) >= end_limit
    ]

    refined_start = float(coarse_segment["start"])
    refined_end = float(coarse_segment["end"])

    if start_region:
        refined_start = max(
            0.0,
            min(float(x["timestamp"]) for x in start_region)
            - interval / 2.0,
        )

    if end_region:
        refined_end = min(
            float(video_duration),
            max(float(x["timestamp"]) for x in end_region)
            + interval / 2.0,
        )

    if refined_end <= refined_start:
        refined_start = float(coarse_segment["start"])
        refined_end = float(coarse_segment["end"])
        status = "FALLBACK_COARSE"
    else:
        status = "REFINED"

    return {
        "start": round(refined_start, 3),
        "end": round(refined_end, 3),
        "duration": round(refined_end - refined_start, 3),
        "refinement_status": status,
        "dense_points": judged,
    }
