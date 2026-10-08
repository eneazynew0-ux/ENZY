"""Conservative, reproducible cutaways for researched artifact-group identities.

A group identity is insufficient evidence for a historical placement or event.
Only this bounded contextual plan can be approved by this contract. Actual media
still needs the normal identity and licensing checks; this module certifies no asset.
"""
import copy
from engine.beat_grounding import phrase_present

VISUAL_FIELDS = ('visual_intent', 'search_queries', 'requirements', 'avoid', 'edit')


def artifact_cutaway(beat, grounding):
    candidates = []
    positive = ' '.join(str(beat.get(k) or '') for k in
                        ('visual_intent', 'search_queries', 'requirements', 'edit'))
    for entity in grounding.get('entities', []):
        identity = entity.get('researched_search_identity') or {}
        if identity.get('status') != 'VERIFIED' or identity.get('scope') != 'ARTIFACT_GROUP':
            continue
        name, kind = identity.get('canonical_subject'), identity.get('subject_type')
        if not isinstance(name, str) or not name.strip() or not isinstance(kind, str) or not kind.strip():
            continue
        terms = [name, kind] + (identity.get('aliases') or [])
        if kind == 'soapstone bird sculpture':
            terms += ['stone bird', 'stone sculpture of a bird']
        if any(phrase_present(term, positive) for term in terms):
            candidates.append((entity, identity))
    if len(candidates) > 1:
        raise ValueError('CONTEXTUAL_CUTAWAY_AMBIGUOUS')
    if not candidates:
        return None
    entity, identity = candidates[0]
    name, kind = identity['canonical_subject'], identity['subject_type']
    plan = {
        'visual_intent': 'Contextual close-up photograph of {} ({}).'.format(name, kind),
        'search_queries': [name + ' ' + kind, name + ' artifact photograph'],
        'requirements': [name, kind, 'Verified artifact-group identity; contextual subject only'],
        'avoid': ['Historical event reconstruction', 'Specific historical placement or handling',
                  'People interacting with the artifact', 'Unverified individual specimen identity',
                  'Watermarks, logos or added captions'],
        'edit': 'Gentle push-in on the artifact photograph; no added factual elements.',
    }
    return plan, {
        'mode': 'CONTEXTUAL_SUBJECT', 'identity_scope': 'ARTIFACT_GROUP',
        'subject': name, 'source_url': identity.get('source_url'),
        'identity_trace': copy.deepcopy(entity.get('identity_trace', {})),
        'depicts_narrated_event': False,
        'asset_identity_verified': False,
    }


def check_artifact_visual_contract(beat, grounding):
    if (beat.get('visual_contract') or {}).get('mode') == 'CONTEXTUAL_PLACE':
        proposal = named_place_cutaway(beat, grounding)
        if proposal is not None and all(beat.get(k) == proposal[0][k] for k in VISUAL_FIELDS):
            return []
        return [{'type': 'INVALID_CONTEXTUAL_PLACE_PLAN', 'severity': 'HIGH',
                 'detail': 'Contextual place plan differs from locally supported template.'}]
    try:
        proposal = artifact_cutaway(beat, grounding)
    except ValueError as exc:
        return [{'type': 'CONTEXTUAL_CUTAWAY_AMBIGUOUS', 'severity': 'HIGH',
                 'detail': str(exc)}]
    if proposal is None:
        return []
    plan, trace = proposal
    if all(beat.get(key) == plan[key] for key in VISUAL_FIELDS):
        return []
    continuity_fields = tuple(
        key for key in VISUAL_FIELDS if key != "edit"
    )
    if (
        beat.get("continuity_reason")
        and "continue the same shot" in str(beat.get("edit") or "").casefold()
        and all(beat.get(key) == plan[key] for key in continuity_fields)
    ):
        return []
    return [{'type': 'ARTIFACT_GROUP_REQUIRES_CONTEXTUAL_PLAN', 'severity': 'HIGH',
             'detail': 'Group-level identity cannot authorize staged historical surroundings or events.',
             'identity_scope': trace['identity_scope'], 'subject': trace['subject']}]


def repair_artifact_cutaway(beat, issues, grounding):
    if any(i.get('type') == 'UNSUPPORTED_ENTITY_REVEAL' for i in issues):
        proposal = named_place_cutaway(beat, grounding)
        if proposal is not None:
            plan, trace = proposal
            result = copy.deepcopy(beat)
            result.update(plan)
            result['visual_contract'] = trace
            return result
    if not any(i.get('type') == 'ARTIFACT_GROUP_REQUIRES_CONTEXTUAL_PLAN' for i in issues):
        return None
    proposal = artifact_cutaway(beat, grounding)
    if proposal is None:
        raise ValueError('CONTEXTUAL_CUTAWAY_AMBIGUOUS')
    plan, trace = proposal
    result = copy.deepcopy(beat)
    result.update(plan)
    result['visual_contract'] = trace
    return result


def repair_artifact_continuity(beat, issues):
    """Justify one continued artifact shot when no second setting is verified."""
    if not any(
        issue.get("type") == "ADJACENT_VISUAL_REPETITION"
        for issue in issues
    ):
        return None
    contract = beat.get("visual_contract") or {}
    if (
        contract.get("mode") != "CONTEXTUAL_SUBJECT"
        or contract.get("identity_scope") != "ARTIFACT_GROUP"
    ):
        return None

    result = copy.deepcopy(beat)
    result["edit"] = (
        "Continue the same shot as a deliberate continuous artifact cutaway "
        "because no distinct historical setting is verified; shift to a "
        "restrained detail crop without adding factual elements."
    )
    result["continuity_reason"] = (
        "The narration continues the same artifact while the separate historical "
        "setting is unverified."
    )
    return result


def named_place_cutaway(beat, grounding):
    """Context image of a locally named place, never footage of the reception.

    The current bilingual mapping is deliberately limited to Harare airport.
    Other places remain unsupported until their identity mapping is established.
    """
    aliases = ['аэропорт Хараре', 'аэропорту Хараре', 'аэропорта Хараре',
               'аэропортом Хараре', 'Harare airport']
    current = str(beat.get('voice_text') or '')
    mentions = [term for term in aliases if phrase_present(term, current)]
    entities = [e for e in grounding.get('entities', [])
                if e.get('canonical_subject') == 'аэропорт Хараре']
    if not mentions or len(entities) != 1:
        return None
    return {
        'visual_intent': 'Contextual photograph of Harare airport.',
        'search_queries': ['Harare airport photograph', 'Harare airport Zimbabwe'],
        'requirements': ['Verified identity: Harare airport', 'Contextual place photograph only'],
        'avoid': ['Stone bird artifact', 'President or foreign delegation',
                  'Reconstruction of the military reception', 'Watermarks, logos or added captions'],
        'edit': 'Gentle push-in on the place photograph; no added factual elements.',
    }, {
        'mode': 'CONTEXTUAL_PLACE', 'identity_scope': 'NAMED_PLACE',
        'subject': 'Harare airport', 'depicts_narrated_event': False,
        'asset_identity_verified': False,
        'identity_trace': {'matched_mentions': mentions, 'scope': 'current_narration_only'},
        'fallback_reason': 'Unrevealed entity removed; locally named place retained',
    }
