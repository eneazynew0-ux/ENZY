from dataclasses import dataclass, asdict
from typing import List


@dataclass
class VisualScene:
    scene_id: int
    start: float
    end: float
    voice_text: str
    media_type: str
    search_queries: List[str]
    requirements: List[str]
    avoid: List[str]
    edit: str
    mood: str
    factual_priority: bool

    def to_dict(self):
        return asdict(self)


def extract_timed_words(transcript):
    words = []

    for segment in transcript.get("segments", []):
        for word in segment.get("words", []):
            if word.get("start") is None or word.get("end") is None:
                continue

            words.append({
                "start": float(word["start"]),
                "end": float(word["end"]),
                "word": word["word"].strip(),
                "probability": float(word.get("probability", 0.0)),
            })

    words.sort(key=lambda x: x["start"])
    return words


def timed_words_to_sentences(timed_words):
    sentences = []
    current = []

    for item in timed_words:
        current.append(item)

        word = item["word"]

        if word and word.rstrip().endswith((".", "!", "?")):
            sentences.append({
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": " ".join(x["word"] for x in current),
                "word_start_index": current[0]["script_index"],
                "word_end_index": current[-1]["script_index"],
                "complete": True,
            })
            current = []

    if current:
        sentences.append({
            "start": current[0]["start"],
            "end": current[-1]["end"],
            "text": " ".join(x["word"] for x in current),
            "word_start_index": current[0]["script_index"],
            "word_end_index": current[-1]["script_index"],
            "complete": False,
        })

    return sentences


@dataclass
class SceneDecision:
    start: float
    end: float
    voice_text: str
    visual_intent: str
    media_type: str
    factual_priority: bool
    search_queries: List[str]
    requirements: List[str]
    avoid: List[str]
    edit: str
    mood: str
    source_word_start: int
    source_word_end: int

    def to_dict(self):
        return asdict(self)


def prepare_scene_planner_input(sentences):
    return [
        {
            "sentence_id": i + 1,
            "start": sentence["start"],
            "end": sentence["end"],
            "duration": sentence["end"] - sentence["start"],
            "text": sentence["text"],
            "word_start_index": sentence["word_start_index"],
            "word_end_index": sentence["word_end_index"],
        }
        for i, sentence in enumerate(sentences)
        if sentence.get("complete", False)
    ]
