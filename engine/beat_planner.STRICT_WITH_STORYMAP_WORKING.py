import json
from pathlib import Path

from mlx_lm import generate

from engine.visual_beats import find_candidate_beat_boundaries
from engine.beat_grounding import build_local_grounding_context


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
- grounding_context is the ONLY Story Map context available for this semantic scene.
- MASTER narration is authoritative.

- STRICT LOCAL EVIDENCE RULE: every visual beat must be justified by the actual MASTER words inside that beat's own source_word_start..source_word_end range.

- A beat may visualize only subjects, objects, actions, states, locations, or concepts actually expressed by its own MASTER word range.

- Do not use words outside the proposed beat range to justify that beat.

- grounding_context may clarify the identity, canonical name, location, or alias of something ALREADY present in the beat's MASTER words.

- grounding_context must NEVER introduce a different object, event, action, person, artifact, or future/past story element absent from the beat's own MASTER words.

- Story Map context is grounding metadata, NOT additional narration.

- Never pull a reveal from a later sentence or scene into the current beat.

- Never pull an earlier event into the current beat merely because Story Map connects them.

- NEGATION RULE: do not turn something mentioned only through negation, exclusion, absence, threat, comparison, belief, or hypothetical language into a positive factual event on screen.

- Example: "not the president" does NOT justify showing a president.

- Example: "saved from militants" does NOT by itself justify inventing a militant attack, armed convoy, battle, or militants physically handling the object.

- Example: "no buildings" does NOT justify inventing a special map or graphic labeled as having no buildings.

- If narration describes absence, omission, belief, uncertainty, comparison, or metaphor, prefer a neutral visual supported by the positive factual content of MASTER.

- Do not invent reactions, gestures, professions, actions, historical circumstances, or physical interactions merely to make the beat more cinematic.

- Do not invent text overlays, captions, labels, arrows, red crosses, flags, banknotes, maps, diagrams, or symbolic composites unless MASTER explicitly calls for that visible element.

- visual_intent must describe a plausible real photograph or real video shot whenever possible.

- edit must describe treatment of real footage or photography; it must not add unsupported factual content.

- grounding_context may clarify subject, location, aliases and evidence, but must never override MASTER.
- Do not introduce a concrete culture, country, city, historical identity, plant, animal, artifact identity, date, century, person or event unless supported by MASTER narration or grounding_context.
- Never replace a MASTER object with a different object.
- Never assign an artifact to a different culture or country than grounding_context supports.
- If a detail is uncertain, stay general instead of inventing specificity.
- Never invent factual details not supported by MASTER narration or grounding_context.
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

    parent_master_text = " ".join(
        str(w["word"]) for w in master_words
    )

    grounding_context = build_local_grounding_context(
        parent_master_text,
        story_map,
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
        "grounding_context": grounding_context,
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
