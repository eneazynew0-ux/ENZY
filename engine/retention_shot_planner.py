from copy import deepcopy


def _duration(beat):
    if beat.get("duration") is not None:
        return float(beat["duration"])
    return float(beat["end"]) - float(beat["start"])


def choose_phase_count(beat):
    duration = _duration(beat)
    mode = beat.get("documentary_mode")
    strategy = beat.get("motion_strategy")

    # Very short beats should not become nervous micro-montages.
    if duration < 4.0:
        return 1

    # Documents/maps benefit from structured reveals.
    if mode == "DOCUMENT":
        if duration >= 10.0:
            return 3
        return 2

    if mode == "MAP":
        return 2 if duration >= 4.5 else 1

    # Archive material can move from context to evidence.
    if mode == "ARCHIVE":
        return 2 if duration >= 5.0 else 1

    # Exact stills stay restrained.
    if mode == "FACTUAL_STILL":
        return 2 if duration >= 7.0 else 1

    # Video should not be chopped excessively.
    if strategy == "REAL_VIDEO_PRIMARY":
        if duration >= 10.0:
            return 3
        if duration >= 6.5:
            return 2
        return 1

    return 2 if duration >= 8.0 else 1


def phase_roles(beat, count):
    mode = beat.get("documentary_mode")

    if count == 1:
        return ["PRIMARY"]

    if mode == "DOCUMENT":
        if count == 3:
            return ["CONTEXT", "EVIDENCE", "DETAIL"]
        return ["CONTEXT", "DETAIL"]

    if mode == "MAP":
        return ["OVERVIEW", "FOCUS"]

    if mode == "ARCHIVE":
        return ["CONTEXT", "EVIDENCE"]

    if mode == "FACTUAL_STILL":
        return ["PRIMARY", "DETAIL"]

    if count == 3:
        return ["ESTABLISH", "PRIMARY", "DETAIL"]

    return ["PRIMARY", "DETAIL"]


def _weights(count):
    if count == 1:
        return [1.0]
    if count == 2:
        return [0.60, 0.40]
    if count == 3:
        return [0.34, 0.38, 0.28]
    raise ValueError(f"Unsupported phase count: {count}")


def build_retention_phases(beat):
    start = float(beat["start"])
    end = float(beat["end"])
    duration = end - start

    count = choose_phase_count(beat)
    roles = phase_roles(beat, count)
    weights = _weights(count)

    phases = []
    cursor = start

    for i, (role, weight) in enumerate(zip(roles, weights)):
        if i == count - 1:
            phase_end = end
        else:
            phase_end = cursor + duration * weight

        phases.append({
            "phase_index": i,
            "role": role,
            "start": cursor,
            "end": phase_end,
            "duration": phase_end - cursor,
        })

        cursor = phase_end

    return phases


def attach_retention_plan(beat):
    result = deepcopy(beat)
    result["retention_phases"] = build_retention_phases(beat)
    result["retention_phase_count"] = len(result["retention_phases"])
    return result


def plan_retention_sequence(beats):
    return [attach_retention_plan(beat) for beat in beats]
