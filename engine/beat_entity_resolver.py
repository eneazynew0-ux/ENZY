import json
import re
import unicodedata


def _norm(text):
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _beat_text(beat):
    parts = [
        beat.get("voice_text", ""),
        beat.get("visual_intent", ""),
        " ".join(beat.get("search_queries", [])),
        " ".join(beat.get("requirements", [])),
    ]
    return _norm(" ".join(parts))


def _entity_terms(entity):
    terms = []

    for value in [
        entity.get("canonical_subject"),
        entity.get("exact_subject"),
    ]:
        value = _norm(value)
        if value:
            terms.append(("canonical", value))

    for value in entity.get("aliases_or_descriptions", []):
        value = _norm(value)
        if value:
            terms.append(("alias", value))

    location = _norm(entity.get("location"))
    if location:
        terms.append(("location", location))

    return terms


def resolve_beat_entities(beat, scene_entities):
    haystack = _beat_text(beat)
    matches = []

    for entity in scene_entities or []:
        evidence = []
        score = 0

        for kind, term in _entity_terms(entity):
            if term and term in haystack:
                evidence.append({
                    "kind": kind,
                    "term": term,
                })

                if kind == "canonical":
                    score += 100
                elif kind == "alias":
                    score += 70
                elif kind == "location":
                    score += 40

        if evidence:
            matches.append({
                "entity": entity,
                "score": score,
                "evidence": evidence,
            })

    matches.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    if not matches:
        return {
            "status": "UNRESOLVED",
            "entities": [],
        }

    best_score = matches[0]["score"]

    selected = [
        item
        for item in matches
        if item["score"] == best_score
    ]

    if len(selected) > 1:
        return {
            "status": "AMBIGUOUS",
            "entities": selected,
        }

    return {
        "status": "RESOLVED",
        "entities": selected,
    }


if __name__ == "__main__":
    import json

    with open(
        "data/beat_pipeline_90s_no_storymap_test.json",
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    resolved = 0
    unresolved = 0
    ambiguous = 0

    for item in data["results"]:
        result = item["result"]
        entities = result.get(
            "grounding_context", {}
        ).get("entities", [])

        for beat_index, beat in enumerate(
            result.get("beats", []), 1
        ):
            decision = resolve_beat_entities(
                beat,
                entities,
            )

            status = decision["status"]

            if status == "RESOLVED":
                resolved += 1
            elif status == "AMBIGUOUS":
                ambiguous += 1
            else:
                unresolved += 1

            subjects = [
                x["entity"].get("canonical_subject")
                for x in decision["entities"]
            ]

            print(
                f'SCENE {item["scene_number"]} '
                f'BEAT {beat_index}: '
                f'{status} -> {subjects}'
            )
            print(" VOICE:", beat.get("voice_text"))

    print()
    print("RESOLVED:", resolved)
    print("UNRESOLVED:", unresolved)
    print("AMBIGUOUS:", ambiguous)


def resolve_beat_entities_hybrid(
    beat,
    scene_entities,
    model=None,
    tokenizer=None,
):
    baseline = resolve_beat_entities(
        beat,
        scene_entities,
    )

    if baseline["status"] == "RESOLVED":
        return {
            **baseline,
            "resolver": "DETERMINISTIC",
        }

    if not scene_entities:
        return {
            "status": "UNRESOLVED",
            "entities": [],
            "resolver": "NO_CANDIDATES",
        }

    from mlx_lm import load, generate
    from engine.local_visual_brain import MODEL

    if model is None or tokenizer is None:
        model, tokenizer = load(MODEL)

    candidates = []

    for index, entity in enumerate(scene_entities):
        candidates.append({
            "index": index,
            "canonical_subject": entity.get(
                "canonical_subject"
            ),
            "subject_type": entity.get(
                "subject_type"
            ),
            "location": entity.get("location"),
            "aliases_or_descriptions": entity.get(
                "aliases_or_descriptions", []
            ),
            "evidence": entity.get("evidence", []),
        })

    payload = {
        "voice_text": beat.get("voice_text"),
        "visual_intent": beat.get("visual_intent"),
        "search_queries": beat.get(
            "search_queries", []
        ),
        "requirements": beat.get(
            "requirements", []
        ),
        "candidate_entities": candidates,
    }

    prompt = """
You resolve which factual entity, if any, is actually
the subject of ONE documentary visual beat.

Choose ONLY from candidate_entities.

Rules:
- Return NONE if no candidate is clearly relevant.
- Return NONE for generic narration, transitions,
  teasers, summaries, callbacks, setup lines, or atmospheric
  beats unless one candidate is explicitly the immediate
  physical or factual subject of THIS beat.
- A candidate being important to the wider story is NOT
  sufficient.
- A beat that merely sets up, foreshadows, or refers to a
  later story must return NONE unless the entity itself is
  being directly described or shown now.
- Do not choose an entity merely because its evidence
  contains words, places, or events also mentioned in the beat.
- Do not use narrative association alone.
- Resolve pronouns and indirect descriptions only when they
  clearly refer to the candidate as the current subject.
- When uncertain between a candidate and NONE, choose NONE.
- Never invent a new entity.
- If exactly one candidate is clearly the subject,
  return its integer index.

Return ONLY valid JSON:
{"choice":"NONE"}
or
{"choice":0}

INPUT:
""" + json.dumps(payload, ensure_ascii=False)

    messages = [{
        "role": "user",
        "content": prompt,
    }]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    raw = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=80,
        verbose=False,
    )

    try:
        parsed = json.loads(raw.strip())
        choice = parsed.get("choice")
    except Exception:
        return {
            "status": "UNRESOLVED",
            "entities": [],
            "resolver": "LLM_INVALID_JSON",
            "raw": raw,
        }

    if isinstance(choice, str):
        if choice.strip().upper() == "NONE":
            return {
                "status": "UNRESOLVED",
                "entities": [],
                "resolver": "LLM_NONE",
            }

        if choice.strip().isdigit():
            choice = int(choice.strip())

    if (
        isinstance(choice, int)
        and not isinstance(choice, bool)
        and 0 <= choice < len(scene_entities)
    ):
        return {
            "status": "RESOLVED",
            "entities": [{
                "entity": scene_entities[choice],
                "score": None,
                "evidence": [{
                    "kind": "contextual",
                    "term": "local Qwen resolver",
                }],
            }],
            "resolver": "LLM_CONTEXT",
        }

    return {
        "status": "UNRESOLVED",
        "entities": [],
        "resolver": "LLM_INVALID_CHOICE",
        "raw": raw,
    }
