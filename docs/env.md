# Referensi Environment Variables

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

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
| `COOKIE_SECURE` | `false` | Set `true` setelah HTTPS aktif (wajib untuk deployment HTTPS; wawancara hanya desktop/laptop) |

### Keamanan akun dan retensi

| Variable | Default | Keterangan |
| --- | --- | --- |
| `AUTH_LOGIN_MAX_ATTEMPTS` | `5` | Percobaan login per akun per jendela; konfirmasi password memakai bucket terpisah. |
| `AUTH_LOGIN_IP_MAX_ATTEMPTS` | `50` | Percobaan per alamat peer; registrasi dan konfirmasi password memakai bucket terpisah. |
| `AUTH_LOGIN_WINDOW_SECONDS` | `900` | Jendela pembatasan, 15 menit. |
| `AUTH_IDLE_SECONDS` | `1800` | Sesi login berakhir setelah 30 menit tanpa request terautentikasi. |
| `AUTH_ABSOLUTE_SECONDS` | `43200` | Batas mutlak sesi login, 12 jam. |
| `RETENTION_ENABLED` | `true` | Maintenance umur data saat worker mulai dan setiap jam. Jurnal penghapusan pengguna tetap diulang walaupun false. |
| `RETENTION_AUDIO_DAYS` | `7` | Masa simpan berkas suara/cache TTS. |
| `RETENTION_HISTORY_DAYS` | `90` | Riwayat, transkrip, hasil dan CV/JD yang disalin ke sesi. |
| `RETENTION_RECEIPT_DAYS` | `30` | Tanda terima yang sudah selesai; pekerjaan tertunda tetap disimpan. |
| `MAX_REQUEST_BYTES` | `31457280` | Batas total HTTP 30 MiB sebelum parsing, termasuk transfer chunked; batas PDF/audio per berkas tetap berlaku. |

CV profil tidak kedaluwarsa otomatis. Login kedua ditolak selama sesi pertama aktif. Detail cakupan dan batas penghapusan: [keamanan dan privasi](security-and-privacy.md).

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
| `MODEL_FAST` | `gpt-4o-mini` | Model untuk parse CV/JD dan respons teks; STT memakai STT_MODEL |
| `MODEL_DEEP` | `gpt-4o` | Model untuk generate pertanyaan, evaluate, summarize |

---

## TTS (Text-to-Speech)

| Variable | Default | Keterangan |
|----------|---------|------------|
| `TTS_PROVIDER` | `elevenlabs` | Provider tunggal; tidak berpindah suara saat gagal |
| `TTS_LIVE_TIMEOUT_SEC` | `30.0` | Timeout TTS untuk tanggapan/follow-up (kandidat menunggu) |
| `TTS_PREPARED_TIMEOUT_SEC` | `60.0` | Timeout TTS untuk intro/pertanyaan/penutup (dibuat saat prepare) |
| `TTS_CACHE` | `true` | Cache TTS berdasarkan hash konten dalam `data/audio/<uuid>/cache/`, terpisah per sesi. Cache global lama dibersihkan maintenance. |

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
| `STT_PROVIDER` | `openai` | Provider STT: hanya `openai` |
| `STT_MODEL` | `gpt-4o-transcribe` | Model OpenAI STT. Alternatif: `gpt-4o-mini-transcribe`, `whisper-1` |

---

## Perilaku Wawancara

| Variable | Default | Keterangan |
|----------|---------|------------|
| `AI_MOCK` | `false` | Harus `false`; startup menolak true; tidak ada wawancara dummy |
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

## Konfigurasi historis yang tidak aktif

`TTS_MODEL`, `TTS_VOICE_*`, `DEEPGRAM_*` dan `PRICE_*` tidak dibaca oleh alur aktif. Jangan menggunakannya untuk mengaktifkan fallback atau mengklaim biaya aktual. Tidak ada harga provider yang otomatis diperbarui dari environment. `DB_PASSWORD` dibaca Compose; kunci provider hanya berada di server.

## Orkestrasi dan realtime

| Variable | Default kode | Penggunaan |
| --- | --- | --- |
| `ORCHESTRATION_ENGINE` | `legacy` | `legacy` atau `langgraph`, dipin per sesi baru |
| `REALTIME_VOICE_ENABLED` | `true` | Transport suara realtime untuk sesi baru |
| `VAD_SILENCE_MS` | `1200` | Jeda VAD yang dikirim ke transkripsi realtime |
| `VAD_THRESHOLD` | `0.5` | Ambang VAD dalam rentang konfigurasi |
| `PUBLIC_ORIGIN` | kosong | Origin HTTPS eksternal yang tepat untuk proxy/tunnel; bukan daftar bebas origin |

Lihat [graph](langgraph-orchestration.md) dan [realtime](realtime-voice.md). `STT_FALLBACK_PROVIDER` harus kosong. Gate bahasa lokal tidak memerlukan environment variable atau panggilan LLM tambahan.

Bahasa wawancara dipilih per sesi (`language=id|en`); bahasa hasil (`feedback_language`) diambil dari UI saat sesi dibuat. Keduanya bukan environment global. Fullscreen dan mirror adalah opsi browser, bukan pengaturan `.env`. STT tetap model yang sama; bahasa audio tidak dipaksa ke Indonesia.

## Konfigurasi benchmark Mohler

[Runner Mohler](mohler-benchmark.md) memakai konfigurasi `OPENAI_API_KEY` dan `MODEL_DEEP` yang sudah ada melalui klien aplikasi. Tidak ada environment variable baru. Download/prepare tidak memanggil AI; `run --run-paid` mengirim pertanyaan, jawaban instruktur dan jawaban peserta ke OpenAI, tanpa skor manusia. Tidak memakai STT/TTS, ElevenLabs, Redis atau sesi database. Kredensial tetap hanya dibaca dari environment/`.env` dan tidak dimasukkan ke manifest/report.
