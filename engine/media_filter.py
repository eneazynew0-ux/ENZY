import re


BLOCKED_EXTENSIONS = {
    ".pdf",
}

SYMBOLIC_MARKERS = {
    "flag",
    "ensign",
    "seal",
    "coat of arms",
    "emblem",
    "insignia",
    "logo",
    "fin flash",
}


def get_extension(title):
    match = re.search(r"(\.[a-zA-Z0-9]+)$", title.strip())
    return match.group(1).lower() if match else ""


def filter_visual_candidates(assets, allow_svg=False):
    accepted = []
    rejected = []

    for asset in assets:
        title = asset.get("title", "")
        title_lower = title.lower()
        extension = get_extension(title)

        reason = None

        if extension in BLOCKED_EXTENSIONS:
            reason = f"blocked extension {extension}"

        elif extension == ".svg" and not allow_svg:
            reason = "SVG not suitable for photographic scene"

        elif any(marker in title_lower for marker in SYMBOLIC_MARKERS):
            reason = "symbolic/emblematic media"

        if reason:
            item = dict(asset)
            item["reject_reason"] = reason
            rejected.append(item)
        else:
            accepted.append(asset)

    return accepted, rejected
