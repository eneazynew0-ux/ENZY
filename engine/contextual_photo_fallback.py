"""
Verified contextual cutaways after unsuccessful literal media search.
Original narration and beat timing are never changed.
"""

from engine.entity_search_canonicalizer import canonicalize_entity_for_search
from engine.multi_query_visual_pipeline import run_multi_query_visual_pipeline


def _norm(value):
    return " ".join(str(value or "").casefold().split())


def search_contextual_photo(
    beat, scene_entities, excluded_subjects,
    model, tokenizer, output_dir, limit_per_provider=10,
):
    voice = _norm(beat.get("voice_text"))
    if len(voice) < 40 or model is None or tokenizer is None:
        return {"status": "UNAVAILABLE", "reason": "Insufficient context"}

    excluded = {_norm(value) for value in excluded_subjects if value}
    candidates = {}

    for entity in scene_entities or []:
        subject = _norm(entity.get("canonical_subject"))
        if not subject or subject in excluded:
            continue
        if str(entity.get("confidence", "")).upper() != "HIGH":
            continue

        evidence = entity.get("evidence") or []
        supporting = [
            quote for quote in evidence
            if isinstance(quote, str) and voice in _norm(quote)
        ]
        if supporting:
            candidates[subject] = (entity, supporting)

    if len(candidates) != 1:
        return {
            "status": "UNAVAILABLE",
            "reason": "No unique related subject with narration evidence",
            "candidate_count": len(candidates),
        }

    entity, evidence = next(iter(candidates.values()))
    identity = canonicalize_entity_for_search(entity, model, tokenizer)
    if not identity or identity.get("_canonicalization_status") != "OK":
        return {"status": "UNAVAILABLE", "reason": "Identity normalization failed"}

    subject = identity["canonical_subject"]
    queries = [subject]
    kind = str(identity.get("subject_type") or "").strip()
    if kind:
        queries.append(subject + " " + kind)
    for alias in (identity.get("aliases_or_descriptions") or [])[:3]:
        alias = " ".join(str(alias or "").split())
        if alias and len(alias.split()) <= 16:
            queries.append(alias)
    queries = list(dict.fromkeys(queries))
    location = str(identity.get("location") or "").strip()
    if location and location.casefold() not in {"unknown", "none", "n/a"}:
        queries.append(subject + " " + location)

    subject_type = str(identity.get("subject_type") or "").strip()
    target = (
        "A documentary photograph of the actual physical "
        + subject_type + ": " + subject
        + ". Show the object itself, not a flag, logo, emblem or drawing."
    )
    if "sculpt" in subject_type.casefold() or "carving" in subject_type.casefold():
        target += (
            " The subject must be a carved sculpture or artifact. "
            "Reject living animals, including live birds."
        )
    search = run_multi_query_visual_pipeline(
        queries, target,
        limit_per_provider=limit_per_provider,
        output_dir=output_dir,
        factual=True,
        visual_entity=identity,
    )

    best = search.get("best")
    if not isinstance(best, dict) or not isinstance(best.get("asset"), dict):
        return {
            "status": "NO_MATCH",
            "reason": "No verified contextual photo",
            "search": search,
        }

    # Carry this distinction through adapters and timeline assets.
    asset = dict(best["asset"])
    asset["representation"] = {
        "mode": "CONTEXTUAL_CUTAWAY",
        "depicts_original_event": False,
        "original_voice_text": beat.get("voice_text"),
        "original_visual_target": beat.get("visual_intent"),
        "contextual_subject": subject,
        "narration_evidence": evidence,
    }
    search = dict(search)
    search["best"] = {**best, "asset": asset}

    return {
        "status": "MATCH",
        "photo_result": {
            "status": "SEARCHED",
            "plan": {
                "beat": beat,
                "factual_search": True,
                "search_entity": identity,
            },
            "search": search,
        },
    }
