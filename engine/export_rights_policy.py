"""
ENZYVIDEO Export Rights Policy V1

The normal Rights Gate answers:
    "May ENZYVIDEO use this asset at all?"

This module answers the stricter question:
    "May ENZYVIDEO export this asset under NO_VISIBLE_CREDITS?"

NO_VISIBLE_CREDITS means the rendered video itself must contain:
- no stock-service watermark
- no stock-service logo
- no source URL
- no creator/author credit
- no license text
- no mandatory attribution overlay
- no mandatory attribution end-card

Internal provenance metadata is still retained.
"""

from engine.rights_gate import check_asset, normalize_license


EXPORT_POLICY_NO_VISIBLE_CREDITS = "NO_VISIBLE_CREDITS"


NO_VISIBLE_CREDIT_LICENSES = {
    "cc0",
    "public domain",
    "pixabay content license",
    "pexels license",
}


ATTRIBUTION_LICENSE_PREFIXES = (
    "cc by ",
    "cc by-sa ",
)


def requires_visible_attribution(license_name):
    license_name = normalize_license(license_name)

    return any(
        license_name.startswith(prefix)
        for prefix in ATTRIBUTION_LICENSE_PREFIXES
    )


def check_export_asset(
    asset,
    policy=EXPORT_POLICY_NO_VISIBLE_CREDITS,
):
    """
    Fail closed.

    First require the existing Rights Gate to approve the asset.
    Then apply the stricter export policy.
    """

    rights = check_asset(asset)

    if rights["status"] != "ALLOWED":
        return {
            "status": "REJECT",
            "policy": policy,
            "reason": (
                "Base rights gate did not approve asset: "
                + rights["reason"]
            ),
            "rights": rights,
        }

    if policy != EXPORT_POLICY_NO_VISIBLE_CREDITS:
        return {
            "status": "REJECT",
            "policy": policy,
            "reason": f"Unknown export policy: {policy}",
            "rights": rights,
        }

    license_name = normalize_license(
        asset.get("license_short")
    )

    if requires_visible_attribution(license_name):
        return {
            "status": "REJECT",
            "policy": policy,
            "reason": (
                "License requires attribution and is not "
                "approved for NO_VISIBLE_CREDITS"
            ),
            "rights": rights,
        }

    if license_name not in NO_VISIBLE_CREDIT_LICENSES:
        return {
            "status": "REJECT",
            "policy": policy,
            "reason": (
                "License is not explicitly approved for "
                "NO_VISIBLE_CREDITS"
            ),
            "rights": rights,
        }

    if asset.get("has_watermark") is True:
        return {
            "status": "REJECT",
            "policy": policy,
            "reason": "Asset contains a watermark",
            "rights": rights,
        }

    if asset.get("requires_visible_credit") is True:
        return {
            "status": "REJECT",
            "policy": policy,
            "reason": "Asset explicitly requires visible credit",
            "rights": rights,
        }

    return {
        "status": "EXPORT_ALLOWED",
        "policy": policy,
        "reason": (
            "Asset approved for export without visible credits"
        ),
        "license": license_name,
        "source_url": rights.get("source_url", ""),
        "license_url": rights.get("license_url", ""),
        "artist": rights.get("artist", ""),
        "credit": rights.get("credit", ""),
    }


def filter_export_allowed(
    assets,
    policy=EXPORT_POLICY_NO_VISIBLE_CREDITS,
):
    allowed = []

    for asset in assets:
        decision = check_export_asset(asset, policy)

        if decision["status"] == "EXPORT_ALLOWED":
            item = dict(asset)
            item["export_rights"] = decision
            allowed.append(item)

    return allowed
