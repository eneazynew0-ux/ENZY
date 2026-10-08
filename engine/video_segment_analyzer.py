import json
import subprocess
from pathlib import Path


def probe_video(video_path):
    video_path = str(video_path)

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate:format=duration,size",
        "-of", "json",
        video_path,
    ]

    data = json.loads(subprocess.check_output(cmd, text=True))

    if not data.get("streams"):
        raise ValueError("Video has no video stream")

    stream = data["streams"][0]
    fmt = data.get("format", {})

    return {
        "path": video_path,
        "duration": float(fmt["duration"]),
        "size_bytes": int(fmt.get("size", 0)),
        "codec": stream.get("codec_name"),
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
    }


def build_sample_points(duration, interval=2.0):
    if duration <= 0:
        raise ValueError("Duration must be positive")

    if interval <= 0:
        raise ValueError("Interval must be positive")

    points = []
    t = 0.5

    while t < duration:
        points.append(round(t, 3))
        t += interval

    if not points:
        points.append(round(duration / 2.0, 3))

    return points


if __name__ == "__main__":
    path = Path("data/pixabay_video_test/7bb929241b5563f0.mp4")

    info = probe_video(path)
    points = build_sample_points(info["duration"])

    print("VIDEO:", info["path"])
    print("DURATION:", info["duration"])
    print("SIZE:", info["width"], "x", info["height"])
    print("CODEC:", info["codec"])
    print("SAMPLE COUNT:", len(points))
    print("SAMPLE POINTS:", points)


def extract_sample_frames(video_path, points, output_dir="data/video_analysis_frames"):
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = []

    for index, timestamp in enumerate(points):
        filename = f"frame_{index:04d}_{timestamp:.3f}s.jpg"
        output_path = output_dir / filename

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-ss", f"{timestamp:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path),
        ]

        subprocess.run(cmd, check=True)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ValueError(f"Failed to extract frame at {timestamp:.3f}s")

        frames.append({
            "timestamp": timestamp,
            "path": str(output_path),
            "size_bytes": output_path.stat().st_size,
        })

    return frames
