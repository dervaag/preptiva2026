# Referensi API

Pembaruan bahasa jawaban: `/api/sessions/{sid}/answers` dapat mengembalikan HTTP 200 dengan `action: language_retry`, `question_id`, `expected_language`, `transcript`, `response_text`, `response_audio_url` dan `is_last: false`. Pada streaming, payload dikirim sebagai event `type: result`. Ini permintaan mengulang dalam bahasa sesi, bukan jawaban terkomit; jangan memajukan giliran atau memanggil finish. `/api/sessions/{sid}/speech/language/{question_id}` menyediakan suara pengingat tetap bagi pertanyaan aktif milik pengguna. Lihat [kebijakan bahasa](languages-and-personas.md).

Pembaruan bahasa hasil, 7 November 2026: `POST /api/sessions` menerima form opsional `feedback_language=id|en`. Browser mengisinya dari bahasa platform saat sesi dibuat; jika tidak dikirim, server memakai `language` wawancara. Nilai disimpan di snapshot sesi. `GET /api/sessions/{sid}/result` menyertakan `feedback_language`; untuk sesi lama field ini menggunakan fallback bahasa wawancara. Mengganti bahasa UI kemudian tidak memicu terjemahan/penilaian ulang hasil tersimpan. Lihat [kebijakan hasil](results.md).

Base URL: `http://localhost:8000`

## Implementasi 7 November 2026

`POST /api/sessions/{uuid}/start` menandai sesi `ready` menjadi `running` setelah pemeriksaan perangkat browser. Endpoint bersifat idempotent untuk sesi yang masih `running`; sesi terminal ditolak 409. Jawaban hanya diterima pada sesi `running`. `finish` menolak 409 sampai semua pertanyaan aktif (termasuk follow-up) terjawab. Lihat [status implementasi](implementation-status.md) untuk perbedaan terhadap kontrak historis di bawah.

`state.answer_seconds`, `state.max_followups`, dan `state.retry_limit` mengikuti konfigurasi saat sesi dibuat. Batas retry/durasi juga divalidasi oleh server sebelum panggilan STT. Timeout tanggapan mengembalikan 504 pada endpoint JSON atau event `error` pada NDJSON; jawaban belum disimpan dan dapat dikirim ulang. Penolakan provider mengembalikan 502/event `error` dengan pesan aman tanpa kredensial atau isi respons mentah provider.

Autentikasi: cookie `isim_session` membawa token acak yang hash-nya diverifikasi terhadap sesi aktif di database. Login/registrasi tidak memerlukan login sebelumnya; logout idempoten. Endpoint privat, termasuk `/api/auth/session` dan `/api/auth/password`, memerlukan sesi aktif. Kebijakan dan bukti: [keamanan dan privasi](security-and-privacy.md).

---

## Auth

### POST /api/auth/register
Daftar akun baru.

**Body (JSON):**
```json
{
  "name": "Budi Santoso",
  "email": "budi@example.com",
  "password": "budi1234",
  "password_confirm": "budi1234",
  "gender": "male",
  "age": 28,
  "agree": true
}
```

**Response 200:**
```json
{ "id": 1, "name": "Budi Santoso" }
```

**Validasi:**
- `name`: 2–120 karakter
- `email`: format valid, unik
- `password`: min 8 karakter, mengandung huruf + angka
- `gender`: `"male"` atau `"female"`
- `age`: 15–80
- `agree`: harus `true`

---

### POST /api/auth/login
Login dengan email dan password.

**Body (JSON):**
```json
{ "email": "demo@interview.local", "password": "demo1234" }
```

**Response 200:**
```json
{ "id": 1, "name": "Demo User" }
```

**Error:**
- `401` — email atau password salah
- `409` — akun masih aktif pada browser/perangkat lain; sesi pertama tetap berlaku
- `429` — batas percobaan tercapai; header `Retry-After` menyatakan detik tunggu

---

### POST /api/auth/logout
Cabut token sesi aktif di database dan hapus cookie. Cookie yang disalin sebelum logout tidak dapat digunakan kembali.

**Response 200:**
```json
{ "ok": true }
```

---

### GET /api/me
Data user yang sedang login.

**Response 200:**
```json
{
  "id": 1,
  "email": "demo@interview.local",
  "name": "Demo User",
  "gender": "male",
  "age": 28,
  "has_cv": true,
  "cv_preview": "Nama: Budi Santoso\nEmail: ..."
}
```

---

## Endpoint keamanan dan penghapusan

| Endpoint | Masukan / hasil |
| --- | --- |
| `GET /api/auth/session` | Batas idle/absolut dan waktu kedaluwarsa; tidak mengembalikan token. |
| `POST /api/auth/password` | JSON `current_password`, `new_password`, `password_confirm`; mengganti password dan meminta login ulang. |
| `PATCH /api/profile` | Perubahan email memerlukan form `current_password`; perubahan nama saja tidak. |
| `GET /api/privacy/policy` | Kebijakan retensi dan batas penghapusan. |
| `GET /api/privacy/receipts` | Maksimal 20 tanda terima terbaru milik pengguna aktif. |
| `DELETE /api/profile/cv` | JSON `password` dan `confirmation: "HAPUS CV"`; hapus CV profil, bukan snapshot sesi lama. |
| `DELETE /api/sessions/{uuid}` | JSON `password` dan `confirmation: "HAPUS"`; hapus satu sesi milik pengguna. |
| `DELETE /api/sessions` | JSON `password` dan `confirmation: "HAPUS RIWAYAT"`; hapus seluruh riwayat pengguna. |
| `DELETE /api/profile` | JSON `password` dan `confirmation: "HAPUS AKUN"`; hapus akun dan data turunannya, cabut login. |

Penghapusan mengembalikan objek `receipt`: ID, lingkup, waktu, jumlah data, `database_deleted`, `files_pending` dan status `complete` atau `pending_files`. Status tertunda berarti database sudah dihapus dan worker masih perlu membersihkan berkas. Tanda terima akun yang sudah dihapus hanya tersedia pada respons penghapusan; tidak ada endpoint unduhan publik. Konfirmasi salah ditolak 422, password salah 403, data pengguna lain 404, dan pembatasan konfirmasi password 429. Tidak ada password atau isi CV/jawaban dalam receipt.

Mutasi browser wajib berasal dari Origin/Referer aplikasi; sumber asing ditolak 403. API privat dan halaman HTML memakai `Cache-Control: no-store`. Ukuran total permintaan melebihi batas ditolak 413, termasuk body chunked.

## Sessions

### POST /api/sessions
Buat sesi wawancara baru.

**Content-Type:** `multipart/form-data`

| Field | Tipe | Wajib | Keterangan |
|-------|------|-------|------------|
| `candidate_name` | string | ✓ | |
| `gender` | `male`/`female` | ✓ | |
| `age` | integer | ✓ | 15–80 |
| `job_role` | string | ✓ | mis. "Backend Developer" |
| `level` | `junior`/`middle`/`senior`/`manager` | ✓ | |
| `job_description` | string | ✓ | min 30 karakter |
| `industry` | string | ✓ | |
| `company` | string | – | opsional |
| `question_count` | integer | – | `3`, `5`, atau `7` (default 7) |
| `interviewer` | `hr`/`user`/`manager` | ✓ | |
| `language` | `id`/`en` | – | Bahasa sesi, default `id`; jawaban campuran diterima |
| `consent` | boolean | ✓ | harus `true` |
| `use_last_cv` | boolean | – | pakai CV dari sesi sebelumnya |
| `cv_text` | string | * | teks CV (min 200 karakter) |
| `cv_pdf` | file | * | PDF CV (maks 5 MB) |

\* Salah satu dari `cv_text`, `cv_pdf`, atau `use_last_cv=true` wajib ada.

**Response 200:**
```json
{ "session_id": "a8916f7e-bb7b-4380-b991-6f5af381a4f4", "status": "preparing" }
```

**Rate limit:** maks 5 sesi per jam per user.

---

### GET /api/sessions
Daftar semua sesi milik user.

**Response 200:**
```json
{
  "items": [
    {
      "id": "a8916f7e-bb7b-4380-b991-6f5af381a4f4",
      "job_role": "Backend Developer",
      "level": "senior",
      "interviewer": "user",
      "company": "PT Inovasi Digital",
      "status": "done",
      "question_count": 7,
      "total_score": 3.8,
      "label": "Baik",
      "created_at": "2026-11-05T10:00:00",
      "finished_at": "2026-11-05T10:45:00"
    }
  ]
}
```

---

### GET /api/sessions/{id}/state
State sesi saat ini. Di-poll oleh browser setiap 1.5 detik saat status `"preparing"`.

**Response 200:**
```json
{
  "session_id": "a8916f7e-bb7b-4380-b991-6f5af381a4f4",
  "status": "ready",
  "error": null,
  "interviewer": "user",
  "persona": { "name": "Ari Wibowo", "title": "Technical Lead" },
  "job_role": "Backend Developer",
  "level": "senior",
  "question_count": 7,
  "answer_seconds": 120,
  "retry_limit": 2,
  "max_followups": 3,
  "script": {
    "intro": { "text": "Selamat datang...", "audio_url": "/api/sessions/a8916f7e-bb7b-4380-b991-6f5af381a4f4/audio/intro.mp3" },
    "closing": { "text": "Terima kasih...", "audio_url": "..." },
    "fillers": [{ "text": "Baik.", "audio_url": "..." }]
  },
  "questions": [
    {
      "id": 1,
      "kind": "main",
      "main_order": 1,
      "slot": "opening",
      "category": "Perkenalan",
      "question_text": "Silakan perkenalkan diri Anda...",
      "audio_url": "/api/sessions/a8916f7e-bb7b-4380-b991-6f5af381a4f4/audio/q1.mp3"
    }
  ],
  "current_turn": { ... },
  "answered_mains": 0
}
```

**Status values:**
| Status | Arti |
|--------|------|
| `preparing` | Worker sedang generate pertanyaan & TTS |
| `ready` | Siap dimulai |
| `running` | Wawancara sedang berlangsung |
| `scoring` | Worker sedang finalisasi skor |
| `done` | Selesai, hasil tersedia |
| `failed` | Error saat prepare atau finalize |

---

### POST /api/sessions/{id}/answers
Kirim jawaban audio untuk satu pertanyaan.

**Content-Type:** `multipart/form-data`

| Field | Tipe | Keterangan |
|-------|------|------------|
| `question_id` | integer | ID pertanyaan yang dijawab |
| `audio` | file | Blob audio (webm/ogg/mp4/mp3/wav, maks 25 MB) |
| `duration_ms` | integer | Durasi rekaman dalam ms |
| `retry_count` | integer | Jumlah retry (0 = jawaban pertama) |
| `think_ms` | integer | Waktu berpikir sebelum jawab (ms), opsional |
| `timed_out` | boolean | `true` jika timer habis |

**Response 200:**
```json
{
  "answer_id": 10,
  "transcript": "Saya menangani API yang lambat dengan...",
  "action": "follow_up",
  "follow_up_reason": "no_result",
  "response_text": "Menarik. Lalu apa hasil yang Anda capai?",
  "response_audio_url": "/api/sessions/a8916f7e-bb7b-4380-b991-6f5af381a4f4/audio/r_abc123.mp3",
  "follow_up_question": {
    "id": 8,
    "kind": "follow_up",
    "main_order": 1,
    "question_text": "Lalu apa hasil yang Anda capai?",
    "audio_url": "/api/sessions/a8916f7e-bb7b-4380-b991-6f5af381a4f4/audio/r_abc123.mp3"
  },
  "next_question": null,
  "is_last": false,
  "closing": null
}
```

**`action` values:**
| Action | Arti |
|--------|------|
| `next` | Lanjut ke pertanyaan berikutnya |
| `follow_up` | AI menggali lebih dalam |
| `redirect` | AI mengarahkan ulang jawaban |

---

### POST /api/sessions/{id}/finish
Tandai sesi selesai, mulai proses scoring.

**Response 200:**
```json
{ "status": "scoring" }
```

---

### GET /api/sessions/{id}/result
Hasil lengkap sesi (hanya tersedia saat `status=done`).

**Response 200:**
```json
{
  "session_id": "a8916f7e-bb7b-4380-b991-6f5af381a4f4",
  "status": "done",
  "job_role": "Backend Developer",
  "level": "senior",
  "total_score": 3.8,
  "label": "Baik",
  "previous_score": 3.2,
  "delta": 0.6,
  "competencies": [
    {
      "key": "technical",
      "name": "Technical",
      "weight": 30,
      "score": 4.0,
      "evidence": ["saya cek query-nya pakai EXPLAIN"]
    }
  ],
  "unmeasured": [],
  "review": {
    "summary": "Kandidat menunjukkan...",
    "strengths": ["Analisis masalah runtut"],
    "improvements": ["Sertakan angka dampak"],
    "study_recommendations": [
      {
        "topic": "Query optimization",
        "reason": "...",
        "action": "..."
      }
    ]
  },
  "star_summary": { "situation": true, "task": true, "action": true, "result": false },
  "items": [ ... ]
}
```

---

### GET /api/sessions/{id}/audio/{name}
Stream file audio MP3 (pertanyaan, intro, tanggapan AI).

**Response:** `audio/mpeg` stream dengan `Cache-Control: private, max-age=3600`

---

## Dashboard

### GET /api/dashboard
Data ringkasan untuk halaman dashboard.

**Response 200:**
```json
{
  "total_sessions": 5,
  "avg_score": 3.6,
  "best_score": 4.2,
  "recent_sessions": [ ... ],
  "competency_trend": { ... }
}
```

---

## Health Check

### GET /health
Status kesehatan aplikasi.

**Response 200:**
```json
{
  "ok": true,
  "version": "0.1.0",
  "db": true,
  "redis": null,
  "ai_mock": true
}
```

`redis: null` berarti Redis tidak dikonfigurasi (mode in-process).

## Pembaruan 5 November 2026

Lihat [acuan dan snapshot rubrik](assessment-reference.md), [persiapan perangkat dan stream jawaban](session-experience.md), serta [log runtime](logging.md). Setiap perubahan selanjutnya wajib memperbarui Markdown terkait dan [changelog](CHANGELOG.md).

`POST /api/sessions/{id}/answers?stream=true` menerima multipart yang sama dan mengeluarkan NDJSON `transcript`, `pending`, `result`, atau `error`. Tanpa parameter ini format JSON tetap berlaku. `POST /api/sessions/{id}/close` memerlukan autentikasi dan kepemilikan sesi; menutup sesi ready/running sebagai failed, idempotent untuk status terminal.

## UUID dan bahasa sesi (5 November 2026)

- Semua `{id}` sesi di API adalah UUID publik; ID numerik lama ditolak (404). Otorisasi tetap berdasarkan pengguna pemilik, bukan hanya pengetahuan UUID.
- Create menerima `language=id|en` (default `id`). Bahasa lain ditolak 422.
- `session_id` pada create/state/result dan trend dashboard, serta `items[].id` pada daftar sesi, berupa UUID. URL web `/sesi/{uuid}/ruang` dan `/sesi/{uuid}/hasil` mengikuti UUID yang sama.
- ID pertanyaan/jawaban tetap numerik; ini bukan ID sesi. Primary key numerik internal tetap digunakan untuk relasi dan job, tidak dipublikasikan sebagai ID sesi.
- Tidak ada migrasi tipe primary key; kolom UUID unik yang sudah tersedia digunakan sebagai identitas publik.

## Cleansing dan batas dokumen

CV/JD dibersihkan sebelum penyimpanan sesi baru, termasuk CV yang dipakai ulang. PDF <=5 MB dan <=30 halaman; CV 200–60.000 karakter; JD 30–40.000 karakter setelah cleansing. PDF terlalu panjang mendapat 422; teks melebihi batas mendapat 413. Dokumen panjang dipecah saat ekstraksi AI, bukan dipotong di awal. Lihat [document-processing.md](document-processing.md).


## Pembaruan wawancara adaptif dan panel — 7 November 2026

`POST /api/sessions` menerima field form opsional `career_stage` (`auto`, `student`, `fresh_graduate`, `experienced`, `career_switcher`) dan `panel` yang diulang 2–3 kali dengan persona berbeda (`hr`, `user`, `manager`). Tanpa panel, field `interviewer` tetap menentukan satu persona. Pada panel, anggota pertama menjadi host; jumlah pertanyaan 3/5/7 adalah total sesi. Seluruh voice anggota dicek sebelum sesi dibuat.

State menyertakan `panel`. Setiap pertanyaan publik menyertakan `interviewer` dan `persona`; respons jawaban menyertakan `response_interviewer`. `next_question` dapat berbeda dari rencana awal karena dibentuk ulang berdasarkan percakapan. Gunakan pertanyaan/audio dari respons terbaru. Follow-up memakai pembicara yang sama dengan pertanyaan utama.

Result menyertakan `panel_results` (skor dan kompetensi tiap persona). Field lama tetap tersedia. Metadata panduan/profil/pembagian giliran disnapshot dalam JSON script, tanpa kolom database baru. Sesi lama tanpa flag adaptasi mempertahankan pertanyaan lama. API tidak menandai rubrik sebagai tervalidasi hanya karena panel atau guidebook sudah aktif.


## Interupsi pertanyaan dan bukti — 7 November 2026

- `POST /api/sessions/{uuid}/interrupt` menerima JSON `{question_id, reason}` (`tab_hidden|offline|reload|device_lost`). Jawaban `{already_completed, state}`. Interupsi menghentikan pertanyaan, bukan sesi; checkpoint menyimpan ID interupsi dan waktu nol. Jika jawaban sudah tersimpan, `already_completed=true` tanpa menginterupsi giliran berikutnya.
- `POST /api/sessions/{uuid}/recover` menerima JSON `{question_id, interruption_id, action}`. `retry` mengembalikan state dengan pertanyaan sama dan waktu penuh; `next` menyimpan jawaban berstatus dilewati dan mengembalikan payload jawaban normal. Perintah berulang idempoten; status yang kedaluwarsa ditolak 409.
- `answers` menerima salah satu `audio` atau `text_answer` (1–8.000 karakter), bersama field durasi/pertanyaan yang sudah ada. Jawaban teks melewati STT. Audio hasil dapat `null` jika TTS gagal. Payload menambahkan `turn_id`, `input_mode`, `skipped`, `source_refs`.
- `state.checkpoint` menyediakan fase, pertanyaan, pembicara dan status interupsi. `finish` juga menerima `evaluation_failed` untuk mengantrekan penilaian ulang; jawaban tetap tersimpan.
- `result.coverage` terpisah dari skor untuk sesi dengan kebijakan bukti baru. `competency_scores` menambahkan status, kecukupan, provisional, alasan, serta rujukan kutipan/offset. Skor sementara tidak masuk agregat baru. Sesi lama mempertahankan skor/snapshot historis.

## Benchmark eksternal dan API sesi

[Impor dan evaluasi Mohler](mohler-benchmark.md) berjalan melalui CLI `validation/mohler.py`, bukan endpoint HTTP. Tidak ada endpoint impor dataset atau perubahan kontrak `result`, `panel_results`, skor sesi maupun `validated` akibat penambahan benchmark. Data jawaban akademik dan labelnya tidak disimpan sebagai wawancara pengguna. Keluaran benchmark belum tersedia karena run model belum dijalankan.
