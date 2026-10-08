import re
import copy


def sanitize_beat(beat, issues):
    result = copy.deepcopy(beat)

    bad_terms = {
        str(issue.get("term", "")).lower()
        for issue in issues
        if issue.get("severity") == "HIGH"
    }

    # Remove unsupported role/person identity from generated fields.
    role_terms = {
        "farmer",
        "archaeologist",
        "worker",
        "soldier",
        "officer",
        "priest",
        "merchant",
    }

    reaction_terms = {
        "recognition",
        "realization",
        "realized",
        "surprise",
        "shocked",
        "astonished",
        "fear",
        "afraid",
        "terrified",
        "frightened",
        "anger",
        "angry",
        "furious",
        "grief",
        "grieving",
        "mourning",
    }

    unsupported_roles = bad_terms & role_terms
    unsupported_reactions = bad_terms & reaction_terms

    # Expand factual-gate reaction categories into every lexical
    # variant that can trigger the same HIGH issue.
    reaction_variants = {
        "recognition": {
            "recognition",
            "realization",
            "realized",
            "surprise",
            "shocked",
            "astonished",
        },
        "fear": {
            "fear",
            "afraid",
            "terrified",
            "frightened",
        },
        "anger": {
            "anger",
            "angry",
            "furious",
        },
        "grief": {
            "grief",
            "grieving",
            "mourning",
        },
    }

    expanded_reactions = set()
    for category in unsupported_reactions:
        expanded_reactions.update(
            reaction_variants.get(category, {category})
        )
    unsupported_reactions = expanded_reactions

    # Remove only unsupported role words from generated prose.
    for key in ("visual_intent", "edit"):
        text = str(result.get(key, ""))

        for term in unsupported_roles:
            text = text.replace(term, "")
            text = text.replace(term.capitalize(), "")

        # Remove common unsupported reaction phrases as a whole.
        reaction_patterns = [
            r"\s*,?\s*suggesting\s+(recognition|realization|surprise|shock|fear|anger|grief)(?:\s+and\s+\w+)*",
            r"\s*,?\s*showing\s+(recognition|realization|surprise|shock|fear|anger|grief)",
            r"\s*,?\s*with\s+(recognition|realization|surprise|shock|fear|anger|grief)",
            r"\s*,?\s*expressing\s+(recognition|realization|surprise|shock|fear|anger|grief)",
        ]

        for pattern in reaction_patterns:
            text = re.sub(
                pattern,
                "",
                text,
                flags=re.IGNORECASE,
            )

        for term in unsupported_reactions:
            text = re.sub(
                r"\b" + re.escape(term) + r"\b",
                "",
                text,
                flags=re.IGNORECASE,
            )

        result[key] = " ".join(text.split()).strip(" ,.;")

    # Unsupported location / identity details detected by the factual gate.
    unsupported_locations = {
        str(issue.get("term", "")).lower()
        for issue in issues
        if issue.get("severity") == "HIGH"
        and issue.get("type") == "UNSUPPORTED_LOCATION_OR_IDENTITY"
    }

    # Remove contaminated search queries instead of partially
    # rewriting them into potentially misleading searches.
    cleaned_queries = []

    for query in result.get("search_queries", []) or []:
        q = str(query)
        q_lower = q.lower()

        if any(term in q_lower for term in unsupported_roles):
            continue

        if any(term in q_lower for term in unsupported_reactions):
            continue

        if any(term in q_lower for term in unsupported_locations):
            continue

        cleaned_queries.append(q)

    result["search_queries"] = cleaned_queries

    # Final factual cleanup across every generated textual field.
    reaction_words = set(unsupported_reactions)
    role_words = set(unsupported_roles)

    for key in ("visual_intent", "edit"):
        text = str(result.get(key, ""))

        for term in reaction_words | role_words:
            text = re.sub(
                r"\b" + re.escape(term) + r"\b",
                "",
                text,
                flags=re.IGNORECASE,
            )

        # Remove unsupported geographic/identity phrases first,
        # then remove individual unsupported location terms.
        for term in sorted(unsupported_locations, key=len, reverse=True):
            text = re.sub(
                r"\b(?:in|from|near|at)\s+" + re.escape(term) + r"\b",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"\b" + re.escape(term) + r"\b",
                "",
                text,
                flags=re.IGNORECASE,
            )

        # Clean common geographic fragments left after removing
        # a compound location such as "in central Nigeria".
        text = re.sub(
            r"\bin\s+central\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\bin\s+a\s+rural\s+setting\s+in\s+central\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        result[key] = " ".join(text.split()).strip(" ,.;")

    for key in ("requirements", "avoid"):
        values = []

        for value in result.get(key, []) or []:
            value_str = str(value)
            value_lower = value_str.lower()

            if any(term in value_lower for term in reaction_words):
                continue

            if any(term in value_lower for term in role_words):
                continue

            if any(term in value_lower for term in unsupported_locations):
                continue

            values.append(value_str)

        result[key] = values

        result[key] = values

    return result


if __name__ == "__main__":
    print("BEAT FACTUAL SANITIZER MODULE: OK")
