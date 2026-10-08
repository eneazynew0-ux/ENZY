import json
import re
from pathlib import Path


def norm(text):
    return " ".join(str(text or "").lower().replace("ё", "е").split())


def collect_strings(value):
    out = []

    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for item in value:
            out.extend(collect_strings(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(collect_strings(item))

    return out


def phrase_present(phrase, text):
    """Match complete tokens, ignoring punctuation, without substring identities."""
    tokens = lambda value: re.findall(r"\w+", norm(value))
    needle, haystack = tokens(phrase), tokens(text)
    return bool(needle) and any(
        haystack[i:i + len(needle)] == needle
        for i in range(len(haystack) - len(needle) + 1)
    )


def build_causal_grounding_context(current_text, preceding_text, story_map):
    """Expose identity only after a local mention; never inherit chapter staging.

    Evidence quotes must be present verbatim in available narration. This is
    intentionally conservative: unresolved references remain blocked rather
    than borrowing a future reveal. It is not an asset identity certificate.
    """
    available = preceding_text + " " + current_text
    entities, withheld = [], []
    for entity in story_map.get("entities", []):
        terms = [entity.get("canonical_subject"), entity.get("exact_subject")]
        terms += entity.get("aliases_or_descriptions") or []
        terms = [term for term in terms if isinstance(term, str) and term.strip()]
        # Explicit inflected aliases for this named airport, not general stemming.
        if entity.get("canonical_subject") == "аэропорт Хараре":
            terms += ["аэропорту Хараре", "аэропорта Хараре", "аэропортом Хараре"]
        # Provider identity is bilingual but must not establish local presence.
        researched = entity.get("researched_search_identity") or {}
        search_terms = []
        if researched.get("status") == "VERIFIED":
            search_terms = [researched.get("canonical_subject"), researched.get("subject_type")]
            search_terms += researched.get("aliases") or []
            # Physical-description variants of this verified soapstone artifact.
            # These help reject a premature reveal; they never prove an asset.
            if researched.get("subject_type") == "soapstone bird sculpture":
                search_terms += ["stone bird", "stone sculpture of a bird"]
        search_terms = [term for term in search_terms if isinstance(term, str) and term.strip()]
        mentions = [term for term in terms if phrase_present(term, available)]
        quotes = [quote for quote in (entity.get("evidence") or [])
                  if isinstance(quote, str) and len(norm(quote)) >= 40
                  and phrase_present(quote, available)]
        if mentions or quotes:
            entities.append({
                "canonical_subject": entity.get("canonical_subject", ""),
                "exact_subject": entity.get("exact_subject", ""),
                "aliases_or_descriptions": terms,
                "evidence": quotes,
                "identity_trace": {"matched_mentions": mentions,
                                   "matched_quotes": quotes,
                                   "scope": "current_and_preceding_narration_only"},
            })
            if researched.get("status") == "VERIFIED":
                entities[-1]["researched_search_identity"] = {
                    key: researched.get(key) for key in
                    ("status", "canonical_subject", "subject_type", "aliases", "source_url", "basis", "scope")
                }
        else:
            withheld.append({"canonical_subject": entity.get("canonical_subject", ""),
                             "terms": terms + search_terms})
    return {"master_text": current_text, "chapters": [], "entities": entities,
            "withheld_entities": withheld, "chapter_match_score": 0}


def score_context(master_text, item):
    """
    Conservative lexical score used only to select relevant Story Map context.
    It does NOT decide factual truth.
    """
    master_words = {
        w.strip(".,:;!?()[]«»\"'")
        for w in norm(master_text).split()
        if len(w.strip(".,:;!?()[]«»\"'")) >= 4
    }

    context_words = set()

    for text in collect_strings(item):
        for word in norm(text).split():
            word = word.strip(".,:;!?()[]«»\"'")
            if len(word) >= 4:
                context_words.add(word)

    return len(master_words & context_words)


def build_local_grounding_context(master_text, story_map):
    chapters = story_map.get("chapters", [])
    entities = story_map.get("entities", [])

    ranked_chapters = sorted(
        (
            (score_context(master_text, chapter), chapter)
            for chapter in chapters
        ),
        key=lambda x: x[0],
        reverse=True,
    )

    best_score = ranked_chapters[0][0] if ranked_chapters else 0

    selected_chapters = [
        chapter
        for score, chapter in ranked_chapters
        if score == best_score and score > 0
    ]

    selected_subjects = set()

    for chapter in selected_chapters:
        for key in ("primary_subject", "title"):
            value = chapter.get(key)
            if value:
                selected_subjects.add(norm(value))

    selected_entities = []

    for entity in entities:
        subject = norm(entity.get("canonical_subject", ""))

        chapter_match = any(
            subject and (
                subject in candidate
                or candidate in subject
            )
            for candidate in selected_subjects
        )

        # Direct mentions can supply supporting places and events,
        # even when they are not the chapter's primary subject.
        master = norm(master_text)
        terms = [
            entity.get("canonical_subject"),
            entity.get("exact_subject"),
            *(entity.get("aliases_or_descriptions") or []),
        ]
        direct_match = any(
            term and (" " + term + " ") in (" " + master + " ")
            for term in (norm(value) for value in terms)
        )

        # Verbatim evidence can preserve inflected source wording.
        evidence_match = any(
            len(quote) >= 40 and quote in master
            for quote in (
                norm(value) for value in (entity.get("evidence") or [])
            )
        )

        if chapter_match or direct_match or evidence_match:
            selected_entities.append(entity)

    return {
        "master_text": master_text,
        "chapter_match_score": best_score,
        "chapters": selected_chapters,
        "entities": selected_entities,
    }


if __name__ == "__main__":
    from engine.beat_boundary_gate import gate_beat_boundaries
    from engine.beat_sync import sync_beats_to_scene

    timed = json.loads(
        Path("data/timed_script_full_v2.json").read_text(encoding="utf-8")
    )

    plan = json.loads(
        Path("data/visual_plan_90s_refined_batch.json").read_text(encoding="utf-8")
    )

    story = json.loads(
        Path("data/story_map.json").read_text(encoding="utf-8")
    )

    raw = json.loads(
        Path("data/beat_plan_scene7_raw.PROMPT_GATE_FAILED.json").read_text(
            encoding="utf-8"
        )
    )

    scene = next(
        s for s in plan["scenes"]
        if int(s["source_word_start"]) == 87
        and int(s["source_word_end"]) == 114
    )

    gated = gate_beat_boundaries(scene, raw["beats"], timed)
    synced = sync_beats_to_scene(scene, gated, timed)

    # Grounding belongs to the parent semantic scene.
    # Internal visual beats inherit that context so references such as
    # "а потом..." / "прежде чем..." do not lose the subject.
    parent_master_text = " ".join(
        beat["voice_text"] for beat in synced
    )

    parent_context = build_local_grounding_context(
        parent_master_text,
        story,
    )

    print("\n=== PARENT SEMANTIC SCENE ===")
    print("MASTER:", parent_master_text)
    print("MATCH SCORE:", parent_context["chapter_match_score"])

    for i, beat in enumerate(synced, 1):
        context = parent_context

        print(f"\n=== BEAT {i} ===")
        print("MASTER:", beat["voice_text"])
        print("INHERITED MATCH SCORE:", context["chapter_match_score"])

        print("CHAPTERS:")
        for chapter in context["chapters"]:
            print(
                "-",
                chapter.get("title"),
                "|",
                chapter.get("primary_subject"),
                "|",
                chapter.get("location"),
            )

        print("ENTITIES:")
        for entity in context["entities"]:
            print(
                "-",
                entity.get("canonical_subject"),
                "|",
                entity.get("location"),
            )

    print("\nLOCAL GROUNDING TEST COMPLETE")
