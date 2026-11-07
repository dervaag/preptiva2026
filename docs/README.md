# Dokumentasi AI Interview Simulator

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

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
| [security-and-privacy.md](security-and-privacy.md) | Pembatasan login, satu sesi aktif, penghapusan, tanda terima dan retensi |
| [langgraph-orchestration.md](langgraph-orchestration.md) | Aktivasi graph, CLI inspeksi, demo sintetis dan Studio lokal |

## Quick Start

```bash
pip install -r requirements.txt
# Only if .env does not exist: cp .env.example .env
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

## Indeks lengkap dan status terkini

Mulai dari [status terkini](current-state.md). Arsitektur dan alur English berada pada dua berkas terpisah; keduanya mengikuti implementasi opsional LangGraph yang sudah tersedia, bukan bukti konfigurasi deployment/akun Studio sudah diverifikasi. Inspector Studio localhost kini tersedia pada panduan operasi graph.

- [Log perubahan](CHANGELOG.md)
- [Pipeline AI](ai-pipeline.md)
- [Referensi API](api.md)
- [Arsitektur sistem Preptiva](architecture.md)
- [Acuan dan rubrik asesmen](assessment-reference.md)
- [Menyiapkan pembandingan AI–asesor](assessor-validation.md)
- [Status dokumentasi terkini — 7 November 2026](current-state.md)
- [Skema Database](database.md)
- [Menjalankan Preptiva di Kiri](deployment-kiri.md)
- [Arsip rencana deployment VM](deployment-vm.md)
- [Panduan development](development.md)
- [Cleansing CV/JD dan chunking dokumen](document-processing.md)
- [Rubrik Engineering Manager — persona Manager](engineering-manager-rubric.md)
- [Referensi Environment Variables](env.md)
- [Benchmark eksternal penilaian manusia](external-benchmark.md)
- [Implementation status — 7 November 2026](implementation-status.md)
- [Ruang wawancara](interview-room.md)
- [Preptiva End-to-End Flow](langgraph-end-to-end-flow.md)
- [Orkestrasi LangGraph Preptiva](langgraph-orchestration.md)
- [Preptiva Architecture: LangGraph Integration](langgraph-target-architecture.md)
- [Bahasa sesi, konteks campuran, persona, dan variasi](languages-and-personas.md)
- [Panduan log runtime](logging.md)
- [Menggunakan benchmark Mohler di Preptiva](mohler-benchmark.md)
- [Status implementasi brief panel](panel-implementation.md)
- [Pedoman dasar asesor Preptiva](pedoman-asesor.md)
- [Guidebook wawancara adaptif dan panel](question-guidebook.md)
- [Audio realtime dan VAD](realtime-voice.md)
- [Hasil wawancara](results.md)
- [Rencana rubrik berbasis referensi dan pengujiannya](rubric-validation-plan.md)
- [Keamanan akun dan pengelolaan data](security-and-privacy.md)
- [Persiapan perangkat, fokus sesi, dan waktu tunggu](session-experience.md)
- [Form simulasi baru](session-setup.md)
- [Setup dan instalasi](setup.md)
- [Hasil pemeriksaan awal penilaian](validation-initial-report.md)
- [Dashboard and history](workspace.md)

Rencana historis: [auth](superpowers/plans/2026-11-07-auth.md), [ruang wawancara](superpowers/plans/2026-11-07-interview-room.md), [setup](superpowers/plans/2026-11-07-simulation-setup.md), [workspace](superpowers/plans/2026-11-07-workspace.md).
