# Arsitektur Sistem

## Stack Teknologi

| Layer | Teknologi |
|-------|-----------|
| Backend | Python 3.12, FastAPI |
| Template Engine | Jinja2 |
| Frontend | Vanilla JS, Chart.js |
| Database | PostgreSQL 16 (prod) / SQLite (dev) |
| ORM | SQLAlchemy 2 async (`asyncpg` / `aiosqlite`) |
| Queue | Redis + arq (prod) / asyncio in-process (dev) |
| AI — LLM | OpenAI GPT-4o-mini (fast), GPT-4o (deep) |
| AI — TTS | ElevenLabs (provider tunggal, cache dan retry) |
| AI — STT | OpenAI gpt-4o-transcribe / Deepgram nova-3 |
| Web Server | Uvicorn + Nginx (prod) |
| Container | Docker, Docker Compose |

---

## Struktur Direktori

```
app/
├── main.py            FastAPI app factory, middleware, /health
├── config.py          Semua setting dari .env (Pydantic Settings)
├── models.py          ORM: User, InterviewSession, SessionCompetency,
│                          InterviewQuestion, InterviewAnswer
├── db.py              Engine async, SessionLocal, init_db
├── deps.py            FastAPI dependencies: current_user, get_owned_session
├── jobs.py            Enqueue ke arq; fallback in-process
├── log.py             JSON logger satu baris, Timer, RequestIdMiddleware, session_var
├── security.py        bcrypt hash & verify
├── storage.py         Path helper audio/CV, safe_audio_path
├── api/
│   ├── auth.py        POST /api/auth/register, /login, /logout; GET /api/me
│   ├── sessions.py    CRUD sesi, submit jawaban, finish, result, audio
│   └── dashboard.py   GET /api/dashboard
├── services/
│   ├── interview.py   Logika bisnis sesi (create, state, answer, finish, result)
│   ├── dashboard.py   Aggregasi data dashboard
│   └── cv.py          Ekstrak PDF, validasi teks CV
├── ai/
│   ├── orchestrator.py  Kontrak modul AI (build_questions, transcribe, respond, evaluate, summarize)
│   ├── blueprint.py     Slot pertanyaan per interviewer, ensure_coverage
│   ├── prompts.py       Semua prompt LLM + anchor + fairness rules
│   ├── scoring.py       Bobot kompetensi, skor per soal & sesi, verifikasi bukti
│   ├── speech.py        TTS ElevenLabs, STT OpenAI
│   ├── model_router.py  fast()/deep() OpenAI call + JSON parsing + retry
│   ├── delivery.py      word_count, wpm, filler_count
│   ├── assessment.py    Snapshot rubrik Markdown
│   └── types.py         Pydantic types shared: CandidateContext, Turn, EvalResult, dll.
├── worker/
│   ├── tasks.py         prepare_session, evaluate_answer, finalize_session
│   └── settings.py      Konfigurasi arq WorkerSettings
├── web/
│   └── routes.py        Halaman HTML (Jinja2): login, register, dashboard, form, room, result, riwayat
├── scripts/
│   ├── seed.py          Buat akun demo
│   └── dump_schema.py   Generate DDL referensi
├── templates/           HTML Jinja2
└── static/              CSS, JS, vendor
```

---

## Diagram Arsitektur

```
Browser
  │
  ├─ GET /login, /dashboard, /simulasi/baru, /sesi/{id}/ruang, /sesi/{id}/hasil
  │       └─ Jinja2 Template (SSR)
  │
  └─ XHR/Fetch API
        ├─ POST /api/auth/login|register|logout
        ├─ GET  /api/me
        ├─ POST /api/sessions              (multipart: form + CV)
        ├─ GET  /api/sessions/{id}/state
        ├─ POST /api/sessions/{id}/answers (multipart: audio blob)
        ├─ POST /api/sessions/{id}/finish
        ├─ GET  /api/sessions/{id}/result
        ├─ GET  /api/sessions/{id}/audio/{name}
        └─ GET  /api/dashboard

FastAPI (app/main.py)
  ├─ SessionMiddleware (cookie isim_session)
  ├─ RequestIdMiddleware (X-Request-ID)
  ├─ Router: api/auth, api/sessions, api/dashboard, web/routes
  └─ /health

Services Layer (app/services/)
  ├─ interview.py    create_session → jobs.enqueue("prepare_session")
  │                  submit_answer → ai.transcribe → ai.respond → jobs.enqueue("evaluate_answer")
  │                  finish        → jobs.enqueue("finalize_session")
  └─ dashboard.py, cv.py

AI Layer (app/ai/) — pure functions, no DB
  ├─ orchestrator.py   koordinator semua panggilan AI
  ├─ speech.py         TTS ElevenLabs tunggal dan STT OpenAI
  ├─ model_router.py   OpenAI Chat Completions + JSON schema validation
  ├─ scoring.py        bobot, skor per soal, agregasi sesi
  └─ assessment.py     rubrik berversi dari Markdown

Worker (arq / in-process asyncio)
  ├─ prepare_session   → ai.build_questions → TTS paralel → DB ready
  ├─ evaluate_answer   → ai.evaluate_answer → skor per soal → DB done
  └─ finalize_session  → tunggu evaluasi → ai.summarize_session → DB done

Database (PostgreSQL / SQLite)
  └─ users, interview_sessions, session_competencies,
     interview_questions, interview_answers
```

---

## Alur Sesi

```
1. POST /api/sessions
   └─ Validasi form + CV
   └─ Buat InterviewSession (status: "preparing")
   └─ Enqueue prepare_session

2. Worker: prepare_session
   └─ LLM fast: parse CV + JD → cv_summary, jd_summary
   └─ LLM deep: generate N pertanyaan per slot blueprint
   └─ TTS paralel: intro, pertanyaan, filler, closing, detail
   └─ Simpan ke DB (status: "ready")

3. Browser polling GET /api/sessions/{id}/state
   └─ Status "ready" → tampilkan ruang wawancara

4. Per pertanyaan:
   └─ POST /api/sessions/{id}/answers (audio blob)
   └─ STT (OpenAI/Deepgram) → transkrip
   └─ LLM fast: respond → next | follow_up | redirect
   └─ TTS live: audio tanggapan
   └─ Jika action=next → enqueue evaluate_answer (async)

5. POST /api/sessions/{id}/finish
   └─ Status → "scoring"
   └─ Enqueue finalize_session

6. Worker: finalize_session
   └─ Tunggu semua evaluate_answer selesai
   └─ Hitung skor kompetensi & total
   └─ LLM deep: summarize_session → review + saran belajar
   └─ Hapus audio jawaban (privasi)
   └─ Status → "done"

7. GET /api/sessions/{id}/result
   └─ Tampilkan halaman hasil
```

---

## Suara dan snapshot asesmen

Seluruh suara pewawancara menggunakan ElevenLabs Multilingual v2, dengan voice yang sama per persona untuk prepared dan live. Konkurensi dibatasi dua request per proses; 429 di-retry. Kegagalan tidak mengganti suara ke OpenAI atau browser. Cache tersimpan di `data/tts_cache/`.

Rubrik dari Markdown disnapshot ke `interview_sessions.script.assessment` saat sesi dibuat, lalu diteruskan ke evaluator. Tidak ada tabel baru. Lihat [assessment-reference.md](assessment-reference.md).

Sebelum mulai, browser memeriksa kamera/mikrofon/suara dan meminta konfirmasi aturan fokus. `POST /answers?stream=true` mengirim transkrip lebih awal, kemudian hasil lengkap. `POST /close` mengakhiri sesi ketika halaman ditinggalkan setelah mulai. Lihat [session-experience.md](session-experience.md) dan [logging.md](logging.md).

---

## Kompetensi yang Dinilai

| Kompetensi | Keterangan |
|------------|------------|
| `communication` | Kejelasan, struktur, dan efektivitas komunikasi |
| `problem_solving` | Pendekatan sistematis terhadap masalah |
| `technical` | Penguasaan teknis relevan dengan role |
| `analytical` | Kemampuan analisis data dan situasi |
| `teamwork` | Kolaborasi dan kerja sama tim |
| `adaptability` | Fleksibilitas dan kemampuan beradaptasi |
| `leadership` | Kepemimpinan dan pengambilan keputusan |

Bobot per kompetensi berbeda berdasarkan tipe interviewer (HR / User / Manager).

## Pembaruan bahasa dan identitas publik

URL/API memakai `interview_sessions.uuid`; ID numerik tetap internal untuk relasi/job. Bahasa sesi di `script.settings.language`; konteks campuran dan persona didokumentasikan dalam [languages-and-personas.md](languages-and-personas.md). Generator menggunakan variasi sudut ber-seed UUID dan sampai 35 pertanyaan pemilik/persona yang sama untuk menghindari pengulangan.

## Komponen benchmark lokal

`validation/mohler.py` menyediakan download → prepare → run → report untuk [benchmark Mohler](mohler-benchmark.md). Komponen ini memakai klien model aplikasi dengan prompt akademik tersendiri dan tidak berada dalam alur web/worker wawancara. `validation/audit.py` tetap mengaudit kesiapan dataset asesor EM; `validation/external_compare.py` membandingkan skor eksternal dengan provenance tersendiri. Ketiga alat tidak menandai rubrik tervalidasi. Artefak benchmark berada di `data/external/` dan tidak dikemas ke deployment.
