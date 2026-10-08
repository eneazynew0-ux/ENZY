from pathlib import Path

from engine.video_downloader import download_video
from engine.video_segment_analyzer import (
    probe_video,
    build_sample_points,
    extract_sample_frames,
)
from engine.video_visual_analyzer import describe_video_frames
from engine.video_segment_judge import judge_video_frames
from engine.video_segment_selector import select_best_coarse_segment
from engine.video_segment_refiner import refine_segment_boundaries


def analyze_video_candidate(
    asset,
    target,
    output_dir="data/video_candidate_analysis",
    sample_interval=2.0,
    match_threshold=60,
):
    output_dir = Path(output_dir)
    video_dir = output_dir / "videos"
    coarse_frames_dir = output_dir / "coarse_frames"
    dense_frames_dir = output_dir / "dense_frames"

    downloaded = download_video(
        asset,
        output_dir=str(video_dir),
    )

    video_path = downloaded["local_path"]
    probe = probe_video(video_path)
    duration = float(probe["duration"])

    points = build_sample_points(
        duration,
        interval=sample_interval,
    )

    frames = extract_sample_frames(
        video_path,
        points,
        output_dir=str(coarse_frames_dir),
    )

    analyzed = describe_video_frames(frames)
    judged = judge_video_frames(
        analyzed,
        target,
    )

    coarse = select_best_coarse_segment(
        judged,
        duration,
        sample_interval=sample_interval,
        match_threshold=match_threshold,
        bridge_single_reject=True,
    )

    if coarse is None:
        return {
            "status": "NO_RELEVANT_SEGMENT",
            "asset": downloaded,
            "probe": probe,
            "sample_points": points,
            "coarse_frames": judged,
            "coarse_segment": None,
            "best_segment": None,
        }

    refined = refine_segment_boundaries(
        video_path,
        coarse,
        duration,
        target,
        interval=0.5,
        match_threshold=match_threshold,
        output_dir=str(dense_frames_dir),
    )

    return {
        "status": "MATCH",
        "asset": downloaded,
        "probe": probe,
        "sample_points": points,
        "coarse_frames": judged,
        "coarse_segment": coarse,
        "best_segment": refined,
    }
