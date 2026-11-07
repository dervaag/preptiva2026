# Dokumentasi AI Interview Simulator

Selamat datang di dokumentasi lengkap proyek **AI Video Interview Simulator**.

Implementasi pertama tersedia sejak 7 November 2026. Mulai dari [README aplikasi](../README.md) dan [status implementasi](implementation-status.md) untuk perintah yang sudah diverifikasi dan perbedaan terhadap rancangan historis.

## Daftar Dokumen

| Dokumen | Deskripsi |
|---------|-----------|
| [architecture.md](architecture.md) | Arsitektur sistem, komponen, dan alur data |
| [api.md](api.md) | Referensi lengkap REST API |
| [setup.md](setup.md) | Panduan instalasi dan konfigurasi |
| [env.md](env.md) | Referensi semua environment variable |
| [ai-pipeline.md](ai-pipeline.md) | Alur pipeline AI: TTS, STT, LLM, scoring |
| [database.md](database.md) | Skema database dan model data |
| [development.md](development.md) | Panduan pengembangan lokal dan tips dev |

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env: AI_MOCK=false; isi API key OpenAI dan ElevenLabs
python -m app.scripts.seed
uvicorn app.main:app --reload --port 8000
```

Buka http://localhost:8000 — login dengan `demo@interview.local` / `demo1234`, atau buka langsung http://localhost:8000/dev-login untuk bypass login di mode development.

## Acuan dan pemeliharaan

- [Pedoman dasar asesor: sumber, langkah penilaian dan contoh bukti](pedoman-asesor.md)
- [Benchmark eksternal: sumber rating manusia, akses dan pembanding skor](external-benchmark.md)
- [Benchmark Mohler: dataset lokal dan perintah evaluasi](mohler-benchmark.md)
- [Hasil pemeriksaan teknis dan status validasi](validation-initial-report.md)
- [Acuan asesmen](assessment-reference.md)
- [Rencana rubrik berbasis referensi dan pengujiannya](rubric-validation-plan.md)
- [Perangkat, fokus sesi, dan latensi](session-experience.md)
- [Panduan log runtime](logging.md)
- [Log perubahan](CHANGELOG.md)

- [Bahasa dan fokus persona](languages-and-personas.md)

- [Cleansing dan chunking dokumen](document-processing.md)

Panduan pertanyaan adaptif, fresh graduate dan panel: [question-guidebook.md](question-guidebook.md). Sumber runtime: [question-guidebook.json](question-guidebook.json).

- [Status brief panel, memori dan interupsi](panel-implementation.md)
- [Persiapan pembandingan asesor](assessor-validation.md)
