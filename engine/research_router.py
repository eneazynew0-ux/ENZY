FACTUAL_TRIGGERS = {
    "artifact",
    "archaeological site",
    "historical event",
    "historical person",
    "specific place",
    "institution",
    "civilization",
    "culture",
    "monument",
}

def route_scene(fact):
    confidence = str(fact.get("confidence", "")).upper()
    subject_type = str(fact.get("subject_type", "")).lower()
    exact_subject = str(fact.get("exact_subject", "")).strip().upper()
    factual_priority = bool(fact.get("factual_priority", False))

    needs_research = (
        factual_priority
        or confidence in {"LOW", "MEDIUM"}
        or exact_subject in {"", "UNKNOWN"}
        or subject_type in FACTUAL_TRIGGERS
    )

    return "FACTUAL_RESEARCH" if needs_research else "DIRECT_SEARCH"


def route_facts(facts):
    return [
        {
            "sentence_id": fact["sentence_id"],
            "route": route_scene(fact),
            "exact_subject": fact.get("exact_subject", "UNKNOWN"),
            "confidence": fact.get("confidence", "UNKNOWN"),
        }
        for fact in facts
    ]
