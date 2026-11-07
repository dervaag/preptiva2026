# Referensi Environment Variables

File konfigurasi: `.env` (copy dari `.env.example`)

## Status implementasi 7 November 2026

- `ANSWER_SECONDS_*`, `MAX_FOLLOWUPS_ENABLED`, `FOLLOWUPS_*`, dan `RETRY_LIMIT` sudah dipakai saat membuat sesi. Durasi dan batas follow-up tersimpan di kolom sesi; `retry_limit` disnapshot dalam `script.settings`. Sesi lama tanpa snapshot retry tetap memakai batas 2.
- Durasi valid 10–300 detik; retry 0–10; follow-up 0 sampai jumlah pertanyaan utama, tetap maksimal satu follow-up per pertanyaan. Menonaktifkan `MAX_FOLLOWUPS_ENABLED` membuat batas sesi baru 0. Server memvalidasi retry dan durasi upload (toleransi encoder/browser 2 detik).
- `RESPOND_TIMEOUT_SEC` membatasi keseluruhan tahap LLM tanggapan + TTS live setelah STT selesai. Timeout membatalkan pemrosesan sebelum commit dan jawaban yang sama dapat dikirim ulang. Timeout TTS per request juga tetap berlaku. Nilai timeout harus >0 dan <=300 detik.
- `ELEVENLABS_OUTPUT_FORMAT` dipakai pada request dan kunci cache. Saat ini hanya format MP3 didukung karena endpoint pemutar mengirim `audio/mpeg`. `ELEVENLABS_LANGUAGE_CODE` dikirim hanya untuk model `*_v2_5`; nilai `id` tidak dipaksakan ke Multilingual v2 yang tidak mendukung parameter ini.
- `TTS_PROVIDER` harus `elevenlabs`, `STT_PROVIDER` harus `openai`, dan `STT_FALLBACK_PROVIDER` harus kosong. Nilai alternatif ditolak saat startup, bukan diam-diam menggunakan provider lain.
- `TTS_MODEL`, `TTS_VOICE_*`, `DEEPGRAM_*`, dan `PRICE_*` pada referensi historis di bawah belum digunakan implementasi aktif. `DB_PASSWORD` dibaca Docker Compose, bukan Settings Python.
- File `.env` dibaca saat proses mulai. Restart web dan worker setelah mengubahnya. Jangan membagikan nilai API key.

---

## Aplikasi

| Variable | Default | Keterangan |
|----------|---------|------------|
| `APP_ENV` | `development` | `development` atau `production` |
| `SECRET_KEY` | `dev-secret-change-me` | Secret key untuk session cookie. **Wajib diganti di produksi.** |
| `COOKIE_SECURE` | `false` | Set `true` setelah HTTPS aktif (wajib untuk kamera di HP/luar localhost) |

---

## Database & Queue

| Variable | Default | Keterangan |
|----------|---------|------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/dev.db` | Kosong = SQLite dev. Produksi: `postgresql+asyncpg://app:PASS@db:5432/interview_sim` |
| `DB_PASSWORD` | — | Password PostgreSQL (samakan dengan yang di `DATABASE_URL`) |
| `REDIS_URL` | `` (kosong) | Kosong = job berjalan in-process (asyncio). Produksi: `redis://redis:6379/0` |

---

## OpenAI

| Variable | Default | Keterangan |
|----------|---------|------------|
| `OPENAI_API_KEY` | `` | API key OpenAI. Wajib untuk wawancara nyata |
| `MODEL_FAST` | `gpt-4o-mini` | Model untuk parse CV/JD, respond, transcribe decision |
| `MODEL_DEEP` | `gpt-4o` | Model untuk generate pertanyaan, evaluate, summarize |

---

## TTS (Text-to-Speech)

| Variable | Default | Keterangan |
|----------|---------|------------|
| `TTS_PROVIDER` | `elevenlabs` | Provider tunggal; tidak berpindah suara saat gagal |
| `TTS_MODEL` | `gpt-4o-mini-tts` | Model OpenAI TTS. `tts-1` juga valid (lebih murah, dijadwalkan pensiun 6 Jan 2027) |
| `TTS_LIVE_TIMEOUT_SEC` | `30.0` | Timeout TTS untuk tanggapan/follow-up (kandidat menunggu) |
| `TTS_PREPARED_TIMEOUT_SEC` | `60.0` | Timeout TTS untuk intro/pertanyaan/penutup (dibuat saat prepare) |
| `TTS_CACHE` | `true` | Cache audio TTS di `data/tts_cache/` berdasarkan hash konten |
| `TTS_VOICE_HR` | `nova` | Suara OpenAI TTS untuk interviewer HR |
| `TTS_VOICE_USER` | `onyx` | Suara OpenAI TTS untuk interviewer User/Technical |
| `TTS_VOICE_MANAGER` | `alloy` | Suara OpenAI TTS untuk interviewer Manager |

### ElevenLabs (konfigurasi suara proyek)

| Variable | Default | Keterangan |
|----------|---------|------------|
| `ELEVENLABS_API_KEY` | `` | API key ElevenLabs |
| `ELEVENLABS_MODEL_PREPARED` | `eleven_multilingual_v2` | Model untuk audio yang disiapkan (kualitas tinggi) |
| `ELEVENLABS_MODEL_LIVE` | `eleven_multilingual_v2` | Sama dengan prepared agar suara konsisten |
| `ELEVENLABS_VOICE_HR` | `` | Voice ID ElevenLabs untuk HR (dari Voice Library) |
| `ELEVENLABS_VOICE_USER` | `` | Voice ID ElevenLabs untuk User/Technical |
| `ELEVENLABS_VOICE_MANAGER` | `` | Voice ID ElevenLabs untuk Manager |
| `ELEVENLABS_OUTPUT_FORMAT` | `mp3_44100_128` | Format output audio |
| `ELEVENLABS_LANGUAGE_CODE` | `` | Kode bahasa, mis. `id` (hanya untuk model `*_v2_5`) |

---

## STT (Speech-to-Text)

| Variable | Default | Keterangan |
|----------|---------|------------|
| `STT_PROVIDER` | `openai` | Provider STT: `openai` atau `deepgram` |
| `STT_MODEL` | `gpt-4o-transcribe` | Model OpenAI STT. Alternatif: `gpt-4o-mini-transcribe`, `whisper-1` |
| `DEEPGRAM_API_KEY` | `` | API key Deepgram (hanya jika `STT_PROVIDER=deepgram`) |
| `DEEPGRAM_MODEL` | `nova-3` | Model Deepgram |

---

## Perilaku Wawancara

| Variable | Default | Keterangan |
|----------|---------|------------|
| `AI_MOCK` | `false` | Harus `false`; dummy hanya tersedia untuk isian form awal |
| `MAX_FOLLOWUPS_ENABLED` | `true` | Aktifkan/matikan fitur follow-up |
| `FOLLOWUPS_DEMO` | `1` | Maks follow-up untuk mode demo (3 pertanyaan) |
| `FOLLOWUPS_SHORT` | `2` | Maks follow-up untuk mode singkat (5 pertanyaan) |
| `FOLLOWUPS_STANDARD` | `3` | Maks follow-up untuk mode standar (7 pertanyaan) |
| `RESPOND_TIMEOUT_SEC` | `60.0` | Batas total LLM tanggapan + TTS live setelah STT (detik) |
| `RETRY_LIMIT` | `2` | Maks retry per pertanyaan |
| `MAX_SESSIONS_PER_HOUR` | `5` | Rate limit sesi per user per jam |
| `ANSWER_SECONDS_JUNIOR` | `90` | Waktu jawab (detik) untuk level Junior |
| `ANSWER_SECONDS_MIDDLE` | `120` | Waktu jawab untuk level Middle |
| `ANSWER_SECONDS_SENIOR` | `120` | Waktu jawab untuk level Senior |
| `ANSWER_SECONDS_MANAGER` | `150` | Waktu jawab untuk level Manager |

---

## Estimasi Harga (USD)

Dipakai untuk laporan biaya internal per sesi di log. Cek ulang di halaman harga resmi provider.

| Variable | Default | Keterangan |
|----------|---------|------------|
| `PRICE_STT_PER_MIN` | `0.006` | gpt-4o-transcribe per menit |
| `PRICE_OPENAI_TTS_PER_1K_CHARS` | `0.02` | gpt-4o-mini-tts per 1k karakter |
| `PRICE_ELEVEN_PREPARED_PER_1K_CHARS` | `0.10` | ElevenLabs Multilingual v2 |
| `PRICE_ELEVEN_LIVE_PER_1K_CHARS` | `0.05` | ElevenLabs Flash v2.5 |
| `PRICE_FAST_IN_PER_1M` | `0.15` | gpt-4o-mini input per 1M token |
| `PRICE_FAST_OUT_PER_1M` | `0.60` | gpt-4o-mini output per 1M token |
| `PRICE_DEEP_IN_PER_1M` | `2.50` | gpt-4o input per 1M token |
| `PRICE_DEEP_OUT_PER_1M` | `10.00` | gpt-4o output per 1M token |

`STT_FALLBACK_PROVIDER` default kosong; transkripsi tetap OpenAI. Nilai PRICE_* adalah konfigurasi estimasi historis, bukan harga otomatis atau tagihan aktual. Karena live TTS kini Multilingual v2, jangan memakai asumsi biaya Flash untuk laporan biaya.

Bahasa dipilih per sesi di form/API (`language=id|en`), bukan environment global. Fullscreen dan mirror adalah opsi browser, bukan pengaturan `.env`. STT tetap model yang sama; bahasa audio tidak dipaksa ke Indonesia.

## Konfigurasi benchmark Mohler

[Runner Mohler](mohler-benchmark.md) memakai konfigurasi `OPENAI_API_KEY` dan `MODEL_DEEP` yang sudah ada melalui klien aplikasi. Tidak ada environment variable baru. Download/prepare tidak memanggil AI; `run --run-paid` mengirim pertanyaan, jawaban instruktur dan jawaban peserta ke OpenAI, tanpa skor manusia. Tidak memakai STT/TTS, ElevenLabs, Redis atau sesi database. Kredensial tetap hanya dibaca dari environment/`.env` dan tidak dimasukkan ke manifest/report.
