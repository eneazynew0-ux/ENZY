MIN_CROP_WIDTH = 0.20
MIN_CROP_HEIGHT = 0.20


def full_frame():
    return {
        "x": 0.0,
        "y": 0.0,
        "width": 1.0,
        "height": 1.0,
    }


def normalize_crop(crop):
    """
    Validate a normalized crop rectangle.

    Coordinates are normalized to 0..1:
    x, y = top-left
    width, height = crop size

    Invalid or unsafe crops fall back to full frame.
    """

    if not isinstance(crop, dict):
        return full_frame()

    try:
        x = float(crop["x"])
        y = float(crop["y"])
        width = float(crop["width"])
        height = float(crop["height"])
    except (KeyError, TypeError, ValueError):
        return full_frame()

    if width < MIN_CROP_WIDTH or height < MIN_CROP_HEIGHT:
        return full_frame()

    if x < 0.0 or y < 0.0:
        return full_frame()

    if width > 1.0 or height > 1.0:
        return full_frame()

    if x + width > 1.0 or y + height > 1.0:
        return full_frame()

    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def build_reframe_context(beat, composed_clip, phase):
    """
    Build semantic context for a future local vision model.

    This function does not inspect or modify the image.
    """

    return {
        "voice_text": beat.get("voice_text", ""),
        "visual_intent": beat.get("visual_intent", ""),
        "requirements": beat.get("requirements", []),
        "avoid": beat.get("avoid", []),
        "semantic_purpose": composed_clip.get("semantic_purpose"),
        "phase_role": phase.get("role"),
        "media_type": composed_clip.get("media_type"),
        "local_path": composed_clip.get("local_path"),
    }


def apply_reframe_to_phase(phase, crop):
    """
    Attach crop metadata to a visual phase.

    Phase timing and source asset are protected.
    """

    result = dict(phase)

    protected = {
        "phase_index": phase.get("phase_index"),
        "role": phase.get("role"),
        "start": phase.get("start"),
        "end": phase.get("end"),
        "duration": phase.get("duration"),
        "source_asset": phase.get("source_asset"),
    }

    result["crop"] = normalize_crop(crop)

    for field, value in protected.items():
        assert result.get(field) == value, (
            f"Semantic Reframe modified protected field: {field}"
        )

    return result


def safe_primary_crop():
    """
    PRIMARY/CONTEXT phases default to the complete source image.
    """
    return full_frame()


SPATIAL_REGIONS = {
    "1": "TOP_LEFT",
    "2": "TOP_CENTER",
    "3": "TOP_RIGHT",
    "4": "CENTER_LEFT",
    "5": "CENTER",
    "6": "CENTER_RIGHT",
    "7": "BOTTOM_LEFT",
    "8": "BOTTOM_CENTER",
    "9": "BOTTOM_RIGHT",
}


def parse_spatial_region(text):
    """
    Fail-closed parser for VLM spatial classification.

    Accepts natural wrapper text such as:
        "5"
        "Answer: 5"

    Rejects:
        multiple region numbers
        no region number
        ambiguous output
    """
    import re

    if not isinstance(text, str):
        return None

    matches = re.findall(
        r"(?<!\d)([1-9])(?!\d)",
        text,
    )

    if len(matches) != 1:
        return None

    return SPATIAL_REGIONS[matches[0]]


def region_to_crop(region):
    """
    Convert a semantic 3x3 region into a restrained detail crop.

    Crops deliberately overlap neighboring grid cells so the
    documentary detail shot retains surrounding visual context.
    """

    crops = {
        "TOP_LEFT": {
            "x": 0.00, "y": 0.00,
            "width": 0.65, "height": 0.65,
        },
        "TOP_CENTER": {
            "x": 0.175, "y": 0.00,
            "width": 0.65, "height": 0.65,
        },
        "TOP_RIGHT": {
            "x": 0.35, "y": 0.00,
            "width": 0.65, "height": 0.65,
        },
        "CENTER_LEFT": {
            "x": 0.00, "y": 0.175,
            "width": 0.65, "height": 0.65,
        },
        "CENTER": {
            "x": 0.175, "y": 0.175,
            "width": 0.65, "height": 0.65,
        },
        "CENTER_RIGHT": {
            "x": 0.35, "y": 0.175,
            "width": 0.65, "height": 0.65,
        },
        "BOTTOM_LEFT": {
            "x": 0.00, "y": 0.35,
            "width": 0.65, "height": 0.65,
        },
        "BOTTOM_CENTER": {
            "x": 0.175, "y": 0.35,
            "width": 0.65, "height": 0.65,
        },
        "BOTTOM_RIGHT": {
            "x": 0.35, "y": 0.35,
            "width": 0.65, "height": 0.65,
        },
    }

    return normalize_crop(
        crops.get(region)
    )
