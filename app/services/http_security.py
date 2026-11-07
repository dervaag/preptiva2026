"""Browser request protections; never trust forwarded hosts supplied by clients."""
from urllib.parse import urlsplit
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from app.config import settings


class RequestBodyLimitMiddleware:
    """Bound uploads before multipart parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        lengths = [value for key, value in scope.get('headers', []) if key == b'content-length']
        try:
            declared = int(lengths[0]) if len(lengths) == 1 else 0
            if len(lengths) > 1 or declared < 0:
                raise ValueError()
        except ValueError:
            return await JSONResponse({'detail': 'Ukuran permintaan tidak valid.'}, status_code=400)(scope, receive, send)
        if declared > settings.max_request_bytes:
            return await JSONResponse({'detail': 'Ukuran permintaan melebihi batas.'}, status_code=413)(scope, receive, send)
        consumed = 0
        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message['type'] == 'http.request':
                consumed += len(message.get('body', b''))
                if consumed > settings.max_request_bytes:
                    raise HTTPException(413, 'Ukuran permintaan melebihi batas.')
            return message
        return await self.app(scope, limited_receive, send)


def trusted_browser_origin(request, value, *, referer=False):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.netloc
                or parsed.username is not None or parsed.password is not None
                or (not referer and (parsed.path or parsed.query or parsed.fragment))):
            return False
        origin = f'{parsed.scheme}://{parsed.netloc}'
        scheme = 'https' if settings.cookie_secure else {'ws': 'http', 'wss': 'https'}.get(request.url.scheme, request.url.scheme)
        return origin in {f'{scheme}://{request.headers.get("host", "")}', settings.public_origin}
    except ValueError:
        return False


def unsafe_browser_request(request):
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return False
    site = request.headers.get('sec-fetch-site', '')
    if site == 'cross-site':
        return True
    origin = request.headers.get('origin')
    if origin is not None:
        return not trusted_browser_origin(request, origin)
    referer = request.headers.get('referer')
    if referer is not None:
        return not trusted_browser_origin(request, referer, referer=True)
    # A sibling subdomain is same-site, but is not an authorized application origin.
    # Non-browser API clients may omit browser headers and must still authenticate.
    return site in ('same-site', 'none')


def protect_response(response, path, request_id):
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=(self)'
    response.headers['Content-Security-Policy'] = "base-uri 'self'; object-src 'none'; frame-ancestors 'none'"
    if settings.app_env == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    if path.startswith('/api') or 'text/html' in response.headers.get('content-type', ''):
        response.headers['Cache-Control'] = 'no-store'
    return response
