"""
ENZYVIDEO media provider registry.

Central source of truth for provider capabilities and production status.
This module does NOT perform searches and does NOT change existing provider
behaviour. It only describes which providers may be used for which purpose.
"""

from copy import deepcopy


ACTIVE = "ACTIVE"
ACTIVE_SPECIALIZED = "ACTIVE_SPECIALIZED"
WAITING_FOR_API = "WAITING_FOR_API"
UNSUPPORTED_API = "UNSUPPORTED_API"
BLOCKED_BY_EXPORT_POLICY = "BLOCKED_BY_EXPORT_POLICY"


PROVIDERS = {
    "pixabay": {
        "name": "Pixabay",
        "status": ACTIVE,
        "media_types": {"photo", "video"},
        "generic_search": True,
        "specialized": False,
        "no_visible_credits_compatible": True,
    },

    "wikimedia": {
        "name": "Wikimedia Commons",
        "status": ACTIVE_SPECIALIZED,
        "media_types": {"photo"},
        "generic_search": False,
        "specialized": True,
        "no_visible_credits_compatible": "ASSET_LEVEL",
    },

    "internet_archive": {
        "name": "Internet Archive",
        "status": ACTIVE_SPECIALIZED,
        "media_types": {"photo", "video"},
        "generic_search": False,
        "specialized": True,
        "no_visible_credits_compatible": "ASSET_LEVEL",
    },

    "pexels": {
        "name": "Pexels",
        "status": ACTIVE,
        "media_types": {"photo", "video"},
        "generic_search": True,
        "specialized": False,
        "no_visible_credits_compatible": True,
    },

    "mixkit": {
        "name": "Mixkit",
        "status": UNSUPPORTED_API,
        "media_types": {"video"},
        "generic_search": True,
        "specialized": False,
        "no_visible_credits_compatible": "ASSET_LEVEL",
    },

    "coverr": {
        "name": "Coverr",
        "status": BLOCKED_BY_EXPORT_POLICY,
        "media_types": {"video"},
        "generic_search": True,
        "specialized": False,
        "no_visible_credits_compatible": False,
    },
}


def get_provider(provider_id):
    provider = PROVIDERS.get(provider_id)
    return deepcopy(provider) if provider else None


def list_providers():
    return {
        provider_id: deepcopy(config)
        for provider_id, config in PROVIDERS.items()
    }


def enabled_providers(media_type=None, include_specialized=True):
    result = []

    for provider_id, config in PROVIDERS.items():
        if config["status"] not in {ACTIVE, ACTIVE_SPECIALIZED}:
            continue

        if media_type and media_type not in config["media_types"]:
            continue

        if not include_specialized and config["specialized"]:
            continue

        result.append(provider_id)

    return result


def generic_providers(media_type=None):
    return [
        provider_id
        for provider_id in enabled_providers(
            media_type=media_type,
            include_specialized=False,
        )
    ]


def specialized_providers(media_type=None):
    result = []

    for provider_id, config in PROVIDERS.items():
        if config["status"] != ACTIVE_SPECIALIZED:
            continue

        if media_type and media_type not in config["media_types"]:
            continue

        result.append(provider_id)

    return result
