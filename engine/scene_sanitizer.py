import copy
import re


YEAR_RE = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")


def master_text_for_range(timed_words, start_i, end_i):
    return " ".join(
        str(w["word"])
        for w in timed_words
        if start_i <= int(w["script_index"]) <= end_i
    )


def sanitize_unsupported_query_years(scene, timed_words):
    result = copy.deepcopy(scene)

    start_i = int(result["source_word_start"])
    end_i = int(result["source_word_end"])

    master_text = master_text_for_range(
        timed_words,
        start_i,
        end_i,
    )

    allowed_years = set(YEAR_RE.findall(master_text))

    cleaned_queries = []

    for query in result.get("search_queries", []):
        query = str(query)

        def replace_year(match):
            year = match.group(0)
            return year if year in allowed_years else ""

        cleaned = YEAR_RE.sub(replace_year, query)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
        cleaned = cleaned.strip(" ,.;:-")

        if cleaned:
            cleaned_queries.append(cleaned)

    result["search_queries"] = cleaned_queries
    return result


def sanitize_scene(scene, timed_words):
    result = sanitize_unsupported_query_years(
        scene,
        timed_words,
    )
    return result


if __name__ == "__main__":
    print("SCENE SANITIZER MODULE: OK")
