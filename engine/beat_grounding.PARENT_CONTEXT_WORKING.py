import json
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

        if any(
            subject and (
                subject in candidate
                or candidate in subject
            )
            for candidate in selected_subjects
        ):
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
