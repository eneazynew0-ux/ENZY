import re


YEAR_RE = re.compile(r"\b(?:18|19|20)\d{2}\b", re.I)


def _clean(text):
    value = " ".join(str(text or "").strip().split())
    if value.casefold() in {"unknown", "none", "null", "n/a", "неизвестно"}:
        return ""
    return value


def _search_query(text):
    value = _clean(text)
    # Do not truncate descriptions: truncation can lose factual identity.
    if len(value.split()) > 16:
        return ""
    return value


def _dedupe(items):
    result = []
    seen = set()

    for item in items:
        item = _clean(item)
        if not item:
            continue

        key = item.casefold()
        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def _strip_unverified_years(query, verified_years=None):
    verified_years = {
        str(year)
        for year in (verified_years or [])
    }

    def replace(match):
        year = match.group(0)
        return year if year in verified_years else ""

    return _clean(YEAR_RE.sub(replace, query))


def expand_queries(
    beat,
    visual_entity=None,
    verified_years=None,
):
    """
    Expand search queries for one visual beat.

    visual_entity MUST already be approved by the
    Beat Visual Subject Resolver.

    Never pass a scene-level/story entity here merely
    because it belongs to the surrounding narrative.
    """

    verified_years = verified_years or []

    original_queries = [
        _strip_unverified_years(q, verified_years)
        for q in beat.get("search_queries", [])
        if _clean(q)
    ]

    original_queries = _dedupe(original_queries)

    visual_intent = _strip_unverified_years(
        beat.get("visual_intent", ""),
        verified_years,
    )

    requirements = [
        _strip_unverified_years(x, verified_years)
        for x in beat.get("requirements", [])
        if _clean(x)
    ]
    requirements = _dedupe(requirements)

    exact = []
    broad = list(original_queries)
    visual = []

    if _search_query(visual_intent):
        visual.append(visual_intent)

    for requirement in requirements[:3]:
        if re.match(r"^date:", requirement, re.I):
            continue
        query = re.sub(
            r"^(?:location|setting):\s*", "", requirement, flags=re.I,
        )
        if _search_query(query):
            visual.append(query)

    if visual_entity:
        canonical = _clean(
            visual_entity.get("canonical_subject")
            or visual_entity.get("exact_subject")
        )

        location = _clean(
            visual_entity.get("location")
        )

        aliases = _dedupe(
            visual_entity.get(
                "aliases_or_descriptions",
                [],
            )
        )

        # Entity-specific queries are added only because
        # an upstream visual-subject decision approved it.
        if canonical:
            exact.append(canonical)

        if canonical and location:
            exact.append(
                f"{canonical} {location}"
            )

        for alias in aliases[:3]:
            exact.append(alias)

        # Preserve strong beat-specific stock queries and
        # optionally ground a small number with the entity.
        if canonical:
            for query in original_queries[:2]:
                if canonical.casefold() not in query.casefold():
                    broad.append(
                        f"{canonical} {query}"
                    )

    exact = _dedupe(_search_query(q) for q in exact)
    broad = _dedupe(_search_query(q) for q in broad)
    visual = _dedupe(_search_query(q) for q in visual)

    all_queries = _dedupe(
        exact + broad + visual
    )

    return {
        "exact": exact,
        "broad": broad,
        "visual": visual,
        "all": all_queries,
        "used_visual_entity": bool(visual_entity),
    }


if __name__ == "__main__":
    harare_beat = {
        "visual_intent": (
            "A military guard standing at the entrance "
            "of Harare Airport, April 15th, this year."
        ),
        "search_queries": [
            "military guard at Harare Airport April 15 2024",
            "real footage military guard at airport Harare",
            "aerial view of Harare Airport military presence",
        ],
        "requirements": [
            "military guard present",
            "location: Harare Airport",
        ],
    }

    harare = expand_queries(
        harare_beat,
        visual_entity=None,
    )

    joined = " ".join(harare["all"]).casefold()

    if "2024" in joined:
        raise SystemExit(
            "FAILED: unverified year survived"
        )

    if "каменная птица" in joined:
        raise SystemExit(
            "FAILED: story entity contaminated Harare query"
        )

    if harare["used_visual_entity"]:
        raise SystemExit(
            "FAILED: Harare incorrectly used entity"
        )

    nabta_beat = {
        "visual_intent": (
            "Ancient stone circle in an open desert "
            "aligned with the solstice sun."
        ),
        "search_queries": [
            "ancient stone circle desert solstice",
            "prehistoric stone circle desert",
        ],
        "requirements": [
            "real archaeological stone circle",
            "open arid desert",
        ],
    }

    nabta_entity = {
        "canonical_subject": "Nabta Playa",
        "location": "southern Egypt",
        "aliases_or_descriptions": [
            "Nabta Playa stone circle",
            "Nabta Playa megaliths",
        ],
    }

    nabta = expand_queries(
        nabta_beat,
        visual_entity=nabta_entity,
    )

    nabta_joined = " ".join(nabta["all"]).casefold()

    if "nabta playa" not in nabta_joined:
        raise SystemExit(
            "FAILED: approved visual entity missing"
        )

    if not nabta["used_visual_entity"]:
        raise SystemExit(
            "FAILED: Nabta entity not marked as used"
        )

    print("HARARE QUERIES:")
    for q in harare["all"]:
        print(" -", q)

    print()
    print("NABTA QUERIES:")
    for q in nabta["all"]:
        print(" -", q)

    print()
    print("QUERY EXPANDER V2 BASIC CONTROL PASSED")
