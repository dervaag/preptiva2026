from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import event
from app.config import settings, ROOT

(ROOT / 'data').mkdir(exist_ok=True)
engine = create_async_engine(settings.db_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
if settings.db_url.startswith('sqlite'):
    @event.listens_for(engine.sync_engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')


async def init_db():
    from app.models import Base
    from app.graphs import models as graph_models  # Register additive persistence tables.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as db:
        yield db
