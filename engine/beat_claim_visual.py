"""Safe contextual visuals for reported, quoted, or disputed claims."""

import re


def reported_claim_cutaway(beat, issues, preceding_text):
    issue_types = {issue.get("type") for issue in issues}
    if not issue_types.intersection({
        "REPORTED_CLAIM_VISUALIZED_AS_FACT",
        "ADJACENT_VISUAL_REPETITION",
    }):
        return None

    context = " ".join(
        [str(preceding_text or "")[-600:], str(beat.get("voice_text") or "")]
    ).casefold()
    reported = re.search(
        r"учебник\w*\s+(?:скажет|говорит|утвержда)|"
        r"утверждал|утверждали|считал|считали|предположил|версия|миф|"
        r"\b(?:textbook|source)\s+(?:says|claims|claimed)\b|"
        r"\b(?:claimed|argued|believed|supposed|myth|theory)\b",
        context,
    )
    if not reported:
        return None

    result = dict(beat)
    result.update({
        "visual_intent": (
            "Neutral archival close-up of an old printed educational source "
            "with pages visible but no readable claims. This represents the "
            "source of a disputed narrative, not the claim as reality."
        ),
        "search_queries": [
            "old school textbook pages archival photograph",
            "vintage educational book open pages no readable text",
        ],
        "requirements": [
            "physical old printed educational book or source",
            "documentary photograph",
            "page text is not readable",
        ],
        "avoid": [
            "depicting the reported claim as factual reality",
            "blank map presented as historical fact",
            "readable quotations or added captions",
            "logos and watermarks",
        ],
        "edit": (
            "Slow restrained move across the archival source; the shot frames "
            "the narration as a reported claim without endorsing it."
        ),
    })
    result.pop("visual_contract", None)
    return result
