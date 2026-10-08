from pathlib import Path
import json
from mlx_lm import load, generate

from engine.scene_planner import SYSTEM_PROMPT

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"


def run_visual_brain(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    narration = data.get("narration")
    if narration is None:
        raise ValueError("Planner input is missing 'narration'")

    model, tokenizer = load(MODEL)

    prompt = (
        SYSTEM_PROMPT
        + """

Return ONLY valid JSON. No markdown and no explanation.

JSON FORMAT:
{"scenes":[{"source_word_start":0,"source_word_end":10,"visual_intent":"...","media_type":"VIDEO","factual_priority":true,"search_queries":["..."],"requirements":["..."],"avoid":["..."],"edit":"...","mood":"..."}]}

IMPORTANT:
- Use only source_word_start/source_word_end values present in the supplied narration.
- Cover the supplied narration continuously from its first word index through its last word index.
- No gaps.
- No overlaps.
- Do not output timestamps.
- Do not output invented narration text.
- Split only where the visual meaning genuinely changes.

NARRATION:
"""
        + """
GLOBAL STORY MAP:
The following map was produced from the COMPLETE documentary narration.
Use it to resolve indirect references, teasers, callbacks, exact places,
artifacts, civilizations and monuments in the local narration below.

IMPORTANT:
- Treat the Story Map as global narrative context.
- If a local phrase clearly corresponds to a resolved coreference in the Story Map, use that exact resolved subject.
- Prefer exact canonical subjects from the Story Map over generic guesses.
- Never replace a known subject with a geographically plausible substitute.
- Do not invent a connection that the Story Map does not support.
- The Story Map helps identification only; source_word_start/source_word_end must still come exclusively from NARRATION.

STORY_MAP:
"""
        + json.dumps(
            json.loads(Path("data/story_map.json").read_text(encoding="utf-8")),
            ensure_ascii=False
        )
        + """

LOCAL NARRATION TO PLAN:
"""
        + json.dumps(narration, ensure_ascii=False)
    )

    messages = [{"role": "user", "content": prompt}]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    result = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=2500,
        verbose=False
    )

    return result


if __name__ == "__main__":
    result = run_visual_brain("data/scene_planner_input.json")
    print(result)

    with open("data/local_visual_plan_test.json", "w", encoding="utf-8") as f:
        f.write(result)
