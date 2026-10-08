from engine.visual_relevance import describe_image


def describe_video_frames(frames, max_tokens=50):
    results = []

    for frame in frames:
        timestamp = float(frame["timestamp"])
        path = frame["path"]

        try:
            description = describe_image(
                path,
                max_tokens=max_tokens,
            )

            results.append({
                **frame,
                "description": description,
                "analysis_status": "OK",
            })

        except Exception as exc:
            results.append({
                **frame,
                "description": "",
                "analysis_status": "FAILED",
                "analysis_error": str(exc),
            })

    return results


if __name__ == "__main__":
    from engine.video_segment_analyzer import (
        probe_video,
        build_sample_points,
        extract_sample_frames,
    )

    video = "data/pixabay_video_test/7bb929241b5563f0.mp4"

    info = probe_video(video)
    points = build_sample_points(info["duration"])

    frames = extract_sample_frames(
        video,
        points,
        output_dir="data/video_analysis_frames",
    )

    analyzed = describe_video_frames(frames)

    print("ANALYZED:", len(analyzed))

    for item in analyzed:
        print()
        print(f'TIME: {item["timestamp"]:.3f}s')
        print("STATUS:", item["analysis_status"])
        print("DESCRIPTION:", item["description"])
