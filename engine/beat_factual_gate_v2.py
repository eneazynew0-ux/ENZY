import re


def norm(text):
    text = str(text or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def all_generated_text(beat):
    parts = [
        beat.get("visual_intent", ""),
        beat.get("edit", ""),
    ]

    # Exclusions are not positive claims about the scene.
    for key in ("search_queries", "requirements"):
        parts.extend(beat.get(key, []) or [])

    return " ".join(str(x) for x in parts)


def contains_any(text, variants):
    text = norm(text)
    return any(norm(v) in text for v in variants)


def check_beat(beat, master_text, grounding):
    generated = norm(all_generated_text(beat))
    master = norm(master_text)

    grounding_text = norm(
        str(grounding.get("master_text", ""))
        + " "
        + str(grounding.get("chapters", ""))
        + " "
        + str(grounding.get("entities", ""))
    )

    issues = []

    # Roles / professions must be explicitly grounded.
    role_terms = {
        "farmer": ["farmer", "farmers"],
        "archaeologist": ["archaeologist", "archaeologists"],
        "worker": ["worker", "workers"],
        "soldier": ["soldier", "soldiers"],
        "officer": ["officer", "officers"],
        "priest": ["priest", "priests"],
        "merchant": ["merchant", "merchants"],
    }

    for role, variants in role_terms.items():
        if not contains_any(generated, variants):
            continue

        # A role is allowed only if it appears in the MASTER or
        # explicitly in the local grounding context.
        if not contains_any(master, variants) and not contains_any(
            grounding_text, variants
        ):
            issues.append({
                "type": "UNSUPPORTED_ROLE",
                "severity": "HIGH",
                "term": role,
                "detail": f"Generated role {role!r} is not supported by MASTER or local grounding.",
            })

    # Reactions / emotions are dangerous when narration does not state them.
    reaction_terms = {
        "recognition": [
            "recognition",
            "realization",
            "realized",
            "surprise",
            "shocked",
            "astonished",
        ],
        "fear": ["fear", "afraid", "terrified", "frightened"],
        "anger": ["anger", "angry", "furious"],
        "grief": ["grief", "grieving", "mourning"],
    }

    for reaction, variants in reaction_terms.items():
        if not contains_any(generated, variants):
            continue

        if not contains_any(master, variants):
            issues.append({
                "type": "UNSUPPORTED_REACTION",
                "severity": "HIGH",
                "term": reaction,
                "detail": (
                    f"Generated reaction {reaction!r} is not explicitly "
                    "supported by MASTER narration."
                ),
            })

    # Specific locations / identities must be grounded.
    # Grounding may be Russian while generated beat text is English.
    # Use canonical bilingual aliases and whole-word matching.
    location_aliases = {
        "central nigeria": [
            "central nigeria",
            "центральная нигерия",
        ],
        "nigeria": [
            "nigeria",
            "нигерия",
        ],
        "nok": [
            "nok",
            "нок",
        ],
        "jackfruit": [
            "jackfruit",
            "джекфрут",
        ],
        "china": [
            "china",
            "китай",
        ],
        "chinese": [
            "chinese",
            "китайский",
            "китайская",
            "китайское",
        ],
    }

    def contains_term(text, term):
        text = norm(text)
        term = norm(term)

        if " " in term:
            return term in text

        return re.search(
            r"(?<![a-zа-я])" + re.escape(term) + r"(?![a-zа-я])",
            text,
            flags=re.IGNORECASE,
        ) is not None

    for canonical, aliases in location_aliases.items():
        generated_has = any(
            contains_term(generated, alias)
            for alias in aliases
        )

        if not generated_has:
            continue

        grounded_has = any(
            contains_term(master, alias)
            or contains_term(grounding_text, alias)
            for alias in aliases
        )

        if not grounded_has:
            issues.append({
                "type": "UNSUPPORTED_LOCATION_OR_IDENTITY",
                "severity": "HIGH",
                "term": canonical,
                "detail": (
                    f"Generated concrete detail {canonical!r} is not "
                    "supported by MASTER or local grounding."
                ),
            })

    return issues


if __name__ == "__main__":
    print("BEAT FACTUAL GATE V2 MODULE: OK")
