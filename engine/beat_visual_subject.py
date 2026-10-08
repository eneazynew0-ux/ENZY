import json

from mlx_lm import generate
from engine.local_visual_brain import MODEL


def resolve_visual_subject(
    beat,
    entity,
    model=None,
    tokenizer=None,
):
    """
    Decide whether a resolved contextual entity should be injected
    into visual search queries for THIS beat.

    This is intentionally separate from entity resolution:
    an entity may belong to the story while not being the visual
    subject of the current beat.
    """

    if not entity:
        return {
            "use_entity_for_search": False,
            "reason": "NO_ENTITY",
            "confidence": "HIGH",
        }

    if model is None or tokenizer is None:
        from mlx_lm import load
        model, tokenizer = load(MODEL)

    payload = {
        "beat": {
            "voice_text": beat.get("voice_text", ""),
            "visual_intent": beat.get("visual_intent", ""),
            "requirements": beat.get("requirements", []),
        },
        "entity": {
            "canonical_subject": entity.get(
                "canonical_subject", ""
            ),
            "subject_type": entity.get("subject_type", ""),
            "location": entity.get("location", ""),
            "aliases_or_descriptions": entity.get(
                "aliases_or_descriptions", []
            ),
        },
    }

    prompt = """
You are a conservative visual-search grounding judge.

A separate system has already determined that the supplied ENTITY
belongs to the surrounding story context.

Your ONLY task is to decide whether that ENTITY should be explicitly
used in image/video SEARCH QUERIES for THIS exact beat.

Important distinction:
A beat can belong to an entity's story without visually depicting
that entity.

Return YES only when adding the entity name, identity, or a specific
entity alias would make the visual search more factually accurate.

Examples of YES:
- a beat describing a specific archaeological site's stone circle,
  when the entity is that archaeological site
- a beat describing terracotta artifacts characteristic of a
  specific culture, when the entity is that culture
- a beat describing the rescue of a specific historical library,
  when the entity is that library
- a beat describing a distinctive rock-cut church, when the entity
  is that church complex

NAMED PLACE RULE:
- If ENTITY is a named place and the current narration explicitly
  locates the visible action there, return YES for that place.
- The place need not be the foreground object. A guard at a named
  airport requires that airport identity for accurate footage search.
- This is different from selecting an artifact associated with
  the airport: reject the artifact unless this beat depicts it.
- A place mentioned only as a later callback is still NO.
- Selecting a place does not verify an event or date occurring there.
- Never infer the place from visual_intent alone.

Examples of NO:
- an airport guard merely setting up a story about an artifact,
  when the supplied ENTITY is that artifact rather than the airport
- a teaser saying the story will return to an earlier subject later
- a transition, callback, summary, generic atmosphere, or suspense
  beat where the entity itself should not determine the footage
- the entity is only relevant because of wider story context

Judge the immediate visual search need, not the overall narrative.

Use voice_text as the primary evidence.
visual_intent may clarify what should be shown, but it must not
override the narration or create a factual identity absent from it.

A YES decision requires that the current beat itself describes,
depicts, identifies, or materially specifies the entity or one of
its characteristic physical objects.

Narrative importance is never enough.

Words or ideas such as:
- returning to an earlier story
- closing a circle
- the biggest story comes later
- a climax or ending
- a callback to an earlier location
- symbolic importance
- national significance

do NOT justify YES by themselves.

A location reference alone does not justify injecting an artifact,
person, culture, monument, or institution associated with that
location.

Do not invent an entity as a visual anchor merely because it would
make the scene more dramatic.

For YES, your reason must identify the concrete visual/factual feature
in THIS beat that requires or strongly benefits from the entity
identity.

If you cannot point to such a feature in the current beat, choose NO.

When uncertain, choose NO.

Return ONLY valid JSON in exactly this form:
{"use_entity_for_search":true,"confidence":"HIGH","reason":"short reason"}
or
{"use_entity_for_search":false,"confidence":"HIGH","reason":"short reason"}

INPUT:
""" + json.dumps(payload, ensure_ascii=False)

    formatted = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
    )

    raw = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=120,
        verbose=False,
    ).strip()

    try:
        parsed = json.loads(raw)
    except Exception:
        return {
            "use_entity_for_search": False,
            "confidence": "LOW",
            "reason": "INVALID_JSON",
            "raw": raw,
        }

    decision = parsed.get("use_entity_for_search")

    if decision is not True:
        decision = False

    return {
        "use_entity_for_search": decision,
        "confidence": str(
            parsed.get("confidence", "UNKNOWN")
        ).upper(),
        "reason": str(parsed.get("reason", "")),
        "raw": raw,
    }
