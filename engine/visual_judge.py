import json
import re
from pathlib import Path

from mlx_lm import load, generate


MODEL_PATH = (
    Path.home()
    / ".cache/huggingface/hub/models--mlx-community--Qwen3-4B-Instruct-2507-4bit"
    / "snapshots/50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b"
)

_MODEL = None
_TOKENIZER = None


def load_judge():
    global _MODEL, _TOKENIZER

    if _MODEL is None or _TOKENIZER is None:
        _MODEL, _TOKENIZER = load(str(MODEL_PATH))

    return _MODEL, _TOKENIZER


def judge_visual(target, description):
    model, tokenizer = load_judge()

    prompt = f"""You are a conservative visual relevance judge for documentary footage.

VISUAL TARGET:
{target}

VISIBLE IMAGE DESCRIPTION:
{description}

Judge only whether the VISIBLE CONTENT is useful for representing the visual target.

Important rules:
- Do not assume facts that are not visible.
- A clearly wrong object type must be REJECT.
- Judge VISUAL COMPATIBILITY only. Do not require the image itself to prove geographic origin, culture, date, or exact historical identity; those facts are verified separately from source metadata and research.
- If the target requires an artifact but the image is a flag, map, logo, unrelated landscape, or another clearly wrong object type, REJECT.
- If the visible main subject has the correct physical object type and appearance for the target, return MATCH even when exact provenance cannot be established from pixels alone. Reduce the score for uncertainty instead of rejecting it.
- Give the MAIN VISIBLE SUBJECT much more weight than secondary descriptive details. Vision descriptions may contain unreliable secondary details.
- If the main object class is compatible (for example statue/sculpture versus carved figure/artifact), do not REJECT solely because of uncertain details such as container, room, material, color, pose, or background. Lower the score instead.
- REJECT when the main visible subject itself is incompatible with the target.
- Score relevance from 0 to 100.
- Be conservative.

Return ONLY valid JSON:
{{"decision":"MATCH or REJECT","score":0,"reason":"short reason"}}"""

    messages = [{"role": "user", "content": prompt}]

    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        formatted = prompt

    output = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=80,
        verbose=False,
    )

    match = re.search(r"\{.*?\}", output, re.S)

    if not match:
        return {
            "decision": "REJECT",
            "score": 0,
            "reason": "Judge returned invalid output",
            "raw": output.strip(),
        }

    try:
        result = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "decision": "REJECT",
            "score": 0,
            "reason": "Judge returned invalid JSON",
            "raw": output.strip(),
        }

    decision = str(result.get("decision", "REJECT")).upper()
    if decision not in {"MATCH", "REJECT"}:
        decision = "REJECT"

    try:
        score = int(result.get("score", 0))
    except (TypeError, ValueError):
        score = 0

    score = max(0, min(100, score))

    return {
        "decision": decision,
        "score": score,
        "reason": str(result.get("reason", "")).strip(),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        raise SystemExit(
            'Usage: python -m engine.visual_judge "TARGET" "DESCRIPTION"'
        )

    print(
        json.dumps(
            judge_visual(sys.argv[1], sys.argv[2]),
            ensure_ascii=False,
            indent=2,
        )
    )


def _description_is_valid(description):
    text = " ".join(str(description or "").strip().split())

    if len(text) < 20:
        return False

    lower = text.lower()

    instruction_phrases = (
        "answer with a short factual description",
        "answer with a factual description",
        "describe the image",
        "describe the main subject",
        "describe the objects",
        "describe the background",
        "describe the scene",
        "describe in detail",
        "do not repeat",
        "visible image",
    )

    instruction_hits = sum(
        lower.count(phrase)
        for phrase in instruction_phrases
    )

    if instruction_hits >= 1:
        return False

    words = lower.split()
    if words:
        unique_ratio = len(set(words)) / len(words)
        if len(words) >= 12 and unique_ratio < 0.35:
            return False

    return True


def evaluate_image(image_path, target):
    from engine.visual_relevance import describe_image

    description = describe_image(image_path)

    if not _description_is_valid(description):
        return {
            "image": str(image_path),
            "target": target,
            "description": description,
            "decision": "REJECT",
            "score": 0,
            "reason": "Invalid or instruction-echoing vision description",
        }

    judgment = judge_visual(target, description)

    return {
        "image": str(image_path),
        "target": target,
        "description": description,
        "decision": judgment["decision"],
        "score": judgment["score"],
        "reason": judgment["reason"],
    }
