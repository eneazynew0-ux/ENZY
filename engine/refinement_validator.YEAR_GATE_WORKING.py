import re


RU_BAD_ENDINGS = {
    "что", "чтобы", "который", "которая", "которое", "которые",
    "если", "когда", "потому", "поскольку", "хотя", "будто",
    "словно", "чем", "как", "но", "а", "и", "или", "либо",
    "то", "на", "в", "во", "к", "ко", "с", "со", "из", "от",
    "до", "для", "по", "при", "без", "над", "под", "между"
}

RU_BAD_STARTS = {
    "что", "чтобы", "который", "которая", "которое", "которые",
    "потому", "поскольку"
}


def norm(text):
    return re.sub(r"[^\wа-яё-]+", "", str(text).lower(), flags=re.I)


def validate_boundaries(refined_scenes, timed_words, original_start, original_end):
    issues = []

    if not refined_scenes:
        return ["EMPTY_REFINEMENT"]

    if refined_scenes[0]["source_word_start"] != original_start:
        issues.append("START_COVERAGE_ERROR")

    if refined_scenes[-1]["source_word_end"] != original_end:
        issues.append("END_COVERAGE_ERROR")

    by_index = {int(w["script_index"]): w for w in timed_words}

    for i, scene in enumerate(refined_scenes):
        a = int(scene["source_word_start"])
        b = int(scene["source_word_end"])

        if a > b:
            issues.append(f"SCENE_{i+1}_REVERSED_RANGE")

        if i > 0:
            prev = refined_scenes[i - 1]
            expected = int(prev["source_word_end"]) + 1
            if a != expected:
                issues.append(f"SCENE_{i+1}_NONCONTIGUOUS")

        if i < len(refined_scenes) - 1:
            end_word = norm(by_index[b]["word"])
            next_word = norm(by_index[b + 1]["word"])

            if end_word in RU_BAD_ENDINGS:
                issues.append(
                    f"BOUNDARY_{b}_{b+1}_BAD_END:{end_word}"
                )

            if next_word in RU_BAD_STARTS:
                issues.append(
                    f"BOUNDARY_{b}_{b+1}_BAD_START:{next_word}"
                )

    return issues


def validate_requirements_avoid(refined_scenes):
    issues = []

    for i, scene in enumerate(refined_scenes, 1):
        requirements = {
            norm(x) for x in scene.get("requirements", []) if norm(x)
        }
        avoid = {
            norm(x) for x in scene.get("avoid", []) if norm(x)
        }

        exact_conflicts = requirements & avoid

        for conflict in sorted(exact_conflicts):
            issues.append(
                f"SCENE_{i}_REQUIRE_AVOID_CONFLICT:{conflict}"
            )

        for req in requirements:
            for av in avoid:
                if len(req) >= 6 and len(av) >= 6:
                    if req in av or av in req:
                        issues.append(
                            f"SCENE_{i}_REQUIRE_AVOID_SEMANTIC_CONFLICT:{req}|{av}"
                        )

    return sorted(set(issues))


def validate_unsupported_years(refined_scenes, timed_words, original_start, original_end):
    issues = []

    master_text = " ".join(
        str(w["word"])
        for w in timed_words
        if original_start <= int(w["script_index"]) <= original_end
    )

    allowed_years = set(re.findall(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", master_text))

    for i, scene in enumerate(refined_scenes, 1):
        query_text = " ".join(
            str(q) for q in scene.get("search_queries", [])
        )

        query_years = set(
            re.findall(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", query_text)
        )

        for year in sorted(query_years - allowed_years):
            issues.append(
                f"SCENE_{i}_UNSUPPORTED_QUERY_YEAR:{year}"
            )

    return issues



def validate_refinement(
    refined_scenes,
    timed_words,
    original_start,
    original_end
):
    issues = []
    issues.extend(
        validate_boundaries(
            refined_scenes,
            timed_words,
            original_start,
            original_end
        )
    )
    issues.extend(validate_requirements_avoid(refined_scenes))
    issues.extend(
        validate_unsupported_years(
            refined_scenes,
            timed_words,
            original_start,
            original_end
        )
    )

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


if __name__ == "__main__":
    print("REFINEMENT VALIDATOR MODULE: OK")
