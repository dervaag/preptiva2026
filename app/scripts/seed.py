import asyncio
import sys
from sqlalchemy import select
from app.db import init_db, SessionLocal
from app.models import User
from app.security import hash_password
from app.config import settings


async def main():
    if settings.app_env == 'production' and len(sys.argv) < 3:
        raise SystemExit('Production: supply email and password explicitly.')
    email = sys.argv[1] if len(sys.argv) > 1 else 'demo@interview.local'
    password = sys.argv[2] if len(sys.argv) > 2 else 'demo1234'
    await init_db()
    async with SessionLocal() as db:
        if not await db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, name='Demo User', gender='male', age=28, password_hash=hash_password(password)))
            await db.commit()
    print('Account ready:', email)


if __name__ == '__main__':
    asyncio.run(main())
