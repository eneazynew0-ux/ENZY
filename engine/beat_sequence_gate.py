"""Sequence-level checks that compare adjacent documentary beats."""


def check_adjacent_visual_repetition(previous, current):
    """Reject an exact adjacent visual repeat without explicit continuity."""
    if not previous:
        return []

    def normalize(value):
        return " ".join(str(value or "").casefold().split())

    previous_intent = normalize(previous.get("visual_intent"))
    current_intent = normalize(current.get("visual_intent"))
    previous_queries = tuple(
        sorted(normalize(value) for value in previous.get("search_queries", []))
    )
    current_queries = tuple(
        sorted(normalize(value) for value in current.get("search_queries", []))
    )
    repeated = bool(
        previous_intent
        and previous_intent == current_intent
        and previous_queries
        and previous_queries == current_queries
    )
    continuity = normalize(current.get("edit"))
    explicit_continuity = any(
        marker in continuity
        for marker in (
            "continue the same shot",
            "continuous shot",
            "hold the same shot",
            "продолжить тот же кадр",
            "непрерывный кадр",
        )
    )

    if not repeated or explicit_continuity:
        return []

    return [{
        "type": "ADJACENT_VISUAL_REPETITION",
        "severity": "HIGH",
        "detail": (
            "Adjacent beat repeats the same visual intent and search queries. "
            "Choose a different grounded visual role or explicitly justify a continuous shot."
        ),
        "previous_visual_intent": previous.get("visual_intent"),
        "previous_search_queries": previous.get("search_queries", []),
    }]
