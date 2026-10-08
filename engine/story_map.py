import json
from pathlib import Path


def normalize_text(value):
    return " ".join(str(value or "").lower().strip().split())


def clean_story_map(story_map):
    data = dict(story_map)

    coreferences = data.get("coreferences", [])
    unresolved = data.get("unresolved", [])

    resolved_refs = set()

    for item in coreferences:
        confidence = str(item.get("confidence", "")).upper()
        subject = normalize_text(item.get("resolved_subject"))

        if confidence in {"HIGH", "MEDIUM"} and subject and subject != "unknown":
            ref = normalize_text(item.get("early_reference"))
            if ref:
                resolved_refs.add(ref)

    cleaned_unresolved = []

    for item in unresolved:
        ref = normalize_text(item.get("reference"))

        if ref and ref in resolved_refs:
            continue

        cleaned_unresolved.append(item)

    data["unresolved"] = cleaned_unresolved
    return data


def load_and_clean(input_path, output_path=None):
    source = json.loads(
        Path(input_path).read_text(encoding="utf-8")
    )

    cleaned = clean_story_map(source)

    if output_path:
        Path(output_path).write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    return cleaned


if __name__ == "__main__":
    result = load_and_clean(
        "data/story_map_raw.json",
        "data/story_map.json"
    )

    print("STORY MAP CLEAN: OK")
    print("CHAPTERS:", len(result.get("chapters", [])))
    print("ENTITIES:", len(result.get("entities", [])))
    print("COREFERENCES:", len(result.get("coreferences", [])))
    print("UNRESOLVED:", len(result.get("unresolved", [])))

    for item in result.get("unresolved", []):
        print("-", item.get("reference"))
