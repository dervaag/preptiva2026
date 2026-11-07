"""Async SQLAlchemy LangGraph saver for JSON-only, reference-only graph states.

This deliberately supports this application's sequential StateGraphs, not arbitrary
Python objects, messages, Send tasks or pickle fallback. PostgreSQL and SQLite use
the same additive tables and transaction semantics.
"""
import json

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, WRITES_IDX_MAP
from sqlalchemy import delete, select

from app.graphs.models import GraphCheckpoint, GraphWrite


def json_value(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


class JsonOnlySerializer:
    def dumps_typed(self, value):
        return 'json', json.dumps(value, ensure_ascii=False, allow_nan=False).encode()

    def loads_typed(self, value):
        kind, payload = value
        if kind != 'json':
            raise ValueError('Only JSON graph state is accepted.')
        return json.loads(payload)


def config_for(thread_id, namespace, checkpoint_id):
    return {'configurable': {'thread_id': thread_id, 'checkpoint_ns': namespace, 'checkpoint_id': checkpoint_id}}


class SQLAlchemySaver(BaseCheckpointSaver):
    def __init__(self, session_factory=None):
        super().__init__(serde=JsonOnlySerializer())
        if session_factory is None:
            from app.db import SessionLocal
            session_factory = SessionLocal
        self.session_factory = session_factory

    async def aget_tuple(self, config):
        values = config['configurable']
        thread_id, namespace = values['thread_id'], values.get('checkpoint_ns', '')
        statement = select(GraphCheckpoint).where(GraphCheckpoint.thread_id == thread_id, GraphCheckpoint.namespace == namespace)
        if values.get('checkpoint_id'):
            statement = statement.where(GraphCheckpoint.checkpoint_id == values['checkpoint_id'])
        else:
            statement = statement.order_by(GraphCheckpoint.checkpoint_id.desc()).limit(1)
        async with self.session_factory() as db:
            row = await db.scalar(statement)
            if row is None:
                return None
            writes = (await db.scalars(select(GraphWrite).where(GraphWrite.thread_id == thread_id,
                GraphWrite.namespace == namespace, GraphWrite.checkpoint_id == row.checkpoint_id)
                .order_by(GraphWrite.task_path, GraphWrite.task_id, GraphWrite.position))).all()
            return CheckpointTuple(config_for(thread_id, namespace, row.checkpoint_id), row.checkpoint, row.meta,
                config_for(thread_id, namespace, row.parent_id) if row.parent_id else None,
                [(w.task_id, w.channel, w.value['value']) for w in writes])

    async def alist(self, config, *, filter=None, before=None, limit=None):
        statement = select(GraphCheckpoint).order_by(GraphCheckpoint.checkpoint_id.desc())
        if config:
            values = config['configurable']
            statement = statement.where(GraphCheckpoint.thread_id == values['thread_id'])
            if 'checkpoint_ns' in values:
                statement = statement.where(GraphCheckpoint.namespace == values['checkpoint_ns'])
            if values.get('checkpoint_id'):
                statement = statement.where(GraphCheckpoint.checkpoint_id == values['checkpoint_id'])
        if before:
            statement = statement.where(GraphCheckpoint.checkpoint_id < before['configurable']['checkpoint_id'])
        async with self.session_factory() as db:
            rows = (await db.scalars(statement)).all()
        emitted = 0
        for row in rows:
            if filter and any(row.meta.get(key) != value for key, value in filter.items()):
                continue
            if limit is not None and emitted >= limit:
                return
            item = await self.aget_tuple(config_for(row.thread_id, row.namespace, row.checkpoint_id))
            if item:
                yield item
                emitted += 1

    async def aput(self, config, checkpoint, metadata, new_versions):
        values = config['configurable']
        thread_id, namespace = values['thread_id'], values.get('checkpoint_ns', '')
        key = (thread_id, namespace, checkpoint['id'])
        async with self.session_factory() as db:
            row = await db.get(GraphCheckpoint, key)
            if row is None:
                row = GraphCheckpoint(thread_id=thread_id, namespace=namespace, checkpoint_id=checkpoint['id'])
                db.add(row)
            row.parent_id = values.get('checkpoint_id')
            row.checkpoint, row.meta = json_value(checkpoint), json_value(metadata)
            await db.commit()
        return config_for(*key)

    async def aput_writes(self, config, writes, task_id, task_path=''):
        values = config['configurable']
        async with self.session_factory() as db:
            for index, (channel, value) in enumerate(writes):
                position = WRITES_IDX_MAP.get(channel, index)
                # Validation exceptions can embed document fragments. The ledger
                # keeps a safe error class; checkpoints need only the failure marker.
                if channel == '__error__':
                    value = 'Node failed; inspect the operation error_type.'
                key = (values['thread_id'], values.get('checkpoint_ns', ''), values['checkpoint_id'], task_id, position)
                row = await db.get(GraphWrite, key)
                if row is not None and position >= 0:
                    continue
                if row is None:
                    row = GraphWrite(thread_id=key[0], namespace=key[1], checkpoint_id=key[2], task_id=task_id, position=position)
                    db.add(row)
                row.channel, row.value, row.task_path = channel, {'value': json_value(value)}, task_path
            await db.commit()

    async def adelete_thread(self, thread_id):
        async with self.session_factory() as db:
            await db.execute(delete(GraphWrite).where(GraphWrite.thread_id == thread_id))
            await db.execute(delete(GraphCheckpoint).where(GraphCheckpoint.thread_id == thread_id))
            await db.commit()
