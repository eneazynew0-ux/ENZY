VALID_MEDIA_TYPES = {"VIDEO", "PHOTO", "MAP", "GRAPHIC"}


def validate_scene(scene):
    required = [
        "start",
        "end",
        "voice_text",
        "visual_intent",
        "media_type",
        "factual_priority",
        "search_queries",
        "requirements",
        "avoid",
        "edit",
        "mood",
        "source_word_start",
        "source_word_end",
    ]

    missing = [key for key in required if key not in scene]

    if missing:
        return False, f"Missing fields: {missing}"

    if scene["media_type"] not in VALID_MEDIA_TYPES:
        return False, f"Invalid media_type: {scene['media_type']}"

    if scene["end"] <= scene["start"]:
        return False, "Scene end must be greater than start"

    if not isinstance(scene["search_queries"], list) or not scene["search_queries"]:
        return False, "search_queries must be a non-empty list"

    if not isinstance(scene["requirements"], list):
        return False, "requirements must be a list"

    if not isinstance(scene["avoid"], list):
        return False, "avoid must be a list"

    return True, "OK"


def validate_plan(scenes):
    errors = []

    for index, scene in enumerate(scenes):
        valid, message = validate_scene(scene)

        if not valid:
            errors.append({
                "scene": index + 1,
                "error": message,
            })

    return {
        "valid": len(errors) == 0,
        "scene_count": len(scenes),
        "errors": errors,
    }
