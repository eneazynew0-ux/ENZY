import json

from mlx_lm import load

from engine.scene_refiner import (
    MODEL,
    refine_scene,
    repair_refinement,
)
from engine.refinement_validator import validate_refinement


def parse_json_array(raw):
    if isinstance(raw, list):
        return raw

    if not isinstance(raw, str):
        raise ValueError("Refiner output must be JSON string or list")

    text = raw.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    data = json.loads(text)

    if not isinstance(data, list):
        raise ValueError("Refiner output must contain a JSON array")

    return data


def run_refinement_cycle(
    original_scene,
    validator_issues,
    timed_words,
    story_map,
    max_repairs=2,
    model=None,
    tokenizer=None,
):
    start_i = int(original_scene["source_word_start"])
    end_i = int(original_scene["source_word_end"])

    if model is None or tokenizer is None:
        model, tokenizer = load(MODEL)

    history = []

    raw = refine_scene(
        original_scene,
        validator_issues,
        timed_words,
        story_map,
        model=model,
        tokenizer=tokenizer,
    )

    try:
        candidate = parse_json_array(raw)
    except Exception as e:
        return {
            "status": "REJECTED",
            "reason": "INVALID_JSON",
            "error": str(e),
            "scenes": [original_scene],
            "history": history,
        }

    for attempt in range(max_repairs + 1):
        check = validate_refinement(
            candidate,
            timed_words,
            original_start=start_i,
            original_end=end_i,
        )

        history.append({
            "attempt": attempt,
            "valid": check["valid"],
            "issues": check["issues"],
            "candidate": candidate,
        })

        if check["valid"]:
            return {
                "status": "ACCEPTED",
                "repairs_used": attempt,
                "scenes": candidate,
                "history": history,
            }

        if attempt >= max_repairs:
            break

        raw = repair_refinement(
            original_scene,
            candidate,
            check["issues"],
            timed_words,
            story_map,
            model=model,
            tokenizer=tokenizer,
        )

        try:
            candidate = parse_json_array(raw)
        except Exception as e:
            history.append({
                "attempt": attempt + 1,
                "valid": False,
                "issues": ["INVALID_JSON"],
                "error": str(e),
            })
            break

    return {
        "status": "FALLBACK",
        "reason": "REFINEMENT_FAILED_VALIDATION",
        "scenes": [original_scene],
        "history": history,
    }


if __name__ == "__main__":
    print("REFINEMENT CONTROLLER MODULE: OK")
