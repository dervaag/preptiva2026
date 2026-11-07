"""Studio read-only inspectors; nodes display ledger metadata, never run providers.

The node names match production plans, but running this graph only inspects their
recorded outcomes. Application checkpoints remain owned by Preptiva's worker.
"""
import asyncio
from importlib import import_module
from typing import NotRequired, TypedDict
from uuid import UUID

from langgraph.graph import START, END, StateGraph
from langchain_core.runnables import RunnableConfig

from app.graphs.topology import plan_nodes


class InspectorInput(TypedDict):
    session_uuid: NotRequired[str]
    execution_thread: NotRequired[str]
    inspection: NotRequired[dict]


class InspectorState(InspectorInput):
    mode: str
    session_id: str
    execution: dict
    observed_nodes: list[dict]
    completed_node: str


def clean_report(value):
    """Whitelist metadata before it becomes an inspector node's output."""
    try:
        session_id = str(UUID(value['session_id']))
        runs = value['executions']
        if not isinstance(runs, list) or len(runs) > 1000:
            raise ValueError()
        cleaned = []
        for run in runs:
            kind = run['kind']
            if kind not in ('prepare', 'turn', 'finalize'):
                raise ValueError()
            operations = run['operations']
            if not isinstance(operations, list) or len(operations) > 2000:
                raise ValueError()
            thread = run['thread_id']
            if not isinstance(thread, str) or len(thread) > 190:
                raise ValueError()
            plan = run['plan_nodes']
            if not isinstance(plan, list) or not 1 <= len(plan) <= 12 or any(
                    not isinstance(node, str) or len(node) > 40 for node in plan):
                raise ValueError()
            safe_operations = []
            for operation in operations:
                key, status = operation['key'], operation['status']
                if not isinstance(key, str) or len(key) > 190 or status not in ('running','succeeded','failed','uncertain','pending'):
                    raise ValueError()
                counts = {key: operation.get(key, 0) for key in ('attempts', 'duration_ms')}
                if any(type(count) is not int or count < 0 for count in counts.values()):
                    raise ValueError()
                safe_operations.append({'key': key, 'status': status, **counts,
                                        'paid': operation.get('paid') is True})
            cleaned.append({'thread_id': thread, 'kind': kind,
                'status': run['status'] if run['status'] in ('pending','running','succeeded','failed','uncertain') else 'unknown',
                'plan_nodes': plan, 'plan_matches': run.get('plan_matches') is True,
                'operations': safe_operations})
        return {'session_id': session_id, 'executions': cleaned}
    except (KeyError, TypeError, ValueError):
        raise ValueError('Metadata inspector tidak valid. Gunakan JSON dari app.graphs.manage inspect.') from None


def build_inspector(kind, roles=()):
    names = plan_nodes(kind, roles)
    graph = StateGraph(InspectorState, input_schema=InspectorInput)

    async def load_metadata(state):
        if state.get('inspection'):
            report = clean_report(state['inspection'])
        else:
            try:
                sid = str(UUID(state.get('session_uuid', '')))
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Isi session_uuid yang valid atau inspection hasil CLI.') from None
            # Settings may read a local env file on its first import. Keep that
            # import off Agent Server's event loop; the DB query itself is async.
            module = await asyncio.to_thread(import_module, 'app.graphs.manage')
            report = clean_report(await module.inspect(sid))
        selected = [run for run in report['executions'] if run['kind'] == kind and
                    (not state.get('execution_thread') or run['thread_id'] == state['execution_thread'])]
        if not selected:
            raise ValueError('Eksekusi graph yang dipilih belum tercatat pada sesi ini.')
        run = selected[-1]
        if not run['plan_matches'] or run['plan_nodes'] != names:
            raise ValueError('Rencana inspector tidak cocok. Untuk finalisasi, samakan configurable.panel_roles dengan panel sesi.')
        return {'mode': 'read_only_inspection', 'session_id': report['session_id'],
                'inspection': report, 'execution': run, 'observed_nodes': [], 'completed_node': 'load_metadata'}

    graph.add_node('load_metadata', load_metadata)
    graph.add_edge(START, 'load_metadata')
    previous = 'load_metadata'
    for name in names:
        def observe(node_name):
            async def node(state):
                operation = next((item for item in state['execution']['operations']
                                  if item['key'] == 'node:' + node_name), None)
                value = {'node': node_name, 'status': 'not_recorded', 'attempts': 0, 'duration_ms': 0}
                if operation:
                    value.update({key: operation[key] for key in ('status','attempts','duration_ms')})
                return {'completed_node': node_name, 'observed_nodes': [*state['observed_nodes'], value]}
            return node
        graph.add_node(name, observe(name))
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    # Agent Server supplies the inspector's own checkpointer. This never replaces
    # or resumes the application's SQLAlchemy checkpoints.
    return graph.compile()


def preparation_inspector(config: RunnableConfig):
    return build_inspector('prepare')


def turn_inspector(config: RunnableConfig):
    return build_inspector('turn')


def finalization_inspector(config: RunnableConfig):
    roles = config.get('configurable', {}).get('panel_roles', ['hr','user','manager'])
    return build_inspector('finalize', roles)
