from arq.connections import RedisSettings
from app.config import settings
from app.db import init_db
from app.worker.tasks import prepare_session, finalize_session


async def startup(ctx):
    await init_db()


class WorkerSettings:
    functions = [prepare_session, finalize_session]
    redis_settings = RedisSettings.from_dsn(settings.redis_url or 'redis://localhost:6379/0')
    on_startup = startup
    job_timeout = 900
