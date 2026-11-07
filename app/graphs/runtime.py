"""Durable, versioned graph runner with an application operation ledger.

LangGraph persists only execution references. Model outputs live once in the
operation ledger; interview answers and session status remain authoritative in
the application tables. Successful operations are reused after checkpoint gaps.
An interrupted paid call is never silently replayed: its outcome is ambiguous
until an explicit retry acknowledges that the provider may charge again.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta
from hashlib import sha256
import json
import time
from typing import TypedDict
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from app.graphs.models import GraphExecution, GraphOperation
from app.log import emit
from app.models import now
from app.services.locks import local_lock

_context = ContextVar('graph_run_context', default=None)
_node = ContextVar('graph_node', default='')
_usage = ContextVar('graph_operation_usage', default=None)


class GraphBusy(RuntimeError):
    pass


class GraphInputMismatch(ValueError):
    pass


class GraphOperationUncertain(RuntimeError):
    def __init__(self, operation_key):
        self.operation_key = operation_key
        super().__init__('Hasil panggilan provider belum dapat dipastikan. Retry eksplisit diperlukan; panggilan dapat dikenai biaya kembali.')


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':')).encode()).hexdigest()


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def observe_usage(model, usage, latency_ms, attempt=1):
    """Called by the provider adapter, without prompts, secrets or candidate text."""
    target = _usage.get()
    if target is not None:
        target.append({'model': str(model), 'usage': _json(usage or {}),
                       'latency_ms': round(latency_ms), 'attempt': attempt})


async def durable_call(name, inputs, callback, *, paid=True):
    """Transparent outside graphs; payload hashes distinguish parallel model calls."""
    context = _context.get()
    if context is None:
        return await callback()
    return await context.operation('provider:' + name + ':' + fingerprint(inputs), inputs, callback, paid=paid)


async def acknowledge_retry(thread_id, session_id, *, session_factory=None):
    """Local-operator-only, one-shot permission for an ambiguous provider retry.

    No browser route calls this function. It is useful before STT acceptance,
    when recovery still needs the original audio to be resubmitted by its owner.
    The grant is scoped to one exact session/thread and consumed under its lease.
    """
    if session_factory is None:
        from app.db import SessionLocal
        session_factory = SessionLocal
    async with local_lock(('graph-grant', thread_id)), session_factory() as db:
        row = await db.scalar(select(GraphExecution).where(GraphExecution.thread_id == thread_id).with_for_update())
        if row is None or row.session_id != session_id:
            raise ValueError('Eksekusi bukan milik sesi ini.')
        if row.lease_owner and row.lease_until and row.lease_until > now():
            raise GraphBusy('Eksekusi masih aktif; izin retry belum dapat diberikan.')
        ambiguous = await db.scalar(select(GraphOperation).where(GraphOperation.thread_id == thread_id,
            GraphOperation.paid.is_(True), GraphOperation.status.in_(['running', 'uncertain'])).limit(1))
        if ambiguous is None:
            raise ValueError('Tidak ada panggilan berbayar dengan hasil yang belum pasti.')
        if not row.allow_uncertain_once:
            history = [*(row.retry_authorizations or []), {
                'grant_id': uuid4().hex, 'granted_at': now().isoformat() + 'Z',
                'source': 'local_operator', 'possible_charge_acknowledged': True,
                'consumed_at': None}]
            changed = await db.execute(update(GraphExecution).where(GraphExecution.thread_id == thread_id,
                GraphExecution.session_id == session_id,
                or_(GraphExecution.lease_owner.is_(None), GraphExecution.lease_until < now()))
                .values(allow_uncertain_once=True, retry_authorizations=history))
            if not changed.rowcount:
                raise GraphBusy('Eksekusi baru saja dimulai; izin retry belum dapat diberikan.')
        await db.commit()
    return {'thread_id': thread_id, 'authorized': True}


class RunContext:
    def __init__(self, thread_id, session_id, owner, session_factory, *, allow_uncertain=False):
        self.thread_id, self.session_id = thread_id, session_id
        self.owner, self.session_factory = owner, session_factory
        self.allow_uncertain = allow_uncertain
        self.lost = False

    async def assert_owned(self):
        if self.lost:
            raise GraphBusy('Graph lease no longer belongs to this worker.')
        async with self.session_factory() as db:
            row = await db.get(GraphExecution, self.thread_id)
            if not row or row.lease_owner != self.owner or not row.lease_until or row.lease_until <= now():
                self.lost = True
                raise GraphBusy('Graph lease no longer belongs to this worker.')

    async def result(self, node_name):
        async with self.session_factory() as db:
            row = await db.get(GraphOperation, (self.thread_id, 'node:' + node_name))
            if not row or row.status != 'succeeded':
                raise LookupError('Graph node has no completed output: ' + node_name)
            return row.output['value']

    async def operation(self, name, inputs, callback, *, paid=False, _node_output=False):
        key = 'node:' + name if _node_output else ((_node.get() + ':') if _node.get() else '') + name
        if len(key) > 190:
            key = key[:100] + ':' + sha256(key.encode()).hexdigest()
        input_hash = fingerprint(inputs)
        # Also deduplicate identical parallel subcalls within the same graph node.
        async with local_lock(('graph-operation', self.thread_id, key)):
            await self.assert_owned()
            async with self.session_factory() as db:
                row = await db.get(GraphOperation, (self.thread_id, key))
                if row and row.input_hash != input_hash:
                    raise GraphInputMismatch('Operation inputs changed under an existing idempotency key.')
                if row and row.paid != paid:
                    raise GraphInputMismatch('Operation payment policy changed under an existing key.')
                if row and row.status == 'succeeded':
                    return row.output['value']
                if row and row.paid and row.status in ('running', 'uncertain') and not self.allow_uncertain:
                    row.status = 'uncertain'
                    await db.commit()
                    raise GraphOperationUncertain(key)
                if row is None:
                    row = GraphOperation(thread_id=self.thread_id, operation_key=key, input_hash=input_hash,
                                         paid=paid, status='running', attempts=0, duration_ms=0, telemetry={})
                    db.add(row)
                previous_attempts = row.attempts
                previous_duration = row.duration_ms
                previous_telemetry = row.telemetry or {}
                acknowledged = row.paid and row.status in ('running', 'uncertain')
                row.status, row.error_type = 'running', None
                row.attempts += 1
                row.started_at, row.finished_at = now(), None
                await db.commit()
            calls = []
            usage_token = _usage.set(calls)
            start = time.monotonic()
            try:
                value = _json(await callback())
                await self.assert_owned()
                async with self.session_factory() as db:
                    row = await db.get(GraphOperation, (self.thread_id, key))
                    row.output = {'value': value}
                    row.status, row.finished_at = 'succeeded', now()
                    elapsed = round((time.monotonic() - start) * 1000)
                    row.duration_ms = previous_duration + elapsed
                    row.telemetry = self._telemetry(previous_telemetry, calls, previous_attempts + 1,
                                                    elapsed, acknowledged, 'succeeded')
                    await db.commit()
                emit('graph_operation_completed', thread_id=self.thread_id, operation=key,
                     attempt=previous_attempts + 1, duration_ms=elapsed, paid=paid)
                return value
            except BaseException as error:
                # A child provider operation may already be marked ambiguous. Node
                # callbacks remain safely replayable because each paid call is cached.
                elapsed = round((time.monotonic() - start) * 1000)
                with suppress(Exception):
                    async with self.session_factory() as db:
                        row = await db.get(GraphOperation, (self.thread_id, key))
                        if row and row.status != 'succeeded':
                            row.status = 'uncertain' if paid else 'failed'
                            row.error_type, row.finished_at = type(error).__name__, now()
                            row.duration_ms = previous_duration + elapsed
                            row.telemetry = self._telemetry(previous_telemetry, calls, previous_attempts + 1,
                                                            elapsed, acknowledged, row.status)
                            await db.commit()
                if paid and not isinstance(error, (asyncio.CancelledError, GraphOperationUncertain)):
                    raise GraphOperationUncertain(key) from error
                raise
            finally:
                _usage.reset(usage_token)

    @staticmethod
    def _telemetry(previous, calls, attempt, elapsed, acknowledged, status):
        return {'attempts': [*previous.get('attempts', []), {'attempt': attempt, 'duration_ms': elapsed,
            'status': status, 'ambiguous_retry_acknowledged': bool(acknowledged), 'calls': calls}]}


async def _ensure_execution(factory, thread_id, session_id, kind, input_hash, plan_hash):
    async with factory() as db:
        row = await db.get(GraphExecution, thread_id)
        if row is None:
            db.add(GraphExecution(thread_id=thread_id, session_id=session_id, kind=kind,
                                  input_hash=input_hash, plan_hash=plan_hash))
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
            row = await db.get(GraphExecution, thread_id)
        if not row or (row.session_id, row.kind, row.input_hash, row.plan_hash) != (session_id, kind, input_hash, plan_hash):
            raise GraphInputMismatch('Graph inputs or versioned node plan changed under an existing thread.')


@asynccontextmanager
async def _lease(factory, thread_id, session_id, *, allow_uncertain=False, seconds=120):
    owner = str(uuid4())
    deadline = time.monotonic() + 25
    while True:
        granted = False
        async with factory() as db:
            acquired = await db.execute(update(GraphExecution).where(GraphExecution.thread_id == thread_id,
                or_(GraphExecution.lease_owner.is_(None), GraphExecution.lease_until < now()))
                .values(lease_owner=owner, lease_until=now() + timedelta(seconds=seconds),
                        status='running', attempts=GraphExecution.attempts + 1, error_type=None))
            if acquired.rowcount:
                # The UPDATE owns the row lock, so grant consumption and lease
                # acquisition are one transaction even across worker processes.
                row = await db.get(GraphExecution, thread_id)
                granted = row.allow_uncertain_once
                if granted:
                    row.allow_uncertain_once = False
                    history = [dict(entry) for entry in (row.retry_authorizations or [])]
                    for entry in reversed(history):
                        if entry.get('consumed_at') is None:
                            entry.update(consumed_at=now().isoformat() + 'Z', execution_attempt=row.attempts)
                            break
                    row.retry_authorizations = history
            await db.commit()
        if acquired.rowcount:
            break
        if time.monotonic() >= deadline:
            raise GraphBusy('Graph is still running on another worker.')
        await asyncio.sleep(.15)
    context = RunContext(thread_id, session_id, owner, factory, allow_uncertain=allow_uncertain or granted)
    async def heartbeat():
        while True:
            await asyncio.sleep(max(.1, seconds / 3))
            try:
                async with factory() as db:
                    result = await db.execute(update(GraphExecution).where(GraphExecution.thread_id == thread_id,
                        GraphExecution.lease_owner == owner).values(lease_until=now() + timedelta(seconds=seconds)))
                    await db.commit()
                if not result.rowcount:
                    context.lost = True
                    return
            except Exception:
                context.lost = True
                return
    task = asyncio.create_task(heartbeat())
    try:
        yield context
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        async with factory() as db:
            await db.execute(update(GraphExecution).where(GraphExecution.thread_id == thread_id,
                GraphExecution.lease_owner == owner).values(lease_owner=None, lease_until=None))
            await db.commit()


class ReferenceState(TypedDict):
    thread_id: str
    session_id: int
    completed_node: str


async def execute(kind, session_id, run_key, nodes, input_data=None, *, allow_uncertain=False, session_factory=None):
    """Run/resume one versioned sequential LangGraph with durable node outputs.

    callbacks: async function(ctx) -> JSON. The supplied run_key identifies one
    logical operation forever. Changed inputs or node names require a new version.
    """
    # Imports stay lazy: legacy sessions do not import or initialize LangGraph.
    from langgraph.graph import END, START, StateGraph
    from app.graphs.checkpoint import SQLAlchemySaver

    names = [name for name, _ in nodes]
    if not names or len(names) != len(set(names)) or len(run_key) > 190:
        raise ValueError('Graph needs unique nodes and a thread ID of at most 190 characters.')
    if session_factory is None:
        from app.db import SessionLocal
        session_factory = SessionLocal
    factory = session_factory
    await _ensure_execution(factory, run_key, session_id, kind, fingerprint(input_data), fingerprint(names))
    async with local_lock(('graph-execution', run_key)):
        async with _lease(factory, run_key, session_id, allow_uncertain=allow_uncertain) as context:
            token = _context.set(context)
            try:
                graph = StateGraph(ReferenceState)
                for name, callback in nodes:
                    def wrap(node_name, action):
                        async def node(state):
                            marker = _node.set(node_name)
                            try:
                                await context.operation(node_name, {'versioned_thread': run_key}, lambda: action(context), _node_output=True)
                                return {'completed_node': node_name}
                            finally:
                                _node.reset(marker)
                        return node
                    graph.add_node(name, wrap(name, callback))
                graph.add_edge(START, names[0])
                for before, after in zip(names, names[1:]):
                    graph.add_edge(before, after)
                graph.add_edge(names[-1], END)
                saver = SQLAlchemySaver(factory)
                compiled = graph.compile(checkpointer=saver)
                config = {'configurable': {'thread_id': run_key}, 'recursion_limit': max(25, len(names) + 5)}
                previous = await saver.aget_tuple(config)
                if previous:
                    # None means resume the last persisted superstep; never append
                    # a new graph input that could reset a completed interview turn.
                    await compiled.ainvoke(None, config, durability='sync')
                else:
                    await compiled.ainvoke({'thread_id': run_key, 'session_id': session_id, 'completed_node': ''},
                                           config, durability='sync')
                value = await context.result(names[-1])
                await context.assert_owned()
                async with factory() as db:
                    await db.execute(update(GraphExecution).where(GraphExecution.thread_id == run_key,
                        GraphExecution.lease_owner == context.owner).values(status='succeeded', error_type=None))
                    await db.commit()
                return value
            except BaseException as error:
                with suppress(Exception):
                    async with factory() as db:
                        await db.execute(update(GraphExecution).where(GraphExecution.thread_id == run_key,
                            GraphExecution.lease_owner == context.owner).values(
                            status='uncertain' if isinstance(error, GraphOperationUncertain) else 'failed',
                            error_type=type(error).__name__))
                        await db.commit()
                raise
            finally:
                _context.reset(token)
