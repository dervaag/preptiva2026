import asyncio
import hashlib
import json
from uuid import uuid4
import httpx
from app.config import settings, ROOT
from app.storage import audio_dir
from app.log import emit
from app.ai.errors import check_response, provider_post

tts_semaphore = asyncio.Semaphore(2)


async def optional_synthesize(*args, timeout=None, **kwargs):
    from app.ai.errors import ProviderError
    try:
        return await asyncio.wait_for(synthesize(*args, **kwargs), timeout=timeout)
    except (ProviderError, asyncio.TimeoutError, RuntimeError) as exc:
        emit('audio_fallback', error_type=type(exc).__name__)
        return None


def require_credentials(persona):
    if not settings.openai_api_key or not settings.elevenlabs_api_key or not getattr(settings, f'elevenlabs_voice_{persona}'):
        raise ValueError('Isi OPENAI_API_KEY, ELEVENLABS_API_KEY, dan voice ID persona di .env untuk memulai wawancara.')


async def synthesize(text, persona, uuid, name, live=False):
    voice = getattr(settings, f'elevenlabs_voice_{persona}')
    model = settings.elevenlabs_model_live if live else settings.elevenlabs_model_prepared
    payload = {'text': text, 'model_id': model}
    # Multilingual v2 does not support language_code; do not force it there.
    if settings.elevenlabs_language_code and model.endswith('_v2_5'):
        payload['language_code'] = settings.elevenlabs_language_code
    key = hashlib.sha256(json.dumps({'provider': 'elevenlabs', 'version': 2, 'voice': voice,
        'output_format': settings.elevenlabs_output_format, **payload}, sort_keys=True).encode()).hexdigest()
    cache = ROOT / 'data/tts_cache' / (key + '.mp3')
    target = audio_dir(uuid) / name
    if settings.tts_cache and cache.exists():
        target.write_bytes(cache.read_bytes())
        return f'/api/sessions/{uuid}/audio/{name}'
    async with tts_semaphore:
        async with httpx.AsyncClient(timeout=settings.tts_live_timeout_sec if live else settings.tts_prepared_timeout_sec) as client:
            for attempt in range(4):
                response = await provider_post(client, f'https://api.elevenlabs.io/v1/text-to-speech/{voice}', 'ElevenLabs',
                    headers={'xi-api-key': settings.elevenlabs_api_key},
                    params={'output_format': settings.elevenlabs_output_format}, json=payload)
                if response.status_code == 429 and attempt < 3:
                    await asyncio.sleep(min(8, 2 ** attempt))
                    continue
                check_response(response, 'ElevenLabs')
                if not response.content:
                    raise RuntimeError('ElevenLabs mengembalikan audio kosong.')
                target.write_bytes(response.content)
                if settings.tts_cache:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    temporary = cache.with_suffix(f'.{uuid4().hex}.tmp')
                    temporary.write_bytes(response.content)
                    temporary.replace(cache)
                emit('tts_usage', provider='elevenlabs', model=model, chars=len(text))
                return f'/api/sessions/{uuid}/audio/{name}'


async def transcribe(content, filename, language):
    async with httpx.AsyncClient(timeout=90) as client:
        response = await provider_post(client, 'https://api.openai.com/v1/audio/transcriptions', 'OpenAI STT',
            headers={'Authorization': f'Bearer {settings.openai_api_key}'},
            data={'model': settings.stt_model, 'prompt': f'The interview language is {language}. Preserve original code-switching, names and technical terms. Do not translate.'},
            files={'file': (filename, content)})
        check_response(response, 'OpenAI STT')
        return response.json()['text'].strip()


def stream_cache(text, persona):
    voice = getattr(settings, f'elevenlabs_voice_{persona}')
    key = hashlib.sha256(json.dumps({'v':1, 'voice':voice, 'model':settings.elevenlabs_model_live,
        'format':settings.elevenlabs_output_format,'language':settings.elevenlabs_language_code,'text':text},sort_keys=True).encode()).hexdigest()
    return ROOT / 'data/tts_stream_cache' / (key+'.mp3')


async def stream_audio(text, persona):
    from app.services.locks import local_lock
    target = stream_cache(text, persona)
    temporary = target.with_suffix('.'+uuid4().hex+'.tmp')
    voice = getattr(settings, f'elevenlabs_voice_{persona}')
    payload = {'text':text, 'model_id':settings.elevenlabs_model_live}
    if settings.elevenlabs_language_code and settings.elevenlabs_model_live.endswith('_v2_5'):
        payload['language_code'] = settings.elevenlabs_language_code
    try:
        async with local_lock(('stream-tts', str(target))):
            if settings.tts_cache and target.exists():
                with target.open('rb') as file:
                    while chunk := file.read(16384):
                        yield chunk
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            async with tts_semaphore, httpx.AsyncClient(timeout=settings.tts_live_timeout_sec) as client:
                async with client.stream('POST',f'https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream',
                        headers={'xi-api-key':settings.elevenlabs_api_key},params={'output_format':settings.elevenlabs_output_format},json=payload) as response:
                    if response.status_code != 200:
                        # Do not log provider bodies or headers.
                        emit('tts_stream_failed', status=response.status_code)
                        return
                    size = 0
                    with temporary.open('wb') as file:
                        temporary.chmod(0o600)
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 16*1024*1024:
                                raise RuntimeError('Voice response too large.')
                            file.write(chunk)
                            yield chunk
                    if size and settings.tts_cache:
                        temporary.replace(target)
                    emit('tts_stream_completed', chars=len(text), bytes=size)
    except (httpx.HTTPError, RuntimeError) as exc:
        emit('tts_stream_failed', error_type=type(exc).__name__)
    finally:
        temporary.unlink(missing_ok=True)
