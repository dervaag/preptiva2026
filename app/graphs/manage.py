"""Local operator recovery and metadata-only tracing. Never prints candidate content."""
import argparse
import asyncio
import json
from collections import Counter
from sqlalchemy import select
from app.db import SessionLocal, engine
from app.models import InterviewSession, GraphTurnInput
from app.graphs.models import GraphExecution, GraphOperation
from app.graphs.policy import enabled
from app.graphs.topology import plan_nodes, matches_plan


async def list_sessions(limit=10):
    if not 1 <= limit <= 100:
        raise ValueError('Batas daftar sesi harus 1–100.')
    async with SessionLocal() as db:
        rows = (await db.scalars(select(InterviewSession).where(
            InterviewSession.script['runtime']['engine'].as_string() == 'langgraph')
            .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc()).limit(limit))).all()
        return {'sessions': [{'session_id': row.uuid, 'status': row.status,
            'graph_version': row.script.get('runtime', {}).get('graph_version'),
            'created_at': row.created_at.isoformat() + 'Z'} for row in rows]}


async def inspect(session_uuid):
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == session_uuid))
        if not session or not enabled(session):
            raise ValueError('Sesi graph tidak ditemukan.')
        runs = list((await db.scalars(select(GraphExecution).where(GraphExecution.session_id == session.id)
            .order_by(GraphExecution.created_at, GraphExecution.thread_id))).all())
        roles = session.script.get('settings', {}).get('panel') or [session.interviewer]
        result = []
        for run in runs:
            operations = list((await db.scalars(select(GraphOperation).where(GraphOperation.thread_id == run.thread_id))).all())
            result.append({'thread_id': run.thread_id, 'kind': run.kind, 'status': run.status,
                'plan_nodes': plan_nodes(run.kind, roles), 'plan_matches': matches_plan(run.kind, roles, run.plan_hash),
                'attempts': run.attempts, 'error_type': run.error_type,
                'retry_authorizations': getattr(run, 'retry_authorizations', []),
                'allow_uncertain_once': getattr(run, 'allow_uncertain_once', False),
                'operations': [{'key': op.operation_key, 'status': op.status, 'paid': op.paid,
                    'attempts': op.attempts, 'duration_ms': op.duration_ms, 'error_type': op.error_type,
                    'telemetry': op.telemetry} for op in operations]})
        return {'session_id': session.uuid, 'status': session.status, 'executions': result,
            'operation_counts': dict(Counter(op['status'] for run in result for op in run['operations']))}


async def retry(session_uuid, thread_id, acknowledge=False):
    await_resubmit = False
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == session_uuid).with_for_update())
        run = await db.get(GraphExecution, thread_id)
        if not session or not enabled(session) or not run or run.session_id != session.id:
            raise ValueError('Eksekusi bukan milik sesi graph ini.')
        if run.kind == 'prepare':
            if session.status == 'preparation_failed': session.status = 'preparing'
            if session.status not in ('preparing', 'ready'): raise ValueError('Sesi sudah melewati tahap persiapan.')
        elif run.kind == 'finalize':
            if session.status == 'evaluation_failed': session.status = 'scoring'
            if session.status not in ('scoring', 'done'): raise ValueError('Sesi tidak sedang menunggu penilaian.')
        elif run.kind == 'turn':
            from app.graphs.turn import thread_key
            if session.status != 'running' or session.script.get('checkpoint', {}).get('phase') == 'interrupted':
                raise ValueError('Pertanyaan terhenti atau sesi ditutup; Retry/Next tetap dilakukan pengguna di browser.')
            inputs = list((await db.scalars(select(GraphTurnInput).where(GraphTurnInput.session_id == session.id))).all())
            saved = next((item for item in inputs if thread_id == thread_key(session.id, item.question_id, item.attempt, item.input_hash)), None)
            if not saved:
                if not acknowledge:
                    raise ValueError('Transkrip belum tersimpan; retry ambigu memerlukan --acknowledge-possible-charge lalu pengguna kirim ulang audio yang sama.')
                await_resubmit = True
        else:
            raise ValueError('Jenis graph tidak dikenali.')
        session.error_message = None
        sid = session.id
        await db.commit()
    if await_resubmit:
        from app.graphs.runtime import acknowledge_retry
        await acknowledge_retry(thread_id, sid, session_factory=SessionLocal)
        return {**await inspect(session_uuid), 'awaiting_same_audio_resubmission': True}
    try:
        if run.kind == 'prepare':
            from app.graphs.preparation import prepare
            await prepare(sid, allow_uncertain=acknowledge)
        elif run.kind == 'finalize':
            from app.graphs.finalization import finalize
            await finalize(sid, allow_uncertain=acknowledge)
        else:
            from app.graphs.turn import resume
            await resume(saved.id, allow_uncertain=acknowledge)
    except Exception:
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, sid)
            expected = 'preparing' if run.kind == 'prepare' else 'scoring'
            if session and run.kind in ('prepare', 'finalize') and session.status == expected:
                session.status = 'preparation_failed' if run.kind == 'prepare' else 'evaluation_failed'
                session.error_message = 'Pemulihan belum selesai. Data tetap tersimpan; periksa status eksekusi.'
                await db.commit()
        raise
    return await inspect(session_uuid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['list', 'inspect', 'retry'])
    parser.add_argument('--session', help='Owned deployment session UUID')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--thread', help='Exact thread ID from inspect')
    parser.add_argument('--acknowledge-possible-charge', action='store_true',
                        help='Explicitly permit repeating provider calls whose previous outcome is uncertain')
    args = parser.parse_args()
    if args.action != 'list' and not args.session: parser.error('inspect/retry requires --session')
    if args.action == 'retry' and not args.thread: parser.error('retry requires --thread')
    async def run():
        try:
            if args.action == 'list': result = await list_sessions(args.limit)
            elif args.action == 'inspect': result = await inspect(args.session)
            else: result = await retry(args.session, args.thread, args.acknowledge_possible_charge)
            print(json.dumps(result, indent=2))
        except Exception as exc:
            print(json.dumps({'ok': False, 'error_type': type(exc).__name__,
                'detail': ('Pemulihan belum selesai. Periksa inspect; operasi ambigu memerlukan '
                           '--acknowledge-possible-charge.' if args.action == 'retry' else
                           'Periksa UUID sesi, jenis graph, serta database yang dipilih.')}))
            raise SystemExit(1)
        finally:
            await engine.dispose()
    asyncio.run(run())


if __name__ == '__main__':
    main()
