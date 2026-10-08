ALLOWED_PHOTO_TREATMENTS = {
    "SLOW_PUSH_IN",
    "SLOW_PULL_OUT",
    "PAN_LEFT_TO_RIGHT",
    "PAN_RIGHT_TO_LEFT",
    "DETAIL_PUSH_IN",
    "ESTABLISHING_HOLD",
}

ALLOWED_VIDEO_TREATMENTS = {
    "NORMAL",
    "VIDEO_THEN_FREEZE",
    "GENTLE_PUSH_IN",
    "ESTABLISHING_HOLD",
}

ALLOWED_PURPOSES = {
    "ESTABLISH",
    "REVEAL",
    "DETAIL",
    "EVIDENCE",
    "ATMOSPHERE",
    "TRANSITION",
}


def build_director_context(beat, timeline_clip):
    return {
        "voice_text": beat.get("voice_text", ""),
        "visual_intent": beat.get("visual_intent", ""),
        "factual_priority": beat.get("factual_priority"),
        "requirements": list(beat.get("requirements") or []),
        "avoid": list(beat.get("avoid") or []),
        "media_type": timeline_clip.get("media_type"),
        "visual_duration": timeline_clip.get("visual_duration"),
        "existing_treatment": timeline_clip.get(
            "visual_treatment"
        ),
    }


def normalize_director_decision(decision, timeline_clip):
    media_type = timeline_clip.get("media_type")
    existing = timeline_clip.get("visual_treatment")

    purpose = decision.get("purpose", "ATMOSPHERE")
    if purpose not in ALLOWED_PURPOSES:
        purpose = "ATMOSPHERE"

    treatment = decision.get("treatment")

    if media_type == "PHOTO":
        if treatment not in ALLOWED_PHOTO_TREATMENTS:
            treatment = "SLOW_PUSH_IN"

    elif media_type == "VIDEO":
        # Timeline safety rule always wins over AI decision.
        if existing == "VIDEO_THEN_FREEZE":
            treatment = "VIDEO_THEN_FREEZE"
        elif treatment not in ALLOWED_VIDEO_TREATMENTS:
            treatment = "NORMAL"

    else:
        treatment = "NONE"

    return {
        "purpose": purpose,
        "treatment": treatment,
        "reason": str(decision.get("reason", ""))[:300],
    }


def apply_semantic_decision(timeline_clip, decision):
    """
    Apply a normalized semantic direction without allowing any
    modification of MASTER or visual timing.
    """

    clip = dict(timeline_clip)

    timing_before = (
        clip.get("speech_start"),
        clip.get("speech_end"),
        clip.get("visual_start"),
        clip.get("visual_end"),
    )

    normalized = normalize_director_decision(
        decision,
        clip,
    )

    clip["semantic_purpose"] = normalized["purpose"]
    clip["director_treatment"] = normalized["treatment"]
    clip["director_reason"] = normalized["reason"]

    timing_after = (
        clip.get("speech_start"),
        clip.get("speech_end"),
        clip.get("visual_start"),
        clip.get("visual_end"),
    )

    assert timing_after == timing_before

    return clip

import json
import re


def _extract_json_object(text):
    if not isinstance(text, str):
        return {}

    text = text.strip()

    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        pass

    match = re.search(r"\{.*?\}", text, flags=re.DOTALL)
    if not match:
        return {}

    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def decide_with_local_model(
    beat,
    timeline_clip,
    model,
    tokenizer,
):
    """
    Ask the already-loaded local Qwen model for a semantic visual
    treatment. The model can suggest only; normalization remains
    authoritative.
    """
    from mlx_lm import generate

    context = build_director_context(
        beat,
        timeline_clip,
    )

    media_type = context["media_type"]

    if media_type == "PHOTO":
        treatments = sorted(ALLOWED_PHOTO_TREATMENTS)
    elif media_type == "VIDEO":
        treatments = sorted(ALLOWED_VIDEO_TREATMENTS)
    else:
        treatments = ["NONE"]

    prompt = f"""
You are the visual director of a restrained, high-retention professional documentary.

Choose how the EXISTING visual should be presented for this narration beat.

DECISION PRIORITY:
1. VOICE TEXT is the primary source of meaning and narrative emphasis.
2. VISUAL INTENT is secondary guidance only. It may be incomplete, overly literal, or wrong.
3. The existing media type and timing are fixed.

DIRECTING RULES:
- Do not change the media asset.
- Do not change speech timing or visual timing.
- Do not invent new footage or objects.
- Do not add sensational, flashy, or arbitrary effects.
- Do not request visible text, captions, labels, dates, arrows, or graphic overlays. Those belong to a separate overlay layer.
- Choose treatment according to the narrative function of THIS beat, not by repeating the same safe choice.
- ESTABLISHING_HOLD is appropriate only when a genuinely static establishing view benefits comprehension.
- For a PHOTO lasting several seconds, prefer subtle purposeful motion when it helps reveal geography, evidence, scale, detail, direction, or narrative emphasis.
- EVIDENCE should be considered when the narration presents a physical object, archaeological feature, document, structure, or other visual proof.
- DETAIL should be considered when the narration focuses attention on a specific feature.
- REVEAL should be considered when the narration introduces a discovery, contradiction, surprise, or important new fact.
- ATMOSPHERE should be used for mood or environmental context rather than factual proof.
- ESTABLISH should be used when orientation to place, setting, or overall subject is the main purpose.
- TRANSITION should be used only when the beat primarily bridges ideas or locations.
- Avoid mechanical variety: repeated treatments are allowed when genuinely justified by meaning.
- Choose only from the allowed values.

MEDIA TYPE:
{media_type}

VOICE TEXT:
{context["voice_text"]}

VISUAL INTENT:
{context["visual_intent"]}

FACTUAL PRIORITY:
{context["factual_priority"]}

REQUIREMENTS:
{json.dumps(context["requirements"], ensure_ascii=False)}

AVOID:
{json.dumps(context["avoid"], ensure_ascii=False)}

VISUAL DURATION:
{context["visual_duration"]}

ALLOWED PURPOSES:
{json.dumps(sorted(ALLOWED_PURPOSES))}

ALLOWED TREATMENTS:
{json.dumps(treatments)}

Return exactly one JSON object and nothing else:
{{
  "purpose": "one allowed purpose",
  "treatment": "one allowed treatment",
  "reason": "short reason"
}}
""".strip()

    messages = [
        {
            "role": "system",
            "content": (
                "You make restrained documentary editing decisions. "
                "Output valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    raw = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=180,
        verbose=False,
    )

    parsed = _extract_json_object(raw)

    normalized = normalize_director_decision(
        parsed,
        timeline_clip,
    )

    return {
        "raw": raw,
        "parsed": parsed,
        "decision": normalized,
    }
