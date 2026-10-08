import json
from mlx_lm import load, generate

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"

def analyze_facts(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    model, tokenizer = load(MODEL)

    prompt = """You are the factual identification layer of ENZYVIDEO, an automated documentary editor.

Your ONLY task is to identify what the narration is actually referring to BEFORE another system searches for visual material.

The narration is Russian. Analyze its context carefully across ALL supplied blocks, not sentence-by-sentence in isolation.

RULES:
- Identify specific named or strongly implied places, archaeological sites, artifacts, cultures, civilizations, people, events and historical objects.
- Use surrounding narration to resolve indirect references.
- Example: if an object is called only "a stone bird", use surrounding geographic and historical clues to determine its identity when reasonably possible.
- Do not create visual search queries yet.
- Do not invent facts merely to fill fields.
- If exact identity cannot be established from the supplied narration, say UNKNOWN.
- Distinguish an exact factual subject from generic illustrative narration.
- factual_priority=true only when showing the correct real subject materially affects documentary accuracy.
- confidence must be HIGH, MEDIUM, or LOW.
- If confidence is LOW, exact_subject should be UNKNOWN rather than a guess.
- Never infer an exact date from phrases such as "this year" unless the date is explicitly supplied.
- Do not modify narration.
- Return ONLY valid JSON. No markdown, comments, or explanation.

For every narration block return:
sentence_id
exact_subject
subject_type
location
historical_period
factual_priority
confidence
evidence
unknowns
forbidden_assumptions

OUTPUT FORMAT:
{"facts":[{"sentence_id":1,"exact_subject":"...","subject_type":"...","location":"...","historical_period":"...","factual_priority":true,"confidence":"HIGH","evidence":["..."],"unknowns":["..."],"forbidden_assumptions":["..."]}]}

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
    result = analyze_facts("data/scene_planner_input.json")
    print(result)

    with open("data/fact_analysis_test.json", "w", encoding="utf-8") as f:
        f.write(result)
