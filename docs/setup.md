# Setup dan instalasi

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Gunakan Python 3.12 dan [status terkini](current-state.md). Panduan ini mengikuti kode baseline `a85d0da`, bukan rancangan provider historis.

## Development lokal

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Jalankan hanya bila .env belum ada:
# cp .env.example .env
.venv/bin/python -m app.scripts.seed
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Buka http://localhost:8000. Akun development yang dibuat seed: `demo@interview.local` / `demo1234`. `/dev-login` hanya development setelah seed; produksi memakai akun nyata/seeder eksplisit. Jangan mengganti atau menimpa environment yang sudah ada.

Untuk akun/dashboard, provider AI tidak diperlukan. Untuk wawancara, isi `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` dan voice ID persona yang digunakan. Pertahankan `AI_MOCK=false`, `STT_PROVIDER=openai`, `STT_FALLBACK_PROVIDER=` dan `TTS_PROVIDER=elevenlabs`. `DATABASE_URL` serta `REDIS_URL` kosong memakai SQLite dan jobs development in-process.

## Pilihan engine

`ORCHESTRATION_ENGINE` menerima `legacy` atau `langgraph`, default kode `legacy`. Instalasi requirements sudah mencakup LangGraph dan detektor bahasa lokal. Sesi dipin ke engine saat dibuat. Restart proses setelah mengubah konfigurasi; jangan mengubah metadata sesi lama untuk memaksakan migrasi. Lihat [operasi graph](langgraph-orchestration.md).

## Pemeriksaan

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/room_controller_test.cjs app/static/js/interview-room.js
node tests/rubric_ui_test.js
```

Tes memakai provider tiruan. Tes Chrome opsional memerlukan Playwright dan Google Chrome. Kamera/mikrofon memerlukan localhost atau HTTPS; wawancara dibatasi ke desktop/laptop. Platform UI mendukung Indonesia/Inggris, terpisah dari bahasa wawancara. Bahasa feedback dipin dari pilihan platform saat sesi dibuat.

## Deployment

Untuk Docker Compose, siapkan `.env`, `DB_PASSWORD`, secret acak panjang dan cookie secure sesuai konfigurasi produksi. Jalankan `docker compose up -d --build` setelah konfigurasi HTTPS/ingress siap. PostgreSQL dan Redis/arq dipakai web/worker dengan konfigurasi yang sama.

Panduan khusus: [Kiri](deployment-kiri.md), [arsip VM](deployment-vm.md), [keamanan dan privasi](security-and-privacy.md). Push ke GitHub bukan bukti deployment sudah berhasil; periksa workflow dan kesehatan web/worker.

## Opsional: benchmark

[Benchmark Mohler](mohler-benchmark.md) memiliki dependency Parquet opsional di `validation/requirements.txt`. Data lokal tidak ikut clone/image; gunakan perintah unduhan revisi tetap pada panduan. Pilot 50 sudah disiapkan di workspace asal, tetapi run model berbayar belum dilakukan pada baseline ini. Download/prepare tidak memerlukan kredit AI; `run --run-paid` memakai OpenAI dan prompt benchmark terpisah.
