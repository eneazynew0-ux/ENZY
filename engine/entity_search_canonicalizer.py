import json

from mlx_lm import generate


def canonicalize_entity_for_search(
    entity,
    model,
    tokenizer,
):
    """
    Convert an already-grounded factual entity into a conservative
    English search identity.

    This function does NOT discover a new entity.
    It may only translate/normalize information already present
    in the supplied entity.
    """

    if not entity:
        return None

    researched = entity.get("researched_search_identity") or {}
    if (
        researched.get("status") == "VERIFIED"
        and researched.get("canonical_subject")
        and researched.get("source_url")
        and researched.get("basis")
    ):
        return {
            "canonical_subject": researched["canonical_subject"],
            "subject_type": researched.get("subject_type", ""),
            "location": researched.get("location", ""),
            "aliases_or_descriptions": researched.get("aliases", []),
            "confidence": entity.get("confidence"),
            "_canonicalization_status": "OK",
            "_source_canonical_subject": entity.get("canonical_subject"),
            "_source_evidence": entity.get("evidence", []),
            "_identity_research": dict(researched),
        }

    payload = {
        "canonical_subject": entity.get(
            "canonical_subject", ""
        ),
        "subject_type": entity.get(
            "subject_type", ""
        ),
        "location": entity.get(
            "location", ""
        ),
        "aliases_or_descriptions": entity.get(
            "aliases_or_descriptions", []
        ),
        "evidence": entity.get("evidence", []),
    }

    prompt = """
You normalize ONE already-resolved factual documentary entity
for English-language media search.

Your job is translation and conservative normalization ONLY.

Rules:
- Do NOT discover or invent a different entity.
- Preserve the exact factual identity.
- Read evidence together with the name, aliases and location.
- If the source name is generic but the supplied context identifies
  its country, site or culture, include a supported qualifier in the
  canonical search name. Do not reduce a specific artifact to a
  generic object class.
- Use a conservative descriptive name when an official name is not
  explicitly supported. Never invent an official name.
- Evidence is narration context, not proof about retrieved footage.
- UNKNOWN location must remain UNKNOWN; do not invent a location.
- Translate the canonical subject into the standard English name
  when the supplied entity clearly supports it.
- Translate location into concise English.
- Translate aliases/descriptions into concise English search terms.
- Do not add facts that are absent from the input.
- Do not add dates.
- Do not add speculative aliases.
- Prefer standard proper-name spelling used in English.
- If a phrase is generic, translate it literally and conservatively.
- Return no more than 5 aliases.
- Return ONLY valid JSON.

Required format:
{
  "canonical_subject": "English factual identity",
  "subject_type": "English subject type",
  "location": "English location",
  "aliases_or_descriptions": [
    "English alias"
  ]
}

INPUT:
""" + json.dumps(payload, ensure_ascii=False)

    formatted = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
    )

    raw = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=300,
        verbose=False,
    ).strip()

    try:
        parsed = json.loads(raw)
    except Exception:
        return {
            **entity,
            "_canonicalization_status": "FAILED_INVALID_JSON",
            "_raw": raw,
        }

    canonical = str(
        parsed.get("canonical_subject", "")
    ).strip()

    subject_type = str(
        parsed.get("subject_type", "")
    ).strip()

    location = str(
        parsed.get("location", "")
    ).strip()

    aliases = parsed.get(
        "aliases_or_descriptions",
        [],
    )

    if not isinstance(aliases, list):
        aliases = []

    aliases = [
        str(x).strip()
        for x in aliases[:5]
        if str(x).strip()
    ]

    if not canonical:
        return {
            **entity,
            "_canonicalization_status": "FAILED_EMPTY_CANONICAL",
            "_raw": raw,
        }

    return {
        "canonical_subject": canonical,
        "subject_type": subject_type,
        "location": location,
        "aliases_or_descriptions": aliases,
        "confidence": entity.get("confidence"),
        "_canonicalization_status": "OK",
        "_source_canonical_subject": entity.get(
            "canonical_subject"
        ),
        "_source_evidence": entity.get("evidence", []),
    }


if __name__ == "__main__":
    from mlx_lm import load
    from engine.local_visual_brain import MODEL

    controls = [
        {
            "canonical_subject": "Набта-Плайя",
            "subject_type": "археологическое место",
            "location": (
                "шестиста километров к югу от Каира, "
                "у границы с Суданом"
            ),
            "aliases_or_descriptions": [
                "высохшее русло древнего озера Набта-Плайя",
                "каменный круг",
                "камни в пустыне",
                "каменные плиты",
                "солнцестояние",
            ],
        },
        {
            "canonical_subject": "культура Нок",
            "subject_type": "археологическая культура",
            "location": "центральная Нигерия, деревня Нок",
            "aliases_or_descriptions": [
                "терракотовые фигуры",
                "терракотовая голова из Джемаа",
                "железные печи",
            ],
        },
        {
            "canonical_subject": "церкви Лалибела",
            "subject_type": "археологическое сооружение",
            "location": "северная Эфиопия, горы Ласта",
            "aliases_or_descriptions": [
                "церкви в скале",
                "церкви-обелиски",
            ],
        },
    ]

    model, tokenizer = load(MODEL)

    failures = []

    for entity in controls:
        result = canonicalize_entity_for_search(
            entity,
            model,
            tokenizer,
        )

        print()
        print(
            "SOURCE:",
            entity["canonical_subject"],
        )
        print(
            "STATUS:",
            result.get("_canonicalization_status"),
        )
        print(
            "CANONICAL:",
            result.get("canonical_subject"),
        )
        print(
            "TYPE:",
            result.get("subject_type"),
        )
        print(
            "LOCATION:",
            result.get("location"),
        )
        print(
            "ALIASES:",
            result.get("aliases_or_descriptions"),
        )

        if result.get(
            "_canonicalization_status"
        ) != "OK":
            failures.append(
                entity["canonical_subject"]
            )

    print()
    print("=" * 72)
    print("CONTROL FAILURES:", len(failures))

    if failures:
        raise SystemExit(
            "ENTITY SEARCH CANONICALIZER CONTROL FAILED"
        )

    print(
        "ENTITY SEARCH CANONICALIZER BASIC CONTROL PASSED — 3/3"
    )
