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
    from app import security_models, privacy_models  # Additive auth and deletion journals.
    if engine.dialect.name == 'sqlite':
        # Dedicated connection: migration toggles foreign_keys only outside its
        # atomic transaction, then restores it before this connection is reused.
        from app.services.sqlite_identity import initialize_sqlite
        async with engine.connect() as connection:
            await connection.run_sync(initialize_sqlite, Base.metadata)
    else:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as db:
        yield db
