from engine.beat_entity_resolver import resolve_beat_entities_hybrid
from engine.beat_visual_subject import resolve_visual_subject
from engine.query_expander import expand_queries
from engine.entity_search_canonicalizer import canonicalize_entity_for_search
from engine.search_contract import bound_contextual_identity, visual_search_target


def _resolved_entity(entity_result):
    if entity_result.get("status") != "RESOLVED":
        return None

    entities = entity_result.get("entities") or []

    if len(entities) != 1:
        return None

    return entities[0].get("entity")


def build_beat_search_plan(
    beat,
    scene_entities,
    model=None,
    tokenizer=None,
    verified_years=None,
):
    """
    Build the factual/visual search plan for one beat.

    Pipeline:
      Beat
        -> contextual entity resolution
        -> visual-subject decision
        -> safe query expansion

    This function does NOT search the internet.
    It only produces the grounded search plan.
    """

    bound_identity = bound_contextual_identity(beat, scene_entities)
    if bound_identity is not None:
        return {
            "beat": beat, "entity_resolution": {"status": "CONTRACT_BOUND"},
            "contextual_entity": None,
            "visual_subject": {"use_entity_for_search": True, "selection_method": "APPROVED_VISUAL_CONTRACT"},
            "visual_entity": bound_identity, "search_entity": bound_identity,
            "factual_search": True,
            "queries": {"all": list(beat["search_queries"])},
        }
    entity_result = resolve_beat_entities_hybrid(
        beat,
        scene_entities,
        model=model,
        tokenizer=tokenizer,
    )

    contextual_entity = _resolved_entity(
        entity_result
    )

    if contextual_entity:
        visual_subject = resolve_visual_subject(
            beat,
            contextual_entity,
            model=model,
            tokenizer=tokenizer,
        )
    else:
        visual_subject = {
            "use_entity_for_search": False,
            "confidence": "HIGH",
            "reason": "NO_RESOLVED_ENTITY",
        }

    if visual_subject.get(
        "use_entity_for_search"
    ) is True:
        visual_entity = contextual_entity
    else:
        visual_entity = None

    # If the contextual subject is not the visible subject,
    # evaluate remaining grounded candidates instead of stopping there.
    if (
        visual_entity is None
        and model is not None
        and tokenizer is not None
    ):
        alternatives = []
        for candidate_entity in scene_entities or []:
            if candidate_entity == contextual_entity:
                continue
            decision = resolve_visual_subject(
                beat,
                candidate_entity,
                model=model,
                tokenizer=tokenizer,
            )
            if (
                decision.get("use_entity_for_search") is True
                and str(decision.get("confidence", "")).upper() == "HIGH"
            ):
                alternatives.append((candidate_entity, decision))

        # Ambiguous alternatives remain blocked.
        if len(alternatives) == 1:
            visual_entity, visual_subject = alternatives[0]
            visual_subject = {
                **visual_subject,
                "selection_method": "UNIQUE_GROUNDED_ALTERNATIVE",
            }

    search_entity = None

    if visual_entity:
        if model is None or tokenizer is None:
            raise ValueError(
                "visual entity canonicalization requires "
                "shared model and tokenizer"
            )

        candidate = canonicalize_entity_for_search(
            visual_entity,
            model,
            tokenizer,
        )

        if candidate.get(
            "_canonicalization_status"
        ) == "OK":
            search_entity = candidate

    expanded = expand_queries(
        beat,
        visual_entity=search_entity,
        verified_years=verified_years,
    )

    # Factual mode is fail-closed. If the beat requires a
    # factual visual entity but that identity cannot be
    # safely canonicalized for search, do not silently
    # downgrade it to generic B-roll.
    required_identity = (
        beat.get("requires_identity_gate") is True
        or beat.get("identity_sensitive") is True
        or beat.get("requires_identity_verification") is True
        or any(
            phase.get("requires_identity_verification") is True
            or (phase.get("execution_request") or {}).get(
                "requires_identity_gate"
            ) is True
            or (phase.get("execution_request") or {}).get(
                "requires_identity_verification"
            ) is True
            for phase in (beat.get("retention_phases") or [])
        )
    )
    factual_search = bool(visual_entity) or required_identity

    return {
        "beat": beat,
        "entity_resolution": entity_result,
        "contextual_entity": contextual_entity,
        "visual_subject": visual_subject,
        "visual_entity": visual_entity,
        "search_entity": search_entity,
        "factual_search": factual_search,
        "queries": expanded,
    }


def run_beat_visual_search(
    beat,
    scene_entities,
    target,
    model=None,
    tokenizer=None,
    verified_years=None,
    limit_per_provider=10,
    output_dir="data/beat_visual_search",
):
    """
    Full photo-search path for one beat.

    Uses the already-proven multi-query visual pipeline.
    """

    target = visual_search_target(beat, target)
    plan = build_beat_search_plan(
        beat,
        scene_entities,
        model=model,
        tokenizer=tokenizer,
        verified_years=verified_years,
    )

    queries = plan["queries"]["all"]

    if (
        plan["factual_search"]
        and not plan["search_entity"]
    ):
        return {
            "plan": plan,
            "search": None,
            "status": "FACTUAL_IDENTITY_UNAVAILABLE",
        }

    if not queries:
        return {
            "plan": plan,
            "search": None,
            "status": "NO_QUERIES",
        }

    # Import here so building/testing search plans does not
    # unnecessarily initialize visual-search dependencies.
    from engine.multi_query_visual_pipeline import (
        run_multi_query_visual_pipeline,
    )

    search = run_multi_query_visual_pipeline(
        queries,
        target,
        limit_per_provider=limit_per_provider,
        output_dir=output_dir,
        factual=plan["factual_search"],
        visual_entity=plan["search_entity"],
    )

    if search.get("best") is None:
        status = "NO_SUITABLE_ASSET"
        reason = (
            "No candidate passed factual identity, export rights, "
            "media quality, download, and visual relevance gates"
        )
    else:
        status = "SEARCHED"
        reason = "At least one suitable visual asset was found"

    return {
        "plan": plan,
        "search": search,
        "status": status,
        "reason": reason,
    }
