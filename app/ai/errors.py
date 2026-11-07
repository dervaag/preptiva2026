"""Safe provider diagnostics: never pass remote response bodies or headers to users."""
import httpx
from app.log import emit


class ProviderError(RuntimeError):
    pass


async def provider_post(client, url, provider, **kwargs):
    try:
        return await client.post(url, **kwargs)
    except httpx.TimeoutException as exc:
        emit('provider_transport_error', provider=provider, error_type=type(exc).__name__)
        raise ProviderError(f'{provider}: waktu tunggu layanan habis. Coba kembali.') from exc
    except httpx.RequestError as exc:
        emit('provider_transport_error', provider=provider, error_type=type(exc).__name__)
        raise ProviderError(f'{provider}: koneksi gagal. Periksa jaringan lalu coba kembali.') from exc


def check_response(response, provider):
    if response.is_success:
        return
    status = response.status_code
    code = ''
    try:
        body = response.json()
        detail = body.get('error') or body.get('detail') or {}
        if isinstance(detail, dict):
            candidate = detail.get('code') or detail.get('status') or ''
            if candidate in ('insufficient_quota', 'quota_exceeded', 'voice_not_found', 'model_not_found', 'invalid_api_key', 'missing_permissions'):
                code = candidate
    except (ValueError, AttributeError):
        pass
    emit('provider_error', provider=provider, status=status, code=code or 'unspecified')
    if code in ('insufficient_quota', 'quota_exceeded'):
        reason = 'kuota/kredit akun tidak mencukupi. Periksa saldo dan batas pemakaian akun.'
    elif status == 401:
        reason = 'API key ditolak. Periksa kredensial di .env dan restart server.'
    elif status == 403 or code == 'missing_permissions':
        reason = 'izin API key atau paket akun tidak mengizinkan operasi ini.'
    elif status == 404 or code in ('voice_not_found', 'model_not_found'):
        reason = 'model atau voice ID tidak ditemukan atau tidak dapat diakses akun ini.'
    elif status == 429:
        reason = 'batas permintaan tercapai. Tunggu sebentar lalu coba kembali.'
    elif status >= 500:
        reason = 'layanan sedang bermasalah. Coba kembali beberapa saat lagi.'
    else:
        reason = 'permintaan ditolak. Periksa model, format audio, dan pengaturan provider.'
    raise ProviderError(f'{provider}: {reason}')
