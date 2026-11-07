import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text, select
from app.config import settings, ROOT
from app.db import init_db, SessionLocal
from app.models import User
from app.api import auth, sessions, dashboard, voice
from app.log import request_var
from app.assets import asset_url


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield
    from app.jobs import tasks
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title='Preptiva — AI Interview Simulator', version='0.1.0', lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie='isim_session',
                   same_site='lax', https_only=settings.cookie_secure, max_age=60*60*24*7)


@app.middleware('http')
async def request_context(request: Request, call_next):
    rid = uuid4().hex
    token = request_var.set(rid)
    try:
        # Cookies are ambient credentials: reject browser cross-origin mutations.
        origin = request.headers.get('origin')
        if request.method in ('POST','PUT','PATCH','DELETE') and (request.headers.get('sec-fetch-site') == 'cross-site' or
            (origin and urlsplit(origin).netloc != request.headers.get('host') and origin != settings.public_origin)):
            return JSONResponse({'detail': 'Cross-origin request ditolak.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Request-ID'] = rid
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=(self)'
        if request.url.path.startswith('/api'):
            response.headers.setdefault('Cache-Control', 'no-store')
        return response
    finally:
        request_var.reset(token)


app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(dashboard.router)
app.include_router(voice.router)
app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')
templates = Jinja2Templates(directory=ROOT / 'app/templates')
templates.env.globals['asset_url'] = asset_url


@app.get('/health')
async def health():
    try:
        async with SessionLocal() as db:
            await db.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = None
    if settings.redis_url:
        from arq import create_pool
        from arq.connections import RedisSettings
        try:
            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            redis_ok = bool(await pool.ping())
            await pool.aclose()
        except Exception:
            redis_ok = False
    return JSONResponse({'ok': db_ok and redis_ok is not False, 'version':'0.1.0', 'db':db_ok, 'redis':redis_ok, 'ai_mock':False},
                        status_code=200 if db_ok and redis_ok is not False else 503)


@app.get('/dev-login')
async def dev_login(request: Request):
    if settings.app_env != 'development':
        return JSONResponse({'detail':'Not found'}, status_code=404)
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == 'demo@interview.local'))
    if not user:
        return RedirectResponse('/login?seed=1', status_code=303)
    request.session.clear()
    request.session['user_id'] = user.id
    return RedirectResponse('/simulasi/baru', status_code=303)


@app.get('/')
@app.get('/{page:path}', include_in_schema=False)
async def page(request: Request, page: str = ''):
    allowed = {'': 'dashboard', 'dashboard':'dashboard', 'login':'login', 'register':'register',
               'simulasi/baru':'form', 'riwayat':'history'}
    kind = allowed.get(page)
    sid = ''
    if page.startswith('sesi/'):
        parts = page.split('/')
        if len(parts) == 3 and parts[2] in ('ruang','hasil'):
            sid = parts[1]
            kind = 'room' if parts[2] == 'ruang' else 'result'
    if not kind:
        return JSONResponse({'detail':'Not found'}, status_code=404)
    user = None
    async with SessionLocal() as db:
        if request.session.get('user_id'):
            user = await db.get(User, request.session['user_id'])
        if kind not in ('login', 'register') and not user:
            return RedirectResponse('/login', status_code=303)
        if sid:
            from app.models import InterviewSession
            owned = await db.scalar(select(InterviewSession.id).where(InterviewSession.uuid == sid, InterviewSession.user_id == user.id))
            if not owned:
                return JSONResponse({'detail':'Sesi tidak ditemukan.'}, status_code=404)
    configured = bool(settings.openai_api_key and settings.elevenlabs_api_key)
    return templates.TemplateResponse(request=request, name='app.html', context={
        'page':kind, 'sid':sid, 'user':user, 'development':settings.app_env == 'development', 'configured':configured})
