"""Repair generated visual fields without giving the model control of MASTER."""
import copy
import json
from mlx_lm import generate
from engine.beat_visual_contract import repair_artifact_cutaway
from engine.beat_claim_visual import reported_claim_cutaway

VISUAL_FIELDS = {"visual_intent", "search_queries", "requirements", "avoid", "edit"}


def repair_beat_visual(beat, issues, grounding, preceding_text, model, tokenizer):
    claim_cutaway = reported_claim_cutaway(beat, issues, preceding_text)
    if claim_cutaway is not None:
        return claim_cutaway
    contextual = repair_artifact_cutaway(beat, issues, grounding)
    if contextual is not None:
        return contextual
    payload = {
        "immutable_narration": beat["voice_text"],
        "preceding_narration_for_referents_only": preceding_text,
        "grounded_entities": grounding.get("entities", []),
        "rejected_visual": {key: beat.get(key) for key in sorted(VISUAL_FIELDS)},
        "audit_issues": issues,
    }
    prompt = """Repair a rejected documentary media search plan.
Return ONLY a JSON object with these five keys:
visual_intent (string), search_queries (list of strings),
requirements (list of strings), avoid (list of strings), edit (string).
No other keys. Never output narration, boundaries, timing or duration.
Use English for visual fields and concise search queries.
Resolve pronouns using preceding narration. An artifact is not a person.
Remove unsupported people, actions, years and historical staging.
Do not fabricate furniture, scenery, climate control, cases or transport.
Context identifies the referent; it does not authorize new events.
Prefer a real photograph or real footage of the supported subject itself.
For historical circumstances without supported footage, describe a contextual
cutaway of the identified subject, explicitly not the historical event.
Do not invent an identity if it remains ambiguous.
Do not request captions, labels, readable text, arrows, watermarks or logos.
Put exclusions in avoid, not positive visual requirements.
Camera framing and gentle editing motion are allowed.
INPUT:
""" + json.dumps(payload, ensure_ascii=False)
    formatted = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False, add_generation_prompt=True,
    )
    raw = generate(model, tokenizer, prompt=formatted, max_tokens=850, verbose=False)
    parsed = json.loads(raw.strip())
    if not isinstance(parsed, dict) or set(parsed) != VISUAL_FIELDS:
        raise ValueError("VISUAL_REPAIR_INVALID_FIELDS")
    for key in ("visual_intent", "edit"):
        if not isinstance(parsed[key], str) or not parsed[key].strip():
            raise ValueError("VISUAL_REPAIR_INVALID_TEXT: " + key)
    for key in ("search_queries", "requirements", "avoid"):
        values = parsed[key]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ValueError("VISUAL_REPAIR_INVALID_LIST: " + key)
    if not parsed["search_queries"] or not parsed["requirements"]:
        raise ValueError("VISUAL_REPAIR_EMPTY_SEARCH_OR_REQUIREMENTS")
    result = copy.deepcopy(beat)
    result.update(parsed)
    return result
