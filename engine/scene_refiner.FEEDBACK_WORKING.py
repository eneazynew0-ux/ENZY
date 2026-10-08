import json
from pathlib import Path
from mlx_lm import load, generate

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"

SYSTEM_PROMPT = """
You are the Scene Refiner of ENZYVIDEO.

You receive ONE documentary scene that has already been flagged by a deterministic validator.

Your task is to repair ONLY that scene.

MASTER AUDIO RULE:
The narration is immutable.
You NEVER create timestamps.
You NEVER rewrite, remove, reorder, summarize or add narration words.
You may only choose boundaries using the supplied MASTER word indices.

SEMANTIC SPLITTING:
- Split only when the visual subject, location, object, action, state, or narrative beat genuinely changes.
- Every boundary must occur at a natural semantic and grammatical boundary in the narration.
- NEVER split inside a dependent phrase, clause, comparison, negation, or construction whose meaning depends on the following words.
- Never leave one scene ending with an incomplete phrase such as "the fact that", "because", "which", "that", "but", or an equivalent unfinished construction.
- Read both sides of every proposed boundary as complete meaningful narration fragments before accepting it.
- A visual change does not justify breaking the grammatical meaning of the narration.
- Preserve the narrator's logical direction. If the narration describes a stereotype, misconception, absence, denial, or claim, do not visualize the opposite factual reality until the narration itself makes that transition.
- Search queries must represent what the narrator is saying at THAT exact moment, not a later correction or reveal.
- Split only when the visual subject, location, object, action, state, or narrative beat genuinely changes.
- Do NOT split mechanically by duration.
- A long scene may remain one scene if it genuinely represents one visual idea.
- A short scene is allowed when the narration itself contains a brief but important visual beat.
- Sequential states such as "first X, then Y" usually require separate scenes when they need different footage.
- Each resulting scene should have one clear visual purpose where practical.

FACTUAL ACCURACY:
- Use the supplied Story Map as global documentary context.
- Prefer exact canonical subjects resolved by the Story Map.
- Do not substitute a different place, artifact, culture, monument, event or person.
- Do not invent years, dates, locations or historical details.
- Search queries must contain only details supported by the MASTER narration or Story Map.
- If a detail is uncertain, omit it from the query.

SEARCH QUERIES:
- English only.
- Concrete and searchable.
- Prefer the exact factual subject when known.
- Queries should help find real documentary footage or photography.
- Do not write speculative cinematic descriptions as factual search terms.

OUTPUT:
Return ONLY a valid JSON array.

Each item:
{
  "source_word_start": 0,
  "source_word_end": 0,
  "visual_intent": "...",
  "media_type": "VIDEO or PHOTO",
  "factual_priority": true,
  "search_queries": ["...", "...", "..."],
  "requirements": ["..."],
  "avoid": ["..."],
  "edit": "...",
  "mood": "..."
}

HARD BOUNDARY RULES:
- Use only supplied MASTER word indices.
- First output scene must start at the original scene's first word.
- Last output scene must end at the original scene's last word.
- Scenes must be ordered.
- No gaps.
- No overlaps.
- Every MASTER word in the original scene must belong to exactly one output scene.
- Do not output timestamps.
- Do not output voice_text.
"""


def refine_scene(scene, issues, timed_words, story_map, model=None, tokenizer=None):
    start_i = int(scene["source_word_start"])
    end_i = int(scene["source_word_end"])

    master_words = [
        {
            "script_index": int(w["script_index"]),
            "word": w["word"]
        }
        for w in timed_words
        if start_i <= int(w["script_index"]) <= end_i
    ]

    if not master_words:
        raise ValueError("No MASTER words found for scene")

    if model is None or tokenizer is None:
        model, tokenizer = load(MODEL)

    payload = {
        "original_scene": {
            k: v for k, v in scene.items()
            if k not in {"start", "end", "duration", "voice_text"}
        },
        "validator_issues": issues,
        "master_words": master_words,
        "story_map": story_map
    }

    prompt = (
        SYSTEM_PROMPT
        + "\n\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    messages = [{"role": "user", "content": prompt}]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    return generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=1800,
        verbose=False
    )


def repair_refinement(
    original_scene,
    bad_refinement,
    validation_issues,
    timed_words,
    story_map,
    model=None,
    tokenizer=None
):
    start_i = int(original_scene["source_word_start"])
    end_i = int(original_scene["source_word_end"])

    master_words = [
        {
            "script_index": int(w["script_index"]),
            "word": w["word"]
        }
        for w in timed_words
        if start_i <= int(w["script_index"]) <= end_i
    ]

    if model is None or tokenizer is None:
        model, tokenizer = load(MODEL)

    payload = {
        "original_scene": {
            k: v for k, v in original_scene.items()
            if k not in {"start", "end", "duration", "voice_text"}
        },
        "rejected_refinement": bad_refinement,
        "validation_errors": validation_issues,
        "master_words": master_words,
        "story_map": story_map
    }

    repair_rules = """
The previous refinement was REJECTED by deterministic validation.

You must repair the listed validation errors.

IMPORTANT:
- Do not defend the previous answer.
- Reconsider the scene boundaries if a boundary caused an incomplete phrase.
- A boundary ending on a connector such as Russian "что" is invalid.
- Requirements and avoid rules must never contradict each other.
- Preserve exact contiguous MASTER word coverage.
- Do not invent timestamps.
- Do not invent facts.
- Do not reverse the narrator's meaning.
- If no semantically clean split exists, returning ONE scene covering the entire original range is valid.
- Return ONLY the corrected JSON array.
"""

    prompt = (
        SYSTEM_PROMPT
        + "\n\n"
        + repair_rules
        + "\n\nREPAIR INPUT:\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    messages = [{"role": "user", "content": prompt}]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    return generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=1800,
        verbose=False
    )


if __name__ == "__main__":
    print("SCENE REFINER MODULE: OK")
