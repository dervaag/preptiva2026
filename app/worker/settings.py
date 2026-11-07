from arq.connections import RedisSettings
from arq import cron
from app.config import settings
from app.db import init_db
from app.worker.tasks import prepare_session, finalize_session, resume_graph_turn, recover_graph_jobs


async def startup(ctx):
    await init_db()
    await recover_graph_jobs(ctx)


class WorkerSettings:
    functions = [prepare_session, finalize_session, resume_graph_turn]
    cron_jobs = [cron(recover_graph_jobs, minute=None, second=15)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url or 'redis://localhost:6379/0')
    on_startup = startup
    job_timeout = 900
    health_check_interval = 30
