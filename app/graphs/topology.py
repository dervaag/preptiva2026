"""Versioned node names for operator inspection, checked against the run hash."""
from app.graphs.runtime import fingerprint


def plan_nodes(kind, roles=()):
    if kind == 'prepare':
        return ['validate', 'parse', 'context', 'plan', 'questions', 'audio', 'commit']
    if kind == 'turn':
        return ['accept_transcript', 'shared_context', 'analyze', 'coordinate', 'prepare_response', 'commit']
    if kind == 'finalize':
        if not roles or len(roles) > 3 or len(set(roles)) != len(roles) or any(
                role not in ('hr', 'user', 'manager') for role in roles):
            raise ValueError('Panel inspector tidak valid.')
        return ['load_sources', *('initial_' + role for role in roles),
                'review_differences', 'aggregate', 'feedback', 'commit']
    raise ValueError('Jenis graph tidak dikenal.')


def matches_plan(kind, roles, stored_hash):
    return fingerprint(plan_nodes(kind, roles)) == stored_hash
