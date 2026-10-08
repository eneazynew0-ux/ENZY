from copy import deepcopy


VIDEO_FIRST = {
    "FACTUAL_VIDEO",
    "REAL_VIDEO",
    "ILLUSTRATIVE_VIDEO",
}

SPECIAL_STATIC = {
    "FACTUAL_STILL",
    "DOCUMENT",
    "MAP",
    "ARCHIVE",
}


def _text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(x) for x in value)
    return str(value)


def has_high_confidence_entity(grounding_context):
    entities = (grounding_context or {}).get("entities", [])

    return any(
        str(entity.get("confidence", "")).upper() == "HIGH"
        and bool(entity.get("canonical_subject"))
        for entity in entities
    )


def classify_visual_mode(beat, grounding_context=None):
    voice = _text(beat.get("voice_text")).lower()
    intent = _text(beat.get("visual_intent")).lower()
    requirements = _text(beat.get("requirements")).lower()

    exact_entity = has_high_confidence_entity(grounding_context)

    # MAP only when the requested visual itself is fundamentally a map.
    explicit_map = (
        intent.startswith("a map ")
        or intent.startswith("map ")
        or "map of africa highlighting" in intent
        or "geographic context on a real map" in requirements
    )

    # DOCUMENT only when a physical/written document is the core visual.
    explicit_document = any(x in intent for x in (
        "textbook open",
        "open textbook",
        "manuscript",
        "document page",
        "historical document",
    ))

    # ARCHIVE only when archive/museum/colonial material itself is the subject.
    explicit_archive = any(x in intent for x in (
        "museum storage",
        "archival photograph",
        "historical photograph",
        "colonial-era furniture",
        "colonial administrative",
    ))

    # Exact static artifact/detail situations where motion would usually
    # require inventing an event instead of documenting the real object.
    artifact_static = any(x in intent for x in (
        "terracotta head lying",
        "hand gently holding the terracotta head",
        "stone sculpture shaped like a bird",
        "artifact close-up",
    ))

    if explicit_map:
        return "MAP"

    if explicit_document:
        return "DOCUMENT"

    if explicit_archive:
        return "ARCHIVE"

    if exact_entity and artifact_static:
        return "FACTUAL_STILL"

    # A grounded real place/event/object should FIRST search for exact
    # identity-matched real video. The identity gate still applies.
    if exact_entity:
        return "FACTUAL_VIDEO"

    action_signals = (
        "guard",
        "airport",
        "walking",
        "pilgrims",
        "kneeling",
        "boats",
        "boat",
        "vehicle",
        "vehicles",
        "excavation",
        "landscape",
        "savanna",
        "desert",
    )

    combined = " ".join((voice, intent, requirements))

    if any(signal in combined for signal in action_signals):
        return "REAL_VIDEO"

    return "ILLUSTRATIVE_VIDEO"


def plan_beat(beat, grounding_context=None):
    result = deepcopy(beat)

    mode = classify_visual_mode(
        beat,
        grounding_context=grounding_context,
    )

    result["documentary_mode"] = mode
    result["prefer_motion"] = mode in VIDEO_FIRST
    result["identity_sensitive"] = has_high_confidence_entity(
        grounding_context
    )

    # Important: identity-sensitive video must still pass exact identity
    # verification. Generic B-roll is not an acceptable substitute.
    result["requires_identity_gate"] = bool(
        result["identity_sensitive"]
    )

    return result


def plan_sequence(scene_results):
    output = []

    for scene in scene_results:
        grounding = scene.get("grounding_context", {})

        for beat in scene.get("beats", []):
            output.append(
                plan_beat(
                    beat,
                    grounding_context=grounding,
                )
            )

    return output
