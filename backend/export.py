"""Versioned downstream projection of a session read through the naming guard."""

from .models import Identity
from .naming import identifiers_for


EVIDENCE_FIELDS = (
    'candidate', 'evidence', 'missing_evidence', 'next_action',
    'reason_unresolved', 'missing_optional_information', 'sources',
)
ACCEPTED_ACTIONS = {'confirmed', 'corrected', 'accepted general identity'}


def export_session(session, exported_at):
    # The current decision is authoritative; never resurrect a historical
    # acceptance or substitute the model's identity for a missing/rejected one.
    decision = session.get('decision')
    ready = bool(decision and decision['action'] in ACCEPTED_ACTIONS)
    result = session.get('result') or {}
    session_id = session['id']
    return {
        'schema_version': '1',
        'session_id': session_id,
        'exported_at': exported_at,
        'ready_for_market_research': ready,
        'recognition_status': result.get('status'),
        'canonical_identity': {
            key: decision['identity'].get(key) for key in Identity.model_fields
        } if ready else None,
        'user_decision': {
            key: decision.get(key) for key in ('action', 'at', 'attempt_number')
        } if decision else None,
        'identifiers': sorted(identifiers_for(session)),
        'recognition_evidence': {
            key: result.get(key, None if key == 'candidate' else '')
            for key in EVIDENCE_FIELDS
        },
        'images': [
            {
                **{key: image[key] for key in ('id', 'filename', 'width', 'height', 'submitted')},
                'preview_url': f"/api/sessions/{session_id}/images/{image['id']}",
            }
            for image in session['images']
        ],
    }
