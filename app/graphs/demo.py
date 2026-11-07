"""Run real Preptiva graphs with synthetic providers in a new, isolated database."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DEMO_UUID = '00000000-0000-4000-8000-000000000001'


async def run(directory):
    from validation.orchestration_benchmark import sample
    result = await sample('langgraph', 3, directory)
    from app.graphs.manage import inspect
    from app.db import engine
    try:
        inspection = await inspect(DEMO_UUID)
    finally:
        await engine.dispose()
    if not result['ok'] or result['actual_provider_requests'] != 0 or not all(
            run['plan_matches'] for run in inspection['executions']):
        raise RuntimeError('Demo graph belum berhasil atau rencana node tidak cocok.')
    destination = directory / 'inspection.json'
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        json.dump(inspection, file, indent=2)
        file.write('\n')
    return {'ok': True, 'synthetic': True, 'session_uuid': DEMO_UUID,
            'database_url': 'sqlite+aiosqlite:///' + str(directory / 'benchmark.db'),
            'inspection_file': str(destination), 'graph_executions': result['graph_execution_count'],
            'actual_provider_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure-studio', action='store_true',
                        help='Point .env.studio at this new synthetic database.')
    arguments = parser.parse_args()
    base = ROOT / 'data/studio-demo'
    if (ROOT / 'data').is_symlink() or base.is_symlink():
        raise SystemExit('Direktori demo tidak boleh symlink.')
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=base))
    try:
        result = asyncio.run(run(directory))
        if arguments.configure_studio:
            from dotenv import set_key
            destination = ROOT / '.env.studio'
            if destination.is_symlink():
                raise ValueError('Environment Studio tidak boleh symlink.')
            if not destination.exists():
                descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'w') as file:
                    file.write((ROOT / '.env.studio.example').read_text())
            destination.chmod(0o600)
            set_key(str(destination), 'DATABASE_URL', result['database_url'], quote_mode='always')
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__, 'synthetic': True}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
