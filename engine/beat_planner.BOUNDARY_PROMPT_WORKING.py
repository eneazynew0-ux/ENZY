import json
from pathlib import Path

from mlx_lm import generate

from engine.visual_beats import find_candidate_beat_boundaries


BEAT_SYSTEM_PROMPT = """
You are the Visual Beat Planner for a documentary editing system.

A SEMANTIC SCENE is already correctly synchronized to an immutable MASTER narration.
Your job is NOT to rewrite or retime the narration.

Your job is to decide whether the scene should contain:
- one continuous visual beat, or
- several internal visual beats because the narration changes visible state, location, action, subject, object, or time.

IMPORTANT:
- A visual beat means a meaningful change in what should be shown on screen.
- Do not split merely because a sentence contains commas or conjunctions.
- Do not create rapid cuts without a visual reason.
- Preserve one continuous beat when the same visual idea can naturally cover the narration.
- Split when keeping one visual would make the picture contradict or lag behind the narration.
- Candidate boundaries are semantic transition points detected directly from MASTER narration.
- You may reject a candidate boundary if no visual change is actually needed there.
- BUT if you decide that a visual change corresponds to a supplied candidate boundary, the new beat MUST start exactly at that candidate_new_beat_start.
- Never move a supplied candidate boundary earlier or later.
- Do not choose a nearby word index merely because it seems visually convenient.
- A free boundary not present in candidate_boundaries is allowed only when a necessary visual change has no suitable supplied candidate.
- Every beat boundary must use an existing MASTER script_index.
- Beats must cover the entire semantic scene exactly.
- No gaps.
- No overlaps.
- Keep beats in narration order.
- Never invent timestamps.
- Never output start, end, duration, seconds, or timecodes.
- Never alter MASTER narration.
- Story Map is context for identifying subjects only.
- Never invent factual details not supported by the narration or Story Map.
- Search queries must be in English.
- Search queries should describe real footage or real photographs that could actually be searched for.
- Prefer exact named subjects when supported.
- Do not invent dates, places, people, cultures, or events.

For each beat output:
source_word_start
source_word_end
visual_intent
search_queries
requirements
avoid
edit

Return JSON only in this exact structure:

{
  "needs_multiple_beats": true,
  "reason": "short explanation",
  "beats": [
    {
      "source_word_start": 0,
      "source_word_end": 0,
      "visual_intent": "what should visibly be on screen",
      "search_queries": ["query 1", "query 2"],
      "requirements": ["required visual facts"],
      "avoid": ["wrong or misleading visuals"],
      "edit": "appropriate documentary editing treatment"
    }
  ]
}
"""


def _scene_master_words(scene, timed_words):
    start = int(scene["source_word_start"])
    end = int(scene["source_word_end"])

    return [
        {
            "script_index": int(w["script_index"]),
            "word": str(w["word"]),
        }
        for w in timed_words
        if start <= int(w["script_index"]) <= end
    ]


def build_beat_prompt(scene, timed_words, story_map):
    master_words = _scene_master_words(scene, timed_words)

    candidates = find_candidate_beat_boundaries(
        scene,
        timed_words,
    )

    payload = {
        "semantic_scene": {
            "source_word_start": int(scene["source_word_start"]),
            "source_word_end": int(scene["source_word_end"]),
            "voice_text": scene.get("voice_text", ""),
            "visual_intent": scene.get("visual_intent", ""),
        },
        "master_words": master_words,
        "candidate_boundaries": candidates,
        "story_map": story_map,
    }

    return (
        BEAT_SYSTEM_PROMPT
        + "\n\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def run_beat_planner(
    scene,
    timed_words,
    story_map,
    model,
    tokenizer,
    max_tokens=1400,
):
    prompt = build_beat_prompt(
        scene,
        timed_words,
        story_map,
    )

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    return generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=max_tokens,
        verbose=False,
    )


if __name__ == "__main__":
    from mlx_lm import load
    from engine.local_visual_brain import MODEL

    timed = json.loads(
        Path("data/timed_script_full_v2.json")
        .read_text(encoding="utf-8")
    )

    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json")
        .read_text(encoding="utf-8")
    )

    story_map = json.loads(
        Path("data/story_map.json")
        .read_text(encoding="utf-8")
    )

    scene = next(
        s for s in plan["scenes"]
        if int(s["source_word_start"]) == 87
        and int(s["source_word_end"]) == 114
    )

    print("LOADING QWEN...")
    model, tokenizer = load(MODEL)

    print("PLANNING VISUAL BEATS FOR SCENE 87->114...")

    result = run_beat_planner(
        scene,
        timed,
        story_map,
        model,
        tokenizer,
    )

    print(result)

    Path("data/beat_plan_scene7_raw.json").write_text(
        result,
        encoding="utf-8",
    )
