from faster_whisper import WhisperModel


def transcribe_master(audio_path, model_name="small"):
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
    )

    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
    )

    result = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": [],
    }

    for segment in segments:
        item = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": [],
        }

        if segment.words:
            for word in segment.words:
                item["words"].append({
                    "start": word.start,
                    "end": word.end,
                    "word": word.word.strip(),
                    "probability": word.probability,
                })

        result["segments"].append(item)

    return result


def save_transcript(result, output_path):
    import json

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
