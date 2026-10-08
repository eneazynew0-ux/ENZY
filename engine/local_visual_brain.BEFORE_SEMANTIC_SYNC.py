import json
from mlx_lm import load, generate

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"

def run_visual_brain(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    model, tokenizer = load(MODEL)

    prompt = """You are the Visual Brain of ENZYVIDEO, an automated documentary editor.

Analyze the Russian narration blocks below and design the REAL visual material that should accompany them.

RULES:
- Understand meaning, not isolated keywords.
- Prefer real documentary footage and real photography.
- Identify exact places, artifacts, cultures and historical subjects whenever narration supports them.
- Never replace a specific factual subject with unrelated generic stock.
- Use factual_priority=true when exact identity matters.
- media_type must be VIDEO, PHOTO, MAP, or GRAPHIC.
- Search queries must be concise ENGLISH queries suitable for Pexels, Pixabay, Wikimedia Commons, museums and public-domain archives.
- Give 2-4 complementary search queries per scene.
- requirements = what absolutely must be visible.
- avoid = plausible but incorrect visuals that must be rejected.
- edit = restrained professional documentary editing.
- mood = intended emotional tone.
- Do NOT modify, shorten, rewrite, or reinterpret the narration.
- Do NOT invent historical facts.
- Do NOT invent timestamps.
- Keep source_word_start and source_word_end exactly within the supplied word-index boundaries.
- Return ONLY valid JSON. No markdown and no explanation.

OUTPUT:
{"scenes":[{"source_sentence_id":1,"source_word_start":0,"source_word_end":10,"visual_intent":"...","media_type":"VIDEO","factual_priority":true,"search_queries":["..."],"requirements":["..."],"avoid":["..."],"edit":"...","mood":"..."}]}

NARRATION:
""" + json.dumps(data["narration"], ensure_ascii=False)

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
