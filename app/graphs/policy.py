"""Session-pinned orchestration selection; changing env never migrates old sessions."""
VERSION = 'langgraph-v1'


class UnsupportedGraphVersion(RuntimeError):
    pass


def enabled(session):
    runtime = session.script.get('runtime', {})
    if runtime.get('engine') != 'langgraph':
        return False
    if runtime.get('graph_version') != VERSION:
        raise UnsupportedGraphVersion('Versi orkestrasi sesi belum didukung server ini.')
    return True


def snapshot(engine):
    if engine == 'legacy':
        return {'engine': 'legacy'}
    from app.graphs.panel_scoring import policy_snapshot
    return {'engine': 'langgraph', 'graph_version': VERSION,
            'aggregation_policy': policy_snapshot(),
            'recovery_policy': 'reuse-completed-explicit-uncertain-retry-v1'}


def aggregation_version(session):
    return session.script.get('runtime', {}).get('aggregation_policy', {}).get('version', 'legacy-owner-per-question')
