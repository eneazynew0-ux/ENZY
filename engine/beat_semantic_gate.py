import json
from mlx_lm import generate
from engine.beat_grounding import phrase_present
from engine.beat_visual_contract import check_artifact_visual_contract


def _reported_claim_visualized_as_fact(beat, preceding_text, positive):
    """Catch a quoted/disputed proposition split across adjacent beats."""
    import re

    narration_context = " ".join(
        [str(preceding_text or "")[-600:], str(beat.get("voice_text") or "")]
    ).casefold()
    reporting_frames = (
        r"учебник\w*\s+(?:скажет|говорит|утвержда)",
        r"(?:утверждал|утверждали|считал|считали|предположил|версия|миф)",
        r"\b(?:textbook|source)\s+(?:says|claims|claimed)\b",
        r"\b(?:claimed|argued|believed|supposed|myth|theory)\b",
    )
    assertion_markers = (
        r"\bno cities\b",
        r"\bno engineering\b",
        r"\bno written (?:culture|language|symbols?)\b",
        r"\b(?:empty|blank|uninhabited) (?:map|regions?|land|africa)\b",
        r"\babsence of (?:cities|engineering|culture|development)\b",
        r"нет городов|без городов|не знала городов",
        r"нет инженер|без инженер|не знала инженер",
        r"нет письмен|без письмен|не знала письмен",
        r"пуст\w* (?:карт|пространств|земл)",
        r"отсутств\w* (?:город|инженер|культур|развит)",
    )

    has_reporting_frame = any(
        re.search(pattern, narration_context)
        for pattern in reporting_frames
    )
    asserts_proposition = any(
        re.search(pattern, positive)
        for pattern in assertion_markers
    )

    if not (has_reporting_frame and asserts_proposition):
        return None

    return {
        "type": "REPORTED_CLAIM_VISUALIZED_AS_FACT",
        "severity": "HIGH",
        "detail": (
            "Visual plan presents a reported or disputed claim as factual "
            "reality; use source/context imagery without depicting the claim as true."
        ),
    }


def check_beat_semantics(beat, grounding, preceding_text, model, tokenizer):
    import re
    positive = " ".join(
        [str(beat.get("visual_intent") or ""), str(beat.get("edit") or "")]
        + [
            str(value)
            for key in ("search_queries", "requirements")
            for value in (beat.get(key) or [])
        ]
    ).casefold()
    # Earlier words resolve identity, but cannot license current staging.
    narration = str(beat.get("voice_text") or "").casefold()
    future_issues = [
        {"type": "UNSUPPORTED_ENTITY_REVEAL", "severity": "HIGH",
         "detail": "Visual introduces an identity absent from available narration: "
                   + str(entity.get("canonical_subject", ""))}
        for entity in grounding.get("withheld_entities", [])
        if any(phrase_present(term, positive) for term in entity.get("terms", []))
    ]
    if future_issues:
        return future_issues
    contract_issues = check_artifact_visual_contract(beat, grounding)
    if contract_issues:
        return contract_issues

    details = (
        ("furniture", r"\bfurniture\b", r"furniture|мебел"),
        ("desk", r"\bdesk\b", r"\bdesk\b|письменн\w* стол|рабоч\w* стол"),
        ("window", r"\bwindows?\b", r"\bwindows?\b|окн|окон"),
        ("countryside view", r"\bcountryside\b", r"countryside|сельск\w* местност"),
        ("climate control", r"\bclimate[- ]controlled\b", r"climate[- ]control|климат[- ]контрол"),
        ("sealed case", r"\bsealed case\b", r"sealed case|герметичн\w* (футляр|витрин|контейнер)"),
    )
    unsupported = [
        {
            "type": "UNSUPPORTED_STAGING_DETAIL",
            "severity": "HIGH",
            "detail": "Visual plan requires " + label
                      + " without support in narration.",
        }
        for label, generated_pattern, evidence_pattern in details
        if re.search(generated_pattern, positive)
        and not re.search(evidence_pattern, narration)
    ]
    if unsupported:
        return unsupported

    claim_issue = _reported_claim_visualized_as_fact(
        beat,
        preceding_text,
        positive,
    )
    if claim_issue:
        return [claim_issue]

    payload = {
        "narration": beat.get("voice_text", ""),
        "preceding_narration_for_referents_only": preceding_text,
        "grounded_entities": grounding.get("entities", []),
        "proposed_visual": {
            key: beat.get(key)
            for key in (
                "visual_intent", "search_queries",
                "requirements", "edit",
            )
        },
        "negative_constraints": beat.get("avoid", []),
    }
    prompt = """
You audit the factual meaning of a documentary visual search plan.
The narration is immutable. Do not rewrite it.

Reject the plan if it:
- changes an artifact or other nonhuman referent into a person;
- changes the narrated object, action, or physical geometry;
- invents a year, century, date, location, event or physical interaction;
- requires invented furniture, scenery, glass cases, climate control,
  storage conditions or other historical staging not supported by narration;
- requests visible captions, labels, arrows, logos or written overlays;
- depicts an excluded, negated or hypothetical event as a real event.

Preceding narration and grounded entities may resolve an existing
pronoun or identify its subject. They do not authorize new actions
or reconstruction of historical circumstances.
A photograph of the identified artifact is acceptable as a contextual
cutaway. A fabricated scene placing it in a specific historical room
with invented surroundings is not.
Camera framing and gentle editing motion are allowed.
Negative constraints describe what must NOT appear: do not treat
their words as requested objects or events.

Check ALL proposed_visual fields, including search queries.
Return only JSON:
{"approved": true, "issues": []}
or
{"approved": false, "issues": ["short concrete unsupported claim"]}
INPUT:
""" + json.dumps(payload, ensure_ascii=False)

    try:
        formatted = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )
        raw = generate(
            model, tokenizer, prompt=formatted,
            max_tokens=450, verbose=False,
        ).strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Root must be an object")
        issues = parsed.get("issues")
        if (
            parsed.get("approved") is True
            and isinstance(issues, list)
            and not issues
        ):
            return []
        if (
            parsed.get("approved") is not False
            or not isinstance(issues, list)
            or not issues
            or any(not isinstance(x, str) or not x.strip() for x in issues)
        ):
            raise ValueError("Invalid audit contract")
        return [{
            "type": "UNSUPPORTED_VISUAL_MEANING",
            "severity": "HIGH",
            "detail": item,
        } for item in issues]
    except Exception as exc:
        return [{
            "type": "SEMANTIC_AUDIT_UNAVAILABLE",
            "severity": "HIGH",
            "detail": str(exc),
        }]
