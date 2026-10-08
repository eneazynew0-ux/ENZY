from engine.visual_judge import judge_visual, _description_is_valid


def judge_video_frames(analyzed_frames, target):
    results = []

    for frame in analyzed_frames:
        description = frame.get("description", "")

        if frame.get("analysis_status") != "OK":
            results.append({
                **frame,
                "target": target,
                "decision": "REJECT",
                "score": 0,
                "reason": "Vision analysis failed",
            })
            continue

        if not _description_is_valid(description):
            results.append({
                **frame,
                "target": target,
                "decision": "REJECT",
                "score": 0,
                "reason": "Invalid or instruction-echoing vision description",
            })
            continue

        judgment = judge_visual(target, description)

        results.append({
            **frame,
            "target": target,
            "decision": judgment["decision"],
            "score": judgment["score"],
            "reason": judgment["reason"],
        })

    return results


if __name__ == "__main__":
    from engine.video_segment_analyzer import (
        probe_video,
        build_sample_points,
        extract_sample_frames,
    )
    from engine.video_visual_analyzer import describe_video_frames

    video = "data/pixabay_video_test/7bb929241b5563f0.mp4"

    target = (
        "A real wide mountain landscape at sunset or dusk, "
        "with distant mountain ridges and warm evening sky"
    )

    info = probe_video(video)
    points = build_sample_points(info["duration"])

    frames = extract_sample_frames(
        video,
        points,
        output_dir="data/video_analysis_frames",
    )

    analyzed = describe_video_frames(frames)
    judged = judge_video_frames(analyzed, target)

    print("TARGET:", target)
    print("JUDGED:", len(judged))

    for item in judged:
        print(
            f'{item["timestamp"]:>6.3f}s',
            "|",
            item["decision"],
            "| SCORE",
            item["score"],
            "|",
            item["reason"],
        )
