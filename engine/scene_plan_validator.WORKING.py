import json
import re
from pathlib import Path


def scene_duration(scene):
    return float(scene.get("duration", 0.0))


def count_visual_transitions(text):
    text = str(text or "").lower()

    markers = [
        " затем ",
        " потом ",
        " сначала ",
        " прежде чем ",
        " после ",
        " а потом ",
        " and then ",
        " then ",
        " before ",
        " after ",
        " followed by ",
    ]

    return sum(text.count(marker) for marker in markers)


def suspicious_query_details(query, voice_text, story_map_text):
    query = str(query or "")
    evidence = (str(voice_text or "") + " " + str(story_map_text or "")).lower()

    problems = []

    years = re.findall(r"\b(?:18|19|20)\d{2}\b", query)
    for year in years:
        if year.lower() not in evidence:
            problems.append(f"unsupported year: {year}")

    return problems


def validate_scene(scene, story_map):
    issues = []

    duration = scene_duration(scene)
    voice = str(scene.get("voice_text", ""))
    visual = str(scene.get("visual_intent", ""))

    if duration > 14.0:
        issues.append({
            "type": "LONG_SCENE",
            "severity": "HIGH",
            "detail": f"Scene lasts {duration:.2f}s and should be reviewed for semantic splitting."
        })
    elif duration > 11.0:
        issues.append({
            "type": "LONG_SCENE",
            "severity": "MEDIUM",
            "detail": f"Scene lasts {duration:.2f}s."
        })

    if duration < 1.5:
        issues.append({
            "type": "VERY_SHORT_SCENE",
            "severity": "MEDIUM",
            "detail": f"Scene lasts only {duration:.2f}s."
        })

    transitions = max(
        count_visual_transitions(voice),
        count_visual_transitions(visual)
    )

    if transitions >= 2:
        issues.append({
            "type": "MULTI_BEAT_SCENE",
            "severity": "HIGH",
            "detail": f"Detected {transitions} sequential meaning/action transitions."
        })
    elif transitions == 1 and duration >= 8.0:
        issues.append({
            "type": "MULTI_BEAT_SCENE",
            "severity": "MEDIUM",
            "detail": "Long scene contains a sequential meaning/action transition."
        })

    story_text = json.dumps(story_map, ensure_ascii=False)

    for query in scene.get("search_queries", []) or []:
        for problem in suspicious_query_details(query, voice, story_text):
            issues.append({
                "type": "UNSUPPORTED_QUERY_DETAIL",
                "severity": "HIGH",
                "detail": f"{query!r}: {problem}"
            })

    return issues


def validate_plan(scenes, story_map):
    report = []

    for index, scene in enumerate(scenes, 1):
        issues = validate_scene(scene, story_map)

        report.append({
            "scene": index,
            "source_word_start": scene.get("source_word_start"),
            "source_word_end": scene.get("source_word_end"),
            "duration": scene.get("duration"),
            "issues": issues
        })

    return report


if __name__ == "__main__":
    from engine.scene_sync import sync_plan_to_master

    raw = json.loads(
        Path("data/visual_plan_real_90s_storymap.json").read_text(encoding="utf-8")
    )
    scenes = raw["scenes"] if isinstance(raw, dict) else raw

    timed = json.loads(
        Path("data/timed_script_full_v2.json").read_text(encoding="utf-8")
    )

    story_map = json.loads(
        Path("data/story_map.json").read_text(encoding="utf-8")
    )

    synced = sync_plan_to_master(
        scenes,
        timed,
        require_contiguous=True
    )

    report = validate_plan(synced, story_map)

    Path("data/scene_plan_validation_90s.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("SCENE PLAN VALIDATION: OK")

    for item in report:
        if not item["issues"]:
            continue

        print(
            f"\nSCENE {item['scene']} | "
            f"WORDS {item['source_word_start']}-{item['source_word_end']} | "
            f"{item['duration']:.2f}s"
        )

        for issue in item["issues"]:
            print(
                f"  {issue['severity']} | "
                f"{issue['type']} | "
                f"{issue['detail']}"
            )
