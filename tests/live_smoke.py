"""Opt-in paid-provider smoke test. Isolated DB, synthetic CV/audio, no user records.

Run: .venv/bin/python tests/live_smoke.py --run-paid
Uses configured OpenAI/ElevenLabs credentials and consumes their API credits.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CV = '''Nama: Kandidat Uji Sintetis. Ini data fiktif untuk pengujian perangkat lunak.
Pengalaman: tiga tahun sebagai Product Designer pada perusahaan contoh.
Melakukan wawancara pengguna, menyusun prototipe, dan berkolaborasi dengan tim produk.
Pada proyek formulir pendaftaran, melakukan lima uji kegunaan dan mengurangi langkah
dari enam menjadi tiga. Tingkat penyelesaian tugas meningkat dari 60 menjadi 80 persen.
Keahlian: riset pengguna, desain interaksi, fasilitasi diskusi, dan evaluasi eksperimen.
Pendidikan: sarjana desain. Ingin mengembangkan produk digital yang mudah digunakan.'''
JD = '''Product Designer tingkat middle untuk perusahaan teknologi contoh.
Tanggung jawab: memahami kebutuhan pengguna, merancang prototipe, menguji kegunaan,
berkolaborasi dengan tim produk dan engineering, serta mengukur dampak desain.
Kualifikasi: mampu menjelaskan keputusan dengan bukti, menerima masukan dan beradaptasi.'''
ANSWERS = {
    1: 'Saya bekerja sebagai desainer produk selama tiga tahun. Saya melakukan riset, membuat prototipe, dan menguji hasil bersama tim. Pada proyek pendaftaran, saya menyederhanakan enam langkah menjadi tiga. Setelah lima pengujian pengguna, tingkat penyelesaian meningkat dari enam puluh menjadi delapan puluh persen.',
    2: 'Ketika prioritas tim berbeda, saya mengajak rekan produk dan engineering membandingkan temuan pengguna. Tugas saya menjelaskan masalah utama dan menyusun dua alternatif. Kami menguji prototipe sederhana, lalu memilih solusi yang lebih mudah dipakai. Hasilnya, tim sepakat dan pekerjaan selesai sesuai jadwal.',
    3: 'Saat kebutuhan berubah, saya meninjau ulang temuan riset dan menyusun prioritas bersama tim. Saya mengurangi lingkup awal, mendokumentasikan asumsi, lalu menguji rancangan kepada lima pengguna. Kami menyelesaikan fitur utama tepat waktu. Saya belajar meminta umpan balik lebih awal agar perubahan lebih mudah ditangani.',
}
FOLLOWUP = 'Kontribusi pribadi saya adalah memfasilitasi diskusi dan menjalankan lima uji kegunaan. Saya membandingkan hasil sebelum dan sesudah perubahan menggunakan tugas yang sama. Tingkat penyelesaian meningkat dua puluh poin persentase. Namun sampel masih kecil, sehingga saya mengusulkan pengujian lanjutan.'


async def run(persona, directory, report):
    from app.main import app
    from app.config import settings
    from app.ai import speech
    from app.ai.errors import check_response
    from app import storage
    from app.db import engine
    import httpx

    # Move only this test process's generated audio/cache into its temporary folder.
    # Provider functions and AI responses remain real and unmodified.
    speech.ROOT = directory
    storage.ROOT = directory
    logging.getLogger('httpx').setLevel(logging.WARNING)
    speech.require_credentials(persona)
    report['models'] = {'fast':settings.model_fast, 'deep':settings.model_deep, 'stt':settings.stt_model,
                        'tts':settings.elevenlabs_model_prepared}

    def progress(stage, **fields):
        report['stage'] = stage
        print(json.dumps({'stage':stage, **fields}, ensure_ascii=False), flush=True)

    progress('memeriksa_voice')
    report['voices'] = {}
    async with httpx.AsyncClient(timeout=20) as client:
        for role in ('hr', 'user', 'manager'):
            voice = getattr(settings,f'elevenlabs_voice_{role}')
            if not voice:
                report['voices'][role] = 'belum diisi'
                continue
            response = await client.get(f'https://api.elevenlabs.io/v1/voices/{voice}',
                headers={'xi-api-key':settings.elevenlabs_api_key})
            try:
                check_response(response,'ElevenLabs')
                report['voices'][role] = 'dapat diakses'
            except Exception:
                report['voices'][role] = f'HTTP {response.status_code}'
                if role == persona:
                    raise
    progress('voice_terverifikasi', voices=report['voices'])

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
            async def request(method, path, **kwargs):
                response = await client.request(method,path,**kwargs)
                if response.status_code >= 400:
                    detail = response.json().get('detail','Permintaan gagal')
                    raise RuntimeError(f'HTTP {response.status_code}: {detail if isinstance(detail,str) else "Validasi permintaan gagal"}')
                return response

            password = secrets.token_hex(16) + '1a'
            await request('POST','/api/auth/register',json={'name':'Kandidat Uji Sintetis','email':'live-smoke@example.com',
                'password':password,'password_confirm':password,'gender':'male','age':28,'agree':True})
            progress('menyiapkan_sesi')
            created = (await request('POST','/api/sessions',data={'candidate_name':'Kandidat Uji Sintetis','gender':'male',
                'age':28,'job_role':'Product Designer','level':'middle','industry':'Technology','company':'Perusahaan Contoh',
                'question_count':3,'interviewer':persona,'language':'id','consent':'true','cv_text':CV,'job_description':JD})).json()
            sid = created['session_id']
            base = f'/api/sessions/{sid}'
            async def wait_state(expected, limit=300):
                end = time.monotonic() + limit
                while time.monotonic() < end:
                    state = (await request('GET',base+'/state')).json()
                    if state['status'] == 'failed':
                        raise RuntimeError(state['error'])
                    if state['status'] == expected:
                        return state
                    await asyncio.sleep(1)
                raise RuntimeError(f'Timeout menunggu status {expected}')
            state = await wait_state('ready')
            assert len(state['questions']) == 3
            report['limits'] = {k:state[k] for k in ('answer_seconds','retry_limit','max_followups')}
            report['prepared_audio_count'] = 0
            for url in [state['script']['intro']['audio_url'], state['script']['closing']['audio_url']] + [q['audio_url'] for q in state['questions']]:
                audio = await request('GET',url)
                assert len(audio.content) > 100
                report['prepared_audio_count'] += 1
            progress('sesi_siap', limits=report['limits'])
            await request('POST',base+'/start')
            current = state['current_turn']
            report['turns'] = []
            for index in range(3 + state['max_followups']):
                if current is None:
                    break
                text = FOLLOWUP if current['kind'] == 'follow_up' else ANSWERS[current['main_order']]
                progress('mengirim_jawaban', turn=index+1, main_order=current['main_order'], kind=current['kind'])
                name = f'synthetic_answer_{index}.mp3'
                await speech.synthesize(text,persona,sid,name)
                content = (storage.audio_dir(sid)/name).read_bytes()
                started = time.monotonic()
                response = await request('POST',base+'/answers?stream=true',data={'question_id':current['id'],
                    'duration_ms':min(30000,state['answer_seconds']*1000),'retry_count':0},
                    files={'audio':('answer.mp3',content,'audio/mpeg')})
                events = [json.loads(line) for line in response.text.splitlines() if line]
                failure = next((e for e in events if e['type']=='error'),None)
                if failure:
                    raise RuntimeError(failure['message'])
                result = next(e for e in events if e['type']=='result')
                assert any(e['type']=='transcript' for e in events)
                assert len(result['transcript'].split()) >= 10
                assert len((await request('GET',result['response_audio_url'])).content) > 100
                report['turns'].append({'main_order':current['main_order'],'kind':current['kind'],'action':result['action'],
                    'transcript_words':len(result['transcript'].split()),'elapsed_seconds':round(time.monotonic()-started,2)})
                progress('jawaban_diterima', **report['turns'][-1])
                current = result['follow_up_question'] or result['next_question']
                if result['is_last']:
                    assert current is None
                    break
            assert current is None, 'Sesi belum mencapai akhir'
            progress('menilai_sesi')
            await request('POST',base+'/finish')
            await wait_state('done')
            result = (await request('GET',base+'/result')).json()
            assert result['total_score'] is not None and 1 <= result['total_score'] <= 5
            assert result['review'].get('summary')
            report['result'] = {'status':result['status'],'score':result['total_score'],'items':len(result['items']),
                'measured_competencies':len([c for c in result['competencies'] if c['score'] is not None]),
                'rubric_version':result['assessment']['version']}
            progress('selesai', **report['result'])
            report['ok'] = True
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-paid',action='store_true',help='Acknowledge real provider calls and API credit usage.')
    parser.add_argument('--persona',choices=['hr','user','manager'],default='hr')
    args = parser.parse_args()
    if not args.run_paid:
        parser.error('Tambahkan --run-paid untuk menjalankan panggilan API berbayar.')
    report = {'ok':False,'persona':args.persona,'synthetic_data':True,'stage':'startup'}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='preptiva-live-') as folder:
        os.environ.update({'DATABASE_URL':f'sqlite+aiosqlite:///{folder}/live.db','APP_ENV':'development',
            'REDIS_URL':'','COOKIE_SECURE':'false','AI_MOCK':'false','SECRET_KEY':secrets.token_hex(32)})
        try:
            asyncio.run(run(args.persona,Path(folder),report))
        except Exception as exc:
            # Never print raw HTTP/validation exceptions: they can contain remote data or credentials.
            from app.ai.errors import ProviderError
            report['error_type'] = type(exc).__name__
            report['error'] = str(exc) if isinstance(exc,(ProviderError,RuntimeError)) else 'Pengujian gagal; lihat tahap dan jenis kesalahan.'
        finally:
            report['elapsed_seconds'] = round(time.monotonic()-started,2)
            destination = ROOT/'artifacts/live-smoke.json'
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
