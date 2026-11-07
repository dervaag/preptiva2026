import asyncio
from app.config import settings

tasks = set()


async def enqueue(name, session_id):
    if settings.redis_url:
        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job(name, session_id)
        finally:
            await pool.aclose()
    else:
        from app.worker import tasks as worker
        task = asyncio.create_task(getattr(worker, name)({}, session_id))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
