"""Real LangGraph persistence tests with isolated SQLite and no provider calls."""
import asyncio
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, InterviewEvent, InterviewSession, User, now
from app.graphs.models import GraphCheckpoint, GraphExecution, GraphOperation, GraphWrite
from app.graphs.runtime import (GraphBusy, GraphInputMismatch, GraphOperationUncertain, acknowledge_retry,
                                durable_call, execute, fingerprint, observe_usage)


@unittest.skipUnless(importlib.util.find_spec('langgraph'), 'LangGraph requires the Python 3.12 environment.')
class GraphRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.temporary.name) / 'graph.db'))
        @event.listens_for(self.engine.sync_engine, 'connect')
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.factory() as db:
            user = User(email='graph@example.test', password_hash='test-only', name='Graph Test')
            db.add(user)
            await db.flush()
            session = InterviewSession(user_id=user.id, candidate_name='Graph Test', gender='male', age=28,
                job_role='Engineer', level='middle', industry='Technology', company='',
                job_description='Synthetic job', cv_text='Synthetic CV', interviewer='hr')
            db.add(session)
            await db.commit()
            self.sid = session.id

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temporary.cleanup()

    async def run_graph(self, key, nodes, **kwargs):
        return await execute('test', self.sid, key, nodes, session_factory=self.factory, **kwargs)

    async def test_failed_node_resumes_new_graph_without_repeating_completed_calls(self):
        calls = {'parse': 0, 'model': 0, 'persist': 0}
        fail_once = True
        async def parse(ctx):
            calls['parse'] += 1
            return {'private_document_summary': 'DO_NOT_DUPLICATE_IN_CHECKPOINT'}
        async def assess(ctx):
            nonlocal fail_once
            async def model():
                calls['model'] += 1
                observe_usage('synthetic-model', {'prompt_tokens': 17, 'completion_tokens': 3, 'total_tokens': 20}, 12)
                return {'score': 3}
            result = await durable_call('model', {'input': await ctx.result('parse')}, model)
            if fail_once:
                fail_once = False
                raise ValueError('Simulated validation failure: DO_NOT_DUPLICATE_IN_CHECKPOINT')
            return result
        async def persist(ctx):
            calls['persist'] += 1
            return await ctx.result('assess')
        nodes = [('parse', parse), ('assess', assess), ('persist', persist)]
        with self.assertRaises(ValueError):
            await self.run_graph('test:resume', nodes)
        # execute constructs a fresh graph and SQL saver, just like another worker.
        result = await self.run_graph('test:resume', nodes)
        self.assertEqual(result, {'score': 3})
        self.assertEqual(calls, {'parse': 1, 'model': 1, 'persist': 1})
        self.assertEqual(await self.run_graph('test:resume', nodes), result)
        self.assertEqual(calls, {'parse': 1, 'model': 1, 'persist': 1})
        async with self.factory() as db:
            checkpoints = (await db.scalars(select(GraphCheckpoint))).all()
            writes = (await db.scalars(select(GraphWrite))).all()
            self.assertGreater(len(checkpoints), 3)
            serialized = json.dumps([r.checkpoint for r in checkpoints] + [r.value for r in writes])
            self.assertNotIn('DO_NOT_DUPLICATE_IN_CHECKPOINT', serialized)
            self.assertNotIn('private_document_summary', serialized)
            operations = (await db.scalars(select(GraphOperation))).all()
            provider = next(row for row in operations if row.paid)
            self.assertEqual(provider.attempts, 1)
            self.assertEqual(provider.telemetry['attempts'][0]['calls'][0]['usage']['total_tokens'], 20)
            graph = await db.get(GraphExecution, 'test:resume')
            self.assertEqual(graph.status, 'succeeded')
            self.assertIsNone(graph.lease_owner)

    async def test_concurrent_calls_same_thread_have_one_result_and_one_side_effect(self):
        count = 0
        async def node(ctx):
            nonlocal count
            await asyncio.sleep(.08)
            count += 1
            return {'committed': count}
        first, second = await asyncio.gather(self.run_graph('test:concurrent', [('commit', node)]),
                                             self.run_graph('test:concurrent', [('commit', node)]))
        self.assertEqual(first, second)
        self.assertEqual(count, 1)

    async def test_parallel_identical_paid_calls_are_deduplicated_by_input_hash(self):
        count = 0
        async def node(ctx):
            async def model():
                nonlocal count
                count += 1
                await asyncio.sleep(.03)
                return {'value': 4}
            return await asyncio.gather(durable_call('model', {'x': 1}, model), durable_call('model', {'x': 1}, model))
        self.assertEqual(await self.run_graph('test:parallel', [('evaluate', node)]), [{'value': 4}, {'value': 4}])
        self.assertEqual(count, 1)

    async def test_ambiguous_paid_call_requires_explicit_retry_and_records_acknowledgement(self):
        calls = 0
        async def node(ctx):
            async def model():
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise TimeoutError('Provider outcome unavailable')
                return {'ok': True}
            return await durable_call('model', {'stable': True}, model)
        with self.assertRaises(GraphOperationUncertain):
            await self.run_graph('test:uncertain', [('evaluate', node)])
        with self.assertRaises(GraphOperationUncertain):
            await self.run_graph('test:uncertain', [('evaluate', node)])
        self.assertEqual(calls, 1)
        self.assertEqual(await self.run_graph('test:uncertain', [('evaluate', node)], allow_uncertain=True), {'ok': True})
        self.assertEqual(calls, 2)
        async with self.factory() as db:
            operation = await db.scalar(select(GraphOperation).where(GraphOperation.paid.is_(True)))
            self.assertEqual(operation.attempts, 2)
            self.assertTrue(operation.telemetry['attempts'][-1]['ambiguous_retry_acknowledged'])

    async def test_expired_worker_lease_preserves_ambiguous_paid_operation(self):
        async with self.factory() as db:
            db.add(GraphExecution(thread_id='test:crashed', session_id=self.sid, kind='test',
                input_hash=fingerprint(None), plan_hash=fingerprint(['evaluate']), status='running',
                lease_owner='dead-worker', lease_until=now() - timedelta(seconds=1)))
            await db.flush()
            db.add(GraphOperation(thread_id='test:crashed', operation_key='evaluate:paid-request',
                input_hash=fingerprint({'x': 1}), status='running', paid=True, attempts=1))
            await db.commit()
        count = 0
        async def node(ctx):
            async def model():
                nonlocal count
                count += 1
                return 1
            return await ctx.operation('paid-request', {'x': 1}, model, paid=True)
        with self.assertRaises(GraphOperationUncertain):
            await self.run_graph('test:crashed', [('evaluate', node)])
        self.assertEqual(count, 0)

    async def test_operator_grant_is_scoped_audited_and_consumed_once(self):
        calls = {'first': 0, 'other': 0}
        def node_for(which):
            async def node(ctx):
                async def model():
                    calls[which] += 1
                    if calls[which] < 3:
                        raise TimeoutError('Unknown provider outcome')
                    return {'ok': True}
                return await durable_call('model', {'which': which}, model)
            return node
        nodes = [('transcribe', node_for('first'))]
        other_nodes = [('transcribe', node_for('other'))]
        for key, plan in [('test:grant', nodes), ('test:other', other_nodes)]:
            with self.assertRaises(GraphOperationUncertain):
                await self.run_graph(key, plan)
        for thread, sid in [('test:grant', self.sid + 999), ('missing-thread', self.sid)]:
            with self.assertRaises(ValueError):
                await acknowledge_retry(thread, sid, session_factory=self.factory)
        await acknowledge_retry('test:grant', self.sid, session_factory=self.factory)
        await acknowledge_retry('test:grant', self.sid, session_factory=self.factory)  # Idempotent until consumed.
        async with self.factory() as db:
            run = await db.get(GraphExecution, 'test:grant')
            self.assertTrue(run.allow_uncertain_once)
            self.assertEqual(len(run.retry_authorizations), 1)
            self.assertIsNone(run.retry_authorizations[0]['consumed_at'])
        with self.assertRaises(GraphOperationUncertain):
            await self.run_graph('test:other', other_nodes)
        self.assertEqual(calls['other'], 1)  # A different thread never inherits the grant.
        with self.assertRaises(GraphOperationUncertain):
            await self.run_graph('test:grant', nodes)
        self.assertEqual(calls['first'], 2)
        async with self.factory() as db:
            run = await db.get(GraphExecution, 'test:grant')
            self.assertFalse(run.allow_uncertain_once)
            self.assertIsNotNone(run.retry_authorizations[0]['consumed_at'])
        with self.assertRaises(GraphOperationUncertain):
            await self.run_graph('test:grant', nodes)
        self.assertEqual(calls['first'], 2)  # Failure does not replenish authorization.
        await acknowledge_retry('test:grant', self.sid, session_factory=self.factory)
        self.assertEqual(await self.run_graph('test:grant', nodes), {'ok': True})
        self.assertEqual(calls['first'], 3)
        async with self.factory() as db:
            run = await db.get(GraphExecution, 'test:grant')
            self.assertFalse(run.allow_uncertain_once)
            self.assertEqual(len(run.retry_authorizations), 2)
            self.assertTrue(all(item['possible_charge_acknowledged'] and item['consumed_at'] for item in run.retry_authorizations))

    async def test_operator_cannot_authorize_retry_while_worker_lease_is_active(self):
        async with self.factory() as db:
            db.add(GraphExecution(thread_id='test:active-grant', session_id=self.sid, kind='test',
                input_hash=fingerprint(None), plan_hash=fingerprint(['evaluate']), status='running',
                lease_owner='active-worker', lease_until=now() + timedelta(seconds=120)))
            await db.flush()
            db.add(GraphOperation(thread_id='test:active-grant', operation_key='evaluate:paid-request',
                input_hash=fingerprint({'x': 1}), status='running', paid=True, attempts=1))
            await db.commit()
        with self.assertRaises(GraphBusy):
            await acknowledge_retry('test:active-grant', self.sid, session_factory=self.factory)
        async with self.factory() as db:
            run = await db.get(GraphExecution, 'test:active-grant')
            self.assertFalse(run.allow_uncertain_once)
            self.assertEqual(run.retry_authorizations, [])

    async def test_two_processes_share_database_lease_without_duplicate_commit(self):
        # Separate interpreters cannot share the in-process asyncio lock.
        source = '''
import asyncio,sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.graphs.runtime import execute
from app.models import InterviewEvent
async def main():
    engine=create_async_engine(sys.argv[1]); factory=async_sessionmaker(engine,expire_on_commit=False)
    Path(sys.argv[3]).write_text('ready')
    while not Path(sys.argv[4]).exists():await asyncio.sleep(.02)
    async def commit(ctx):
        await asyncio.sleep(.15)
        async with factory() as db:
            db.add(InterviewEvent(session_id=int(sys.argv[2]),event_key='one-process-commit',kind='test',payload={}))
            await db.commit()
        return {'committed':True}
    value=await execute('test',int(sys.argv[2]),'test:processes',[('commit',commit)],session_factory=factory)
    assert value=={'committed':True}
    await engine.dispose()
asyncio.run(main())
'''
        root = Path(self.temporary.name)
        go = root / 'start'
        children = []
        try:
            for index in range(2):
                child = await asyncio.create_subprocess_exec(sys.executable, '-c', source,
                    self.engine.url.render_as_string(hide_password=False), str(self.sid), str(root / f'ready{index}'), str(go),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                children.append(child)
            for _ in range(400):
                if all((root / f'ready{index}').exists() for index in range(2)):
                    break
                await asyncio.sleep(.025)
            self.assertTrue(all((root / f'ready{index}').exists() for index in range(2)))
            go.write_text('go')
            for child in children:
                _, error = await asyncio.wait_for(child.communicate(), 35)
                self.assertEqual(child.returncode, 0, error.decode())
        finally:
            for child in children:
                if child.returncode is None:
                    child.kill()
                    await child.wait()
        async with self.factory() as db:
            rows = (await db.scalars(select(InterviewEvent).where(InterviewEvent.session_id == self.sid))).all()
            self.assertEqual(len(rows), 1)
            operation = await db.get(GraphOperation, ('test:processes', 'node:commit'))
            self.assertEqual(operation.attempts, 1)

    async def test_process_crash_after_paid_result_reuses_it_on_restart(self):
        source = '''
import asyncio,os,sys
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.graphs.runtime import execute,durable_call
from app.models import InterviewEvent
async def main():
    engine=create_async_engine(sys.argv[1]); factory=async_sessionmaker(engine,expire_on_commit=False)
    async def node(ctx):
        async def model():
            async with factory() as db:
                db.add(InterviewEvent(session_id=int(sys.argv[2]),event_key='paid-once',kind='test',payload={}))
                await db.commit()
            return {'score':4}
        await durable_call('model',{'x':1},model)
        os._exit(79)
    await execute('test',int(sys.argv[2]),'test:restart',[('evaluate',node)],session_factory=factory)
asyncio.run(main())
'''
        child = await asyncio.create_subprocess_exec(sys.executable, '-c', source, self.engine.url.render_as_string(hide_password=False), str(self.sid),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, error = await asyncio.wait_for(child.communicate(), 20)
        self.assertEqual(child.returncode, 79, error.decode())
        async with self.factory() as db:
            execution = await db.get(GraphExecution, 'test:restart')
            # Simulate passage of the crashed worker's lease interval.
            execution.lease_until = now() - timedelta(seconds=1)
            await db.commit()
        async def resumed(ctx):
            async def should_never_repeat():
                raise AssertionError('Completed paid call was repeated')
            return await durable_call('model', {'x': 1}, should_never_repeat)
        self.assertEqual(await self.run_graph('test:restart', [('evaluate', resumed)]), {'score': 4})
        async with self.factory() as db:
            rows = (await db.scalars(select(InterviewEvent).where(InterviewEvent.session_id == self.sid))).all()
            self.assertEqual(len(rows), 1)

    async def test_versioned_thread_rejects_changed_input_or_plan(self):
        async def node(ctx):
            return {'ok': True}
        await self.run_graph('test:version', [('first', node)], input_data={'version': 1})
        with self.assertRaises(GraphInputMismatch):
            await self.run_graph('test:version', [('first', node)], input_data={'version': 2})
        with self.assertRaises(GraphInputMismatch):
            await self.run_graph('test:version', [('renamed', node)], input_data={'version': 1})

    async def test_json_only_saver_roundtrip_history_and_delete(self):
        from app.graphs.checkpoint import SQLAlchemySaver, JsonOnlySerializer
        async def node(ctx):
            return None
        await self.run_graph('test:saver', [('first', node)])
        saver = SQLAlchemySaver(self.factory)
        config = {'configurable': {'thread_id': 'test:saver'}}
        latest = await saver.aget_tuple(config)
        self.assertEqual(latest.checkpoint['channel_values']['completed_node'], 'first')
        history = [item async for item in saver.alist(config, limit=2)]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].config, latest.config)
        with self.assertRaises(TypeError):
            JsonOnlySerializer().dumps_typed(object())
        with self.assertRaises(ValueError):
            JsonOnlySerializer().loads_typed(('pickle', b'unsafe'))
        await saver.adelete_thread('test:saver')
        self.assertIsNone(await saver.aget_tuple(config))
