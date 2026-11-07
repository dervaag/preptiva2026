# Panduan Development

## Setup Cepat

```bash
cd c:\Software\interview-simulator
pip install -r requirements.txt
cp .env.example .env
# Edit .env: DATABASE_URL= dan REDIS_URL= (kosong), AI_MOCK=false
python -m app.scripts.seed
uvicorn app.main:app --reload --port 8000
```

Buka http://localhost:8000/dev-login — auto-login sebagai demo user dan langsung ke form simulasi dengan data dummy sudah terisi.

---

## Dev Login & Auto-fill

Tersedia di mode `APP_ENV=development`:

- **http://localhost:8000/dev-login** — bypass login, redirect ke form simulasi
- Form simulasi di-autofill dengan data dummy (CV, job description, dll.) oleh JS di `form.html`
- Banner kuning muncul sebagai penanda mode dev

---

## Struktur File yang Sering Diedit

| File | Keterangan |
|------|------------|
| `app/ai/prompts.py` | Ubah prompt LLM (pertanyaan, evaluasi, summarize) |
| `app/ai/blueprint.py` | Ubah slot dan bobot default kompetensi |
| `app/ai/scoring.py` | Ubah bobot per interviewer, formula skor |
| `app/ai/assessment.py` | Versi dan snapshot rubrik dari Markdown |
| `app/templates/` | Ubah UI Jinja2 |
| `app/static/js/interview-room.js` | State machine ruang wawancara |
| `app/config.py` | Tambah setting baru |

---

## Data contoh dan API nyata

`AI_MOCK` harus false; startup menolak true. Dummy hanya mengisi form development, sedangkan seluruh pertanyaan, transkrip, tanggapan, dan evaluasi memakai API. `app/ai/mock.py` adalah artefak lama dan tidak dipanggil pipeline aktif.

Gunakan dependency mock di pengujian otomatis, bukan mode dummy di sesi pengguna. Jalankan `.venv/bin/python -m unittest discover -s tests -v` dan `node tests/test_answer_stream.cjs`.

Tes browser opsional: instal Playwright di virtualenv lalu jalankan `.venv/bin/python tests/browser_smoke.py` dengan Chrome terpasang. Tes memakai database sementara, perangkat sintetis, dan event visibility yang disimulasikan; tidak memanggil API AI. Pemeriksaan speaker fisik tetap manual.

## Mengganti Model AI

Semua lewat `.env`:

```env
MODEL_FAST=gpt-4o-mini        # parse, respond, transcribe decision
MODEL_DEEP=gpt-4o             # generate questions, evaluate, summarize
TTS_MODEL=gpt-4o-mini-tts     # atau tts-1
STT_PROVIDER=openai           # atau deepgram
STT_MODEL=gpt-4o-transcribe   # atau gpt-4o-mini-transcribe, whisper-1
```

---

## Menambah Provider TTS Baru

1. Tambah fungsi `_newprovider_tts(v: Voice, text: str, path: Path)` di `app/ai/speech.py`
2. Daftarkan ke dict `_PROVIDERS`
3. Tambah logic di `voice_chain()` dan `_openai_voice()`/`_eleven_voice()`
4. Tambah setting di `config.py`

---

## Logging

Setiap event ditulis sebagai JSON satu baris ke stdout:

```json
{"ts": 1793860675.1, "event": "step", "rid": "abc123", "sid": 42, "step": "tts", "ms": 1200, "ok": true, "provider": "openai", "model": "gpt-4o-mini-tts", "kind": "prepared", "chars": 145}
```

Field standar:
- `ts` — Unix timestamp
- `event` — nama event
- `rid` — request ID (dari header X-Request-ID)
- `sid` — session ID (dari `session_var` context var)

Field context-specific:
- `step` + `ms` + `ok` — di semua Timer event
- `provider`, `model`, `kind`, `chars` — di TTS events
- `session_id`, `main_order`, `action` — di answer events

**Filter log berguna:**

```bash
# Semua panggilan AI dengan latency
python -m uvicorn app.main:app 2>&1 | python -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('event') == 'step':
            print(f\"{d['step']:20} {d['ms']:5}ms  sid={d.get('sid')}\")
    except: pass
"

# Docker produksi
docker compose logs web worker | grep '"event": "step"'
docker compose logs web worker | grep '"event": "tts_usage"'
docker compose logs web worker | grep '"event": "answer"'
```

---

## Alur Data Ruang Wawancara (JS State Machine)

File: `app/static/js/interview-room.js`

```
State: idle
  → Start Interview → State: intro
      → Audio intro selesai → State: question (pertanyaan pertama)
          → Mulai Jawab → State: recording
              → Stop / Timer habis → upload audio → State: processing
                  → response action=follow_up → State: follow_up → recording
                  → response action=next + is_last=false → State: question (berikutnya)
                  → response action=next + is_last=true → audio closing → State: finished
                      → POST /finish → State: scoring → polling result
```

---

## Tips Dev

**Database reset (SQLite):**
```bash
Remove-Item data\dev.db
python -m app.scripts.seed
```

**Lihat isi DB SQLite:**
```bash
python -c "
import asyncio, json
from app.db import SessionLocal
from app.models import InterviewSession
async def main():
    async with SessionLocal() as db:
        sessions = (await db.execute(__import__('sqlalchemy').select(InterviewSession))).scalars().all()
        for s in sessions:
            print(s.id, s.job_role, s.status, s.total_score)
asyncio.run(main())
"
```

**Test endpoint langsung:**
```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@interview.local","password":"demo1234"}'

# Health check
curl http://localhost:8000/health
```

**Cek import semua modul:**
```bash
python -c "from app.main import app; print('OK')"
```

---

## Git Workflow

Branch utama: `main`

```bash
# Feature baru
git checkout -b feature/nama-fitur

# Commit
git add app/ai/prompts.py
git commit -m "feat: tambah prompt evaluasi STAR lebih ketat"

# Push
git push -u origin feature/nama-fitur
```

Konvensi commit message:
- `feat:` — fitur baru
- `fix:` — bug fix
- `docs:` — perubahan dokumentasi
- `refactor:` — refactor tanpa perubahan perilaku
- `chore:` — update dependency, config

## Pembaruan 5 November 2026

Lihat [acuan dan snapshot rubrik](assessment-reference.md), [persiapan perangkat dan stream jawaban](session-experience.md), serta [log runtime](logging.md). Setiap perubahan selanjutnya wajib memperbarui Markdown terkait dan [changelog](CHANGELOG.md).

Tes browser menggunakan nada sintetis dan menonaktifkan echo/noise suppression hanya pada fixture agar nada tidak dianggap noise setelah beberapa detik. Pemrosesan audio pada aplikasi nyata tetap aktif. Tes terbaru memeriksa UUID, mirror logo/video terpisah, pilihan fullscreen saat mulai dan keluar fullscreen tanpa menutup sesi.
