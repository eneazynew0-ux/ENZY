import json
import re

from mlx_lm import generate


def judge_video_metadata(asset, target, model, tokenizer):
    metadata = {
        "title": str(asset.get("title") or "").strip(),
        "tags": str(asset.get("tags") or "").strip(),
    }

    prompt = """You are a conservative metadata relevance gate for documentary stock video search.

Decide whether this video candidate is worth downloading for the requested visual target.

You are judging ONLY provider metadata: title and tags.
You are NOT judging pixels and must not invent anything that is not present in metadata.

Rules:
- MATCH only when the metadata gives reasonable positive evidence that the video could visually represent the target.
- REJECT when metadata clearly describes a different subject, activity, object type, or context.
- Shared generic words are not enough. For example, "excavation" in construction metadata does not prove archaeological excavation.
- Do not infer archaeology from construction machinery, digging, dirt, or excavation alone.
- Do not infer a specific place, artifact, culture, historical event, or profession unless metadata supports it.
- A candidate may be broad B-roll, but its main metadata subject must still be visually compatible with the target.
- If evidence is ambiguous or weak, REJECT. This gate should save bandwidth by avoiding poor downloads.
- Be conservative.
- Score relevance from 0 to 100.
- Return ONLY valid JSON.

Required format:
{"decision":"MATCH or REJECT","score":0,"reason":"short reason"}

VISUAL TARGET:
""" + str(target) + """

VIDEO METADATA:
""" + json.dumps(metadata, ensure_ascii=False)

    messages = [{"role": "user", "content": prompt}]

    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        formatted = prompt

    raw = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=100,
        verbose=False,
    ).strip()

    match = re.search(r"\{.*?\}", raw, re.S)
    if not match:
        return {
            "decision": "REJECT",
            "score": 0,
            "reason": "Metadata judge returned invalid output",
            "raw": raw,
        }

    try:
        result = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "decision": "REJECT",
            "score": 0,
            "reason": "Metadata judge returned invalid JSON",
            "raw": raw,
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
