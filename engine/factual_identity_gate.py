import re
import unicodedata


def _clean(value):
    return " ".join(str(value or "").strip().split())


def _norm(value):
    value = unicodedata.normalize("NFKD", _clean(value))
    value = "".join(
        ch for ch in value
        if not unicodedata.combining(ch)
    )
    value = value.casefold()
    value = re.sub(r"[^a-z0-9а-яё]+", " ", value)
    return " ".join(value.split())


def _tokens(value):
    return [
        token
        for token in _norm(value).split()
        if len(token) >= 3
    ]


def _asset_metadata_text(asset):
    fields = [
        asset.get("title"),
        asset.get("tags"),
        asset.get("description"),
        asset.get("identifier"),
    ]

    return _norm(
        " ".join(
            _clean(value)
            for value in fields
            if _clean(value)
        )
    )


def _canonical_terms(entity):
    canonical = _clean(
        entity.get("canonical_subject")
        or entity.get("exact_subject")
    )

    if not canonical:
        return []

    terms = [canonical]

    # A multi-word canonical subject can safely contribute
    # the full phrase. Individual words are NOT automatically
    # treated as independent identity proof.
    return [
        {
            "raw": term,
            "norm": _norm(term),
        }
        for term in terms
        if _norm(term)
    ]


def _context_tokens(entity):
    values = []

    values.append(entity.get("subject_type"))
    values.append(entity.get("location"))

    for alias in entity.get(
        "aliases_or_descriptions",
        [],
    ):
        values.append(alias)

    tokens = []

    for value in values:
        tokens.extend(_tokens(value))

    # Remove very generic archaeological/media words.
    blocked = {
        "culture",
        "культура",
        "archaeological",
        "археологическая",
        "ancient",
        "древний",
        "древняя",
        "figures",
        "фигуры",
        "head",
        "голова",
        "village",
        "деревня",
    }

    result = []
    seen = set()

    for token in tokens:
        if token in blocked or token in seen:
            continue
        seen.add(token)
        result.append(token)

    return result


def _canonical_core_tokens(entity):
    canonical = _clean(
        entity.get("canonical_subject")
        or entity.get("exact_subject")
    )

    generic = {
        "culture",
        "культура",
        "churches",
        "церкви",
        "libraries",
        "библиотеки",
        "site",
        "археологический",
        "археологическая",
    }

    return [
        token
        for token in _tokens(canonical)
        if token not in generic
    ]


def check_factual_identity(asset, entity):
    """
    Deterministic factual identity gate.

    Retrieval query is never identity proof.
    Visual similarity is never identity proof.

    Strong path:
      full canonical subject appears in asset metadata.

    Context path:
      a canonical core token appears AND at least one
      independent entity-context token also appears.

    This prevents ambiguous short names such as "Nok"
    from verifying unrelated assets merely because the
    same token appears in their tags.
    """

    if not entity:
        return {
            "status": "NOT_REQUIRED",
            "confidence": "NONE",
            "matched_term": None,
            "context_matches": [],
            "reason": "No factual visual entity supplied",
        }

    metadata = _asset_metadata_text(asset)

    if not metadata:
        return {
            "status": "UNVERIFIED",
            "confidence": "LOW",
            "matched_term": None,
            "context_matches": [],
            "reason": "Asset has no usable identity metadata",
        }

    # A sculpture identity must include evidence of a physical
    # artifact, not just geographic and animal-name tags.
    subject_type = _norm(entity.get("subject_type"))
    if entity.get("_identity_scope") == "ARTIFACT_GROUP":
        # A photograph of a replica or a graphic symbol cannot establish
        # identity of an original physical artifact. Query text is excluded.
        non_original = re.search(
            r"\b(copy|copies|replica|replicas|reproduction|reproductions|"
            r"souvenir|souvenirs|bannister|banister|banknote|banknotes|"
            r"flag|flags|emblem|seal|logo)\b|\bcoat of arms\b",
            metadata,
        )
        if non_original or str(asset.get("mime", "")).lower() == "image/svg+xml":
            return {
                "status": "UNVERIFIED", "confidence": "LOW",
                "matched_term": None, "context_matches": [],
                "reason": "Replica or symbolic representation is not an original artifact",
            }
    sculpture_type = any(
        marker in subject_type
        for marker in ("sculpt", "carving", "скульптур", "стату")
    )
    if sculpture_type:
        artifact_markers = (
            "sculpture", "sculptures", "statue", "statues",
            "carved", "carving", "carvings", "soapstone",
            "steatite", "artifact", "artefact",
            "скульптур", "стату", "артефакт", "резная", "резной",
        )
        artifact_supported = any(
            marker in metadata
            for marker in artifact_markers
        )
        if not artifact_supported:
            return {
                "status": "UNVERIFIED",
                "confidence": "LOW",
                "matched_term": None,
                "context_matches": [],
                "reason": "Metadata does not establish the required sculpture type",
            }

    canonical_terms = _canonical_terms(entity)

    for term in canonical_terms:
        if term["norm"] in metadata:
            return {
                "status": "VERIFIED",
                "confidence": "HIGH",
                "matched_term": term["raw"],
                "context_matches": [],
                "reason": (
                    "Asset metadata explicitly contains "
                    "the full canonical factual identity"
                ),
            }

    metadata_tokens = set(metadata.split())
    core_tokens = _canonical_core_tokens(entity)
    context_tokens = _context_tokens(entity)

    matched_core = [
        token
        for token in core_tokens
        if token in metadata_tokens
    ]

    matched_context = [
        token
        for token in context_tokens
        if token in metadata_tokens
        and token not in matched_core
    ]

    # Multi-word factual identities must not be verified by a
    # single ambiguous token plus generic context. For example,
    # "Nabta Playa" must never verify an unrelated "playa" asset
    # merely because both also mention a desert.
    #
    # Single-core identities such as "Nok" retain the existing
    # requirement: canonical token + independent entity context.
    if len(core_tokens) > 1:
        identity_supported = (
            all(token in metadata_tokens for token in core_tokens)
            and bool(matched_context)
        )
    else:
        identity_supported = bool(
            matched_core and matched_context
        )

    if identity_supported:
        return {
            "status": "VERIFIED",
            "confidence": "MEDIUM",
            "matched_term": (
                " ".join(core_tokens)
                if len(core_tokens) > 1
                else matched_core[0]
            ),
            "context_matches": matched_context[:5],
            "reason": (
                "Canonical identity is supported by "
                "independent entity context in metadata"
            ),
        }

    return {
        "status": "UNVERIFIED",
        "confidence": "LOW",
        "matched_term": (
            matched_core[0]
            if matched_core
            else None
        ),
        "context_matches": matched_context[:5],
        "reason": (
            "Asset metadata does not provide sufficient "
            "evidence for the required factual identity"
        ),
    }


if __name__ == "__main__":
    nabta = {
        "canonical_subject": "Nabta Playa",
        "subject_type": "archaeological site",
        "location": "southern Egypt",
        "aliases_or_descriptions": [
            "Nabta Playa stone circle",
            "Nabta Playa megaliths",
        ],
    }

    nok = {
        "canonical_subject": "Nok culture",
        "subject_type": "archaeological culture",
        "location": "central Nigeria, Nok village",
        "aliases_or_descriptions": [
            "terracotta figures",
            "terracotta head",
            "iron furnaces",
        ],
    }

    controls = [
        (
            {
                "title": "Megaliths from Nabta Playa",
                "identifier": "megaliths-from-nabta-playa-endlos",
            },
            nabta,
            "VERIFIED",
        ),
        (
            {
                "title": "ancient, thracian, megalith",
                "tags": "ancient, thracian, megalith, bulgaria",
            },
            nabta,
            "UNVERIFIED",
        ),
        (
            {
                "title": "Male Head, Nok Culture",
                "identifier": "male-head-nok-culture-endlos",
            },
            nok,
            "VERIFIED",
        ),
        (
            {
                "title": "container ship, ship, freighter",
                "tags": (
                    "container ship, ship, freighter, "
                    "north baltic canal, cargo ship, nok"
                ),
            },
            nok,
            "UNVERIFIED",
        ),
        (
            {
                "title": "Nok terracotta head Nigeria",
                "tags": "nok, terracotta, nigeria",
            },
            nok,
            "VERIFIED",
        ),
    ]

    failures = []

    for asset, entity, expected in controls:
        result = check_factual_identity(asset, entity)

        print()
        print("ASSET:", asset.get("title"))
        print("STATUS:", result["status"])
        print("EXPECTED:", expected)
        print("MATCHED:", result["matched_term"])
        print(
            "CONTEXT:",
            result["context_matches"],
        )

        if result["status"] != expected:
            failures.append(
                f"{asset.get('title')}: expected "
                f"{expected}, got {result['status']}"
            )

    print()
    print("CONTROL FAILURES:", len(failures))

    for failure in failures:
        print(" -", failure)

    if failures:
        raise SystemExit(
            "FACTUAL IDENTITY GATE V2 CONTROL FAILED"
        )

    print(
        "FACTUAL IDENTITY GATE V2 BASIC CONTROL PASSED — 5/5"
    )
