# Panduan Setup & Instalasi

> Implementasi 7 November 2026: perintah terverifikasi ada di [README aplikasi](../README.md). Gunakan `.venv/bin/python`, `.venv/bin/uvicorn`, dan `compose.yaml`. Nginx adalah contoh proxy untuk ingress HTTPS; sertifikat tidak dibundel. Mode tanpa kredensial hanya mendukung akun/dashboard/form, bukan sesi AI dummy. Lihat [status implementasi](implementation-status.md).

## Prasyarat

| Tool | Versi Minimum | Keterangan |
|------|--------------|------------|
| Python | 3.12 | Wajib |
| pip | terbaru | `pip install --upgrade pip` |
| Docker & Docker Compose | 24+ | Hanya untuk deployment produksi |
| PostgreSQL | 16 | Hanya untuk produksi (dev pakai SQLite) |
| Redis | 7 | Hanya untuk produksi (dev pakai in-process) |

---

## Mode 1: Dev Lokal (tanpa Docker, tanpa OpenAI)

Cara paling cepat untuk mulai. Pakai SQLite, job in-process, OpenAI untuk wawancara, dan ElevenLabs untuk suara.

### Langkah

**1. Clone dan masuk ke direktori:**
```bash
cd c:\Software\interview-simulator
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Buat file `.env`:**
```bash
cp .env.example .env
```

**4. Edit `.env` untuk mode dev:**
```env
APP_ENV=development
DATABASE_URL=          # kosong → SQLite di ./data/dev.db
REDIS_URL=             # kosong → job in-process
AI_MOCK=false          # wawancara nyata; isi API key OpenAI dan ElevenLabs
COOKIE_SECURE=false
SECRET_KEY=dev-secret-key-local
```

**5. Buat akun demo:**
```bash
python -m app.scripts.seed
```
Akun: `demo@interview.local` / `demo1234`

**6. Jalankan server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**7. Buka browser:**
- http://localhost:8000/dev-login — bypass login langsung ke form simulasi
- http://localhost:8000/login — login manual

---

## Mode 2: Dev Lokal dengan OpenAI

Sama seperti Mode 1, tapi AI menggunakan GPT yang sesungguhnya.

Edit `.env`:
```env
AI_MOCK=false
OPENAI_API_KEY=sk-...
TTS_PROVIDER=elevenlabs
# Isi ELEVENLABS_API_KEY dan ELEVENLABS_VOICE_HR/USER/MANAGER
TTS_MODEL=gpt-4o-mini-tts
STT_PROVIDER=openai
STT_MODEL=gpt-4o-transcribe
```

> **Catatan biaya:** Satu sesi standar (7 pertanyaan) membutuhkan sekitar 10–15 ribu token dan beberapa menit audio TTS/STT.

---

## Mode 3: Produksi (Docker Compose)

### Persiapan

**1. Isi `.env` produksi:**
```env
APP_ENV=production
SECRET_KEY=           # string random panjang, mis. openssl rand -hex 32
COOKIE_SECURE=true    # setelah HTTPS aktif

DB_PASSWORD=          # password PostgreSQL
DATABASE_URL=postgresql+asyncpg://app:PASSWORD@db:5432/interview_sim
REDIS_URL=redis://redis:6379/0

OPENAI_API_KEY=sk-...
AI_MOCK=false
TTS_PROVIDER=elevenlabs
# Isi ELEVENLABS_API_KEY dan ELEVENLABS_VOICE_HR/USER/MANAGER
TTS_MODEL=gpt-4o-mini-tts
```

**2. Build dan jalankan:**
```bash
docker compose up -d --build
```

**3. Buat akun demo:**
```bash
docker compose exec web python -m app.scripts.seed demo@interview.local demo1234
```

**4. Verifikasi:**
```bash
docker compose ps
curl -s localhost/health
```

### HTTPS (wajib untuk kamera di luar localhost)

1. Taruh `fullchain.pem` dan `privkey.pem` di `deploy/certs/`
2. Aktifkan blok `443` di `deploy/nginx.conf`
3. Set `COOKIE_SECURE=true` di `.env`
4. Restart: `docker compose restart nginx`

### Operasi Database

```bash
# Akses psql
docker compose exec db psql -U app -d interview_sim

# Backup
docker compose exec db pg_dump -U app interview_sim > backup.sql

# Restore
docker compose exec -T db psql -U app interview_sim < backup.sql
```

---

## Dev Lokal dengan PostgreSQL (tanpa Docker)

Jika ingin dev dengan Postgres yang sudah terinstall lokal:

```env
DATABASE_URL=postgresql+asyncpg://app:pass@localhost:5432/interview_sim
```

Buat database dan user:
```sql
CREATE USER app WITH PASSWORD 'pass';
CREATE DATABASE interview_sim OWNER app;
```

---

## Menjalankan Worker Terpisah (opsional, dengan Redis)

Jika `REDIS_URL` diisi, arq worker harus dijalankan terpisah:

```bash
arq app.worker.settings.WorkerSettings
```

Tanpa ini, job berjalan in-process (cukup untuk dev, tidak direkomendasikan untuk produksi dengan load tinggi).

---

## Perintah Berguna

```bash
# Generate DDL referensi dari model
python -m app.scripts.dump_schema

# Cek log per event AI
docker compose logs web worker | grep '"event": "step"'

# Cek biaya per sesi (jika session_var di-set di log)
docker compose logs web worker | grep '"event": "tts_usage"'
```
