"""Create an account without putting its password in source code or arguments."""
import argparse
import asyncio
import getpass
import json
import os
import sys

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.api.auth import check_new_password
from app.db import SessionLocal, engine, init_db
from app.models import User
from app.security import hash_password, verify_password
from app.security_models import AuthSession
from app.services.login_limits import delete_account_limits


class AccountInput(BaseModel):
    email: EmailStr = Field(max_length=190)
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator('password')
    @classmethod
    def valid_password(cls, value):
        return check_new_password(value)


async def seed_account(email, password, *, name=None, reset_password=False):
    email = email.strip().lower()
    data = AccountInput(email=email, name=(name or email.split('@')[0]).strip(), password=password)
    hashed = await asyncio.to_thread(hash_password, data.password)
    async with SessionLocal() as db:
        insert = postgres_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
        created = (await db.execute(insert(User).values(email=str(data.email), name=data.name,
            password_hash=hashed, gender=None, age=None).on_conflict_do_nothing(
                index_elements=[User.email]).returning(User.id))).scalar_one_or_none()
        if created is not None:
            await db.commit()
            return {'status': 'created', 'id': created, 'email': str(data.email)}
        user = await db.scalar(select(User).where(User.email == str(data.email)).with_for_update())
        if await asyncio.to_thread(verify_password, data.password, user.password_hash):
            await db.commit()
            return {'status': 'existing', 'id': user.id, 'email': user.email}
        if not reset_password:
            result = {'status': 'existing_password_differs', 'id': user.id, 'email': user.email,
                      'changed': False}
            await db.rollback()
            return result
        user.password_hash = hashed
        await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        await delete_account_limits(user, db)
        await db.commit()
        return {'status': 'password_reset', 'id': user.id, 'email': user.email,
                'sessions_revoked': True}


def read_password(arguments):
    if arguments.password_stdin:
        return sys.stdin.readline(1024).rstrip('\r\n')
    password = os.environ.pop('PREPTIVA_SEED_PASSWORD', None)
    if password is not None:
        return password
    if not sys.stdin.isatty():
        raise ValueError('Gunakan terminal interaktif, PREPTIVA_SEED_PASSWORD, atau --password-stdin.')
    password = getpass.getpass('Password akun: ')
    if password != getpass.getpass('Ulangi password: '):
        raise ValueError('Konfirmasi password tidak sesuai.')
    return password


async def run(arguments, password):
    try:
        # Validate before opening/migrating a database. Never print a Pydantic
        # ValidationError: it can embed the supplied password in its input.
        AccountInput(email=arguments.email.strip().lower(),
            name=(arguments.name or arguments.email.split('@')[0]).strip(), password=password)
        await init_db()
        result = await seed_account(arguments.email, password, name=arguments.name,
                                    reset_password=arguments.reset_password)
        print(json.dumps(result))
        return 2 if result['status'] == 'existing_password_differs' else 0
    except ValidationError:
        print(json.dumps({'status': 'invalid_input', 'detail': 'Email, nama, atau format password tidak valid.'}))
        return 1
    except Exception as exc:
        # SQL exceptions can include credential parameters. Return only a type.
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        return 1
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--name')
    parser.add_argument('--password-stdin', action='store_true', help='Read one password line from standard input.')
    parser.add_argument('--reset-password', action='store_true',
                        help='Explicitly replace a different existing password and revoke its login.')
    arguments = parser.parse_args()
    try:
        password = read_password(arguments)
    except (ValueError, EOFError):
        print(json.dumps({'status': 'password_required', 'detail': 'Password dan konfirmasi diperlukan.'}))
        return 1
    return asyncio.run(run(arguments, password))


if __name__ == '__main__':
    raise SystemExit(main())
