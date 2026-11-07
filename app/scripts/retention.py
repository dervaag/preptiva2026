"""Preview retention by default; --apply deletes expired content and retries cleanup."""
import argparse
import asyncio
import json
from app.db import engine
from app.services.privacy import run_retention


async def run(apply):
    try:
        print(json.dumps(await run_retention(dry_run=not apply), indent=2))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__, 'retry_pending': True}))
        raise SystemExit(1)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply the configured retention policy.')
    arguments = parser.parse_args()
    asyncio.run(run(arguments.apply))


if __name__ == '__main__':
    main()
