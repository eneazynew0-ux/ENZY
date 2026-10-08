def select_best_coarse_segment(
    judged_frames,
    video_duration,
    sample_interval=2.0,
    match_threshold=60,
    bridge_single_reject=True,
):
    if not judged_frames:
        return None

    frames = sorted(
        judged_frames,
        key=lambda x: float(x["timestamp"]),
    )

    relevant = [
        (
            item.get("decision") == "MATCH"
            and int(item.get("score", 0)) >= match_threshold
        )
        for item in frames
    ]

    # Bridge one isolated bad sample when strong relevant samples
    # exist immediately before and after it.
    if bridge_single_reject and len(relevant) >= 3:
        bridged = relevant[:]

        for i in range(1, len(relevant) - 1):
            if (
                not relevant[i]
                and relevant[i - 1]
                and relevant[i + 1]
            ):
                bridged[i] = True

        relevant = bridged

    runs = []
    start = None

    for i, is_relevant in enumerate(relevant):
        if is_relevant and start is None:
            start = i

        is_last = i == len(relevant) - 1

        if start is not None and (
            (not is_relevant) or is_last
        ):
            end = i if is_relevant and is_last else i - 1

            run_frames = frames[start:end + 1]

            scores = [
                int(x.get("score", 0))
                for x in run_frames
                if x.get("decision") == "MATCH"
            ]

            avg_score = (
                sum(scores) / len(scores)
                if scores
                else 0.0
            )

            first_t = float(run_frames[0]["timestamp"])
            last_t = float(run_frames[-1]["timestamp"])

            segment_start = max(
                0.0,
                first_t - sample_interval / 2.0,
            )

            segment_end = min(
                float(video_duration),
                last_t + sample_interval / 2.0,
            )

            runs.append({
                "start": round(segment_start, 3),
                "end": round(segment_end, 3),
                "duration": round(
                    segment_end - segment_start,
                    3,
                ),
                "average_score": round(avg_score, 2),
                "sample_count": len(run_frames),
                "start_sample_index": start,
                "end_sample_index": end,
            })

            start = None

    if not runs:
        return None

    runs.sort(
        key=lambda x: (
            x["duration"],
            x["average_score"],
            x["sample_count"],
        ),
        reverse=True,
    )

    return runs[0]


if __name__ == "__main__":
    test_frames = [
        {"timestamp": 0.5, "decision": "MATCH", "score": 85},
        {"timestamp": 2.5, "decision": "MATCH", "score": 95},
        {"timestamp": 4.5, "decision": "MATCH", "score": 85},
        {"timestamp": 6.5, "decision": "REJECT", "score": 0},
        {"timestamp": 8.5, "decision": "MATCH", "score": 95},
        {"timestamp": 10.5, "decision": "MATCH", "score": 95},
        {"timestamp": 12.5, "decision": "MATCH", "score": 95},
        {"timestamp": 14.5, "decision": "MATCH", "score": 95},
    ]

    result = select_best_coarse_segment(
        test_frames,
        video_duration=15.766667,
        sample_interval=2.0,
    )

    print("BEST COARSE SEGMENT:", result)

    if result is None:
        raise SystemExit("SEGMENT SELECTOR FAILED")

    if result["start"] != 0.0:
        raise SystemExit(
            f'UNEXPECTED START: {result["start"]}'
        )

    if result["end"] < 15.0:
        raise SystemExit(
            f'UNEXPECTED END: {result["end"]}'
        )

    print("COARSE SEGMENT SELECTOR PASSED")
