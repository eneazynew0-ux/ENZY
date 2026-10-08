import re
import unicodedata


def normalize_word(word):
    word = unicodedata.normalize("NFKC", word)
    word = word.lower().replace("ё", "е")
    word = re.sub(r"[^\w]+", "", word, flags=re.UNICODE)
    return word


def tokenize_script(text):
    tokens = []

    for match in re.finditer(r"\S+", text):
        raw = match.group(0)
        normalized = normalize_word(raw)

        if not normalized:
            continue

        tokens.append({
            "word": raw,
            "normalized": normalized,
            "char_start": match.start(),
            "char_end": match.end(),
        })

    return tokens


from difflib import SequenceMatcher


def word_similarity(a, b):
    a = normalize_word(a)
    b = normalize_word(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


def find_best_match(script_word, whisper_words, start_index=0, window=8):
    best_index = None
    best_score = 0.0

    end_index = min(len(whisper_words), start_index + window)

    for i in range(start_index, end_index):
        score = word_similarity(script_word, whisper_words[i]["word"])

        if score > best_score:
            best_score = score
            best_index = i

    return best_index, best_score


def align_token_sequences(script_tokens, whisper_words, min_similarity=0.72):
    n = len(script_tokens)
    m = len(whisper_words)

    script_norm = [x["normalized"] for x in script_tokens]
    whisper_norm = [normalize_word(x["word"]) for x in whisper_words]

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    trace = [[None] * (m + 1) for _ in range(n + 1)]

    gap_penalty = -0.45

    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap_penalty
        trace[i][0] = "script_gap"

    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap_penalty
        trace[0][j] = "whisper_gap"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            similarity = word_similarity(script_norm[i - 1], whisper_norm[j - 1])

            match_score = 2.0 * similarity if similarity >= min_similarity else -1.0

            choices = [
                (dp[i - 1][j - 1] + match_score, "match"),
                (dp[i - 1][j] + gap_penalty, "script_gap"),
                (dp[i][j - 1] + gap_penalty, "whisper_gap"),
            ]

            dp[i][j], trace[i][j] = max(choices, key=lambda x: x[0])

    matches = []
    i, j = n, m

    while i > 0 or j > 0:
        action = trace[i][j]

        if action == "match":
            similarity = word_similarity(script_norm[i - 1], whisper_norm[j - 1])

            if similarity >= min_similarity:
                matches.append({
                    "script_index": i - 1,
                    "whisper_index": j - 1,
                    "similarity": similarity,
                })

            i -= 1
            j -= 1

        elif action == "script_gap":
            i -= 1

        elif action == "whisper_gap":
            j -= 1

        else:
            break

    matches.reverse()
    return matches


def build_timed_script(script_tokens, whisper_words, matches):
    timed = [None] * len(script_tokens)

    for match in matches:
        si = match["script_index"]
        wi = match["whisper_index"]
        source = whisper_words[wi]

        timed[si] = {
            "script_index": si,
            "word": script_tokens[si]["word"],
            "normalized": script_tokens[si]["normalized"],
            "start": float(source["start"]),
            "end": float(source["end"]),
            "alignment": "matched",
            "similarity": float(match["similarity"]),
        }

    return timed


def interpolate_missing_timings(timed, script_tokens):
    result = list(timed)
    n = len(result)
    i = 0

    while i < n:
        if result[i] is not None:
            i += 1
            continue

        gap_start = i

        while i < n and result[i] is None:
            i += 1

        gap_end = i - 1
        count = gap_end - gap_start + 1

        prev_item = result[gap_start - 1] if gap_start > 0 else None
        next_item = result[i] if i < n else None

        if prev_item is not None and next_item is not None:
            start_time = prev_item["end"]
            end_time = next_item["start"]
        elif next_item is not None:
            end_time = next_item["start"]
            start_time = max(0.0, end_time - 0.35 * count)
        elif prev_item is not None:
            start_time = prev_item["end"]
            end_time = start_time + 0.35 * count
        else:
            start_time = 0.0
            end_time = 0.35 * count

        duration = max(0.0, end_time - start_time)
        step = duration / count if count else 0.0

        for offset, index in enumerate(range(gap_start, gap_end + 1)):
            word_start = start_time + step * offset
            word_end = start_time + step * (offset + 1)

            result[index] = {
                "script_index": index,
                "word": script_tokens[index]["word"],
                "normalized": script_tokens[index]["normalized"],
                "start": word_start,
                "end": word_end,
                "alignment": "interpolated",
                "similarity": 0.0,
            }

    return result
