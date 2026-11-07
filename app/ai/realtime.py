"""OpenAI transcription transport; speech never creates interview turns directly."""
import asyncio
import base64
import json
from contextlib import asynccontextmanager
from websockets.asyncio.client import connect
from app.config import settings


def configuration(language, vad=True):
    return {'type': 'session.update', 'session': {'type': 'transcription', 'audio': {'input': {
        'format': {'type': 'audio/pcm', 'rate': 24000},
        'transcription': {'model': settings.stt_model,
            'prompt': f'Interview in {language} with Indonesian/English code-switching. Preserve the original language, names and numbers; do not translate.'},
        'noise_reduction': {'type': 'near_field'},
        'turn_detection': {'type': 'server_vad', 'threshold': settings.vad_threshold,
            'prefix_padding_ms': 300, 'silence_duration_ms': settings.vad_silence_ms} if vad else None}}}}


@asynccontextmanager
async def connection(language):
    async with connect('wss://api.openai.com/v1/realtime?intent=transcription',
            additional_headers={'Authorization': f'Bearer {settings.openai_api_key}'},
            open_timeout=15, max_size=1024*1024, max_queue=16) as socket:
        await socket.send(json.dumps(configuration(language)))
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), 15))
            if event['type'] == 'error':
                raise RuntimeError('Realtime transcription configuration rejected.')
            if event['type'] == 'session.updated':
                break
        yield socket


class Transcript:
    def __init__(self):
        self.order, self.finals, self.partial = [], {}, {}

    def feed(self, event):
        kind, item = event.get('type'), event.get('item_id')
        if kind == 'input_audio_buffer.committed' and item not in self.order:
            self.order.append(item)
        elif kind == 'conversation.item.input_audio_transcription.delta':
            self.partial[item] = self.partial.get(item, '') + event.get('delta', '')
        elif kind == 'conversation.item.input_audio_transcription.completed':
            self.finals[item] = event.get('transcript', '')
        if len(self.text()) > 8000 or len(self.order) > 150:
            raise ValueError('Transkrip melampaui batas jawaban.')

    def text(self):
        order = self.order + [key for key in self.partial if key not in self.order]
        return '\n'.join(self.finals.get(key, self.partial.get(key, '')).strip() for key in order).strip()

    def complete(self):
        return all(item in self.finals for item in self.order)


async def append(socket, pcm):
    await socket.send(json.dumps({'type': 'input_audio_buffer.append', 'audio': base64.b64encode(pcm).decode()}))
