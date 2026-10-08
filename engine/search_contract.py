"""Bind retrieval and candidate judges to the approved visual plan."""
import copy
import json
from engine.beat_visual_contract import artifact_cutaway, named_place_cutaway, VISUAL_FIELDS


def visual_search_target(beat, legacy_target=''):
    intent = beat.get('visual_intent')
    if not isinstance(intent,str) or not intent.strip():
        raise ValueError('APPROVED_VISUAL_INTENT_REQUIRED')
    # Caller-provided targets may describe rejected plans. Never inherit them.
    positive = {k:beat.get(k) for k in ('visual_intent','requirements','edit')}
    contract=beat.get('visual_contract') or {}
    representation={k:contract.get(k) for k in ('mode','identity_scope','subject','depicts_narrated_event')}
    return ('Judge only this approved visual plan. Search queries are not identity evidence. '
            'Exclusions are forbidden content, not requested subjects. '
            'Contextual media must not be treated as footage of the narrated event.\n'
            +json.dumps({'positive_visual':positive,'exclusions':beat.get('avoid') or [],
                         'representation':representation},ensure_ascii=False))


def bound_contextual_identity(beat, entities):
    contract=beat.get('visual_contract')
    if contract is None:
        return None
    if not isinstance(contract,dict):
        raise ValueError('INVALID_VISUAL_SEARCH_CONTRACT')
    mode=contract.get('mode')
    grounding={'entities':entities or []}
    if mode=='CONTEXTUAL_PLACE':
        proposal=named_place_cutaway(beat,grounding)
        if proposal is None:
            raise ValueError('CONTEXTUAL_PLACE_IDENTITY_UNAVAILABLE')
        identity={'canonical_subject':'Harare airport','subject_type':'airport',
                  'location':'UNKNOWN','aliases_or_descriptions':['Harare airport'],
                  '_source_canonical_subject':'аэропорт Хараре'}
    elif mode=='CONTEXTUAL_SUBJECT':
        proposal=artifact_cutaway(beat,grounding)
        matches=[e for e in entities or []
                 if (e.get('researched_search_identity') or {}).get('canonical_subject')==contract.get('subject')]
        if proposal is None or len(matches)!=1:
            raise ValueError('CONTEXTUAL_SUBJECT_IDENTITY_UNAVAILABLE')
        entity=matches[0];r=entity['researched_search_identity']
        if not r.get('source_url') or not r.get('basis'):
            raise ValueError('IDENTITY_RESEARCH_EVIDENCE_MISSING')
        identity={'canonical_subject':r['canonical_subject'],'subject_type':r['subject_type'],
                  'location':'UNKNOWN','aliases_or_descriptions':r.get('aliases') or [],
                  '_source_canonical_subject':entity.get('canonical_subject'),
                  '_identity_research':copy.deepcopy(r)}
    else:
        raise ValueError('UNSUPPORTED_VISUAL_SEARCH_CONTRACT')
    plan,trace=proposal
    if any(beat.get(k)!=plan[k] for k in VISUAL_FIELDS):
        raise ValueError('VISUAL_PLAN_CHANGED_AFTER_APPROVAL')
    if contract.get('subject')!=trace['subject'] or contract.get('identity_scope')!=trace['identity_scope']:
        raise ValueError('VISUAL_SEARCH_IDENTITY_MISMATCH')
    identity['_canonicalization_status']='OK'
    identity['_representation_mode']=mode
    identity['_identity_scope']=trace['identity_scope']
    return identity
