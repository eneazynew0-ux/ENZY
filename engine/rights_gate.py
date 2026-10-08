ALLOWED_LICENSES = {
    "public domain",
    "cc0",
    "cc by 1.0",
    "cc by 2.0",
    "cc by 2.5",
    "cc by 3.0",
    "cc by 4.0",
    "cc by-sa 1.0",
    "cc by-sa 2.0",
    "cc by-sa 2.5",
    "cc by-sa 3.0",
    "cc by-sa 4.0",
    "pixabay content license",
    "pexels license",
}

BLOCKED_LICENSE_MARKERS = {
    "noncommercial",
    "non-commercial",
    "nc",
    "no derivatives",
    "no-derivatives",
    "nd",
    "all rights reserved",
}


def normalize_license(value):
    return " ".join(str(value or "").strip().lower().split())


def check_asset(asset):
    license_name = normalize_license(asset.get("license_short"))
    license_url = str(asset.get("license_url") or "").strip()
    source_url = str(
        asset.get("description_url")
        or asset.get("source_url")
        or ""
    ).strip()

    if not license_name:
        return {
            "status": "REVIEW",
            "reason": "Missing license metadata",
        }

    if any(marker in license_name for marker in BLOCKED_LICENSE_MARKERS):
        return {
            "status": "BLOCKED",
            "reason": f"Restricted license: {asset.get('license_short')}",
        }

    if license_name not in ALLOWED_LICENSES:
        return {
            "status": "REVIEW",
            "reason": f"Unknown or unapproved license: {asset.get('license_short')}",
        }

    if not source_url:
        return {
            "status": "REVIEW",
            "reason": "Missing source page",
        }

    return {
        "status": "ALLOWED",
        "reason": f"Approved license: {asset.get('license_short')}",
        "license_url": license_url,
        "source_url": source_url,
        "artist": asset.get("artist", ""),
        "credit": asset.get("credit", ""),
    }


def filter_allowed(assets):
    allowed = []

    for asset in assets:
        decision = check_asset(asset)

        if decision["status"] == "ALLOWED":
            item = dict(asset)
            item["rights"] = decision
            allowed.append(item)

    return allowed
