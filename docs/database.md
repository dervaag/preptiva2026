# Skema Database

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Database: **PostgreSQL 16** (produksi) / **SQLite** (dev)

## Pembaruan keamanan dan retensi — 7 November 2026

Sumber skema aktif adalah model SQLAlchemy; beberapa kolom dalam rancangan historis di bawah belum dipakai. Fitur keamanan menambah tabel berikut tanpa memindahkan data PostgreSQL:

| Tabel | Isi dan relasi |
| --- | --- |
| `auth_sessions` | Satu baris per `user_id`, hash token, waktu login/idle/kedaluwarsa. FK akun dengan cascade. |
| `login_limits` | Bucket HMAC, penghitung dan kedaluwarsa; tanpa email/IP mentah. |
| `deletion_receipts` | ID acak, lingkup, status, jumlah data dan waktu. FK pengguna nullable dengan `SET NULL` saat akun dihapus. |
| `storage_cleanup` | Jurnal pembersihan berkas yang terikat receipt; dihapus setelah berkas berhasil dibersihkan. |

Penghapusan riwayat mencakup seluruh tabel anak, termasuk event serta input/checkpoint/ledger LangGraph. Penghapusan database dan pembuatan jurnal satu transaksi; berkas dibersihkan setelah commit agar rollback tidak menghilangkan berkas yang masih diperlukan. Detail retensi, cache per sesi dan bukti: [keamanan dan privasi](security-and-privacy.md).

SQLite memakai `AUTOINCREMENT` pada ID yang dibuat aplikasi agar ID terhapus tidak diberikan kepada akun/sesi baru. Startup meningkatkan tabel SQLite lama secara transaksional dengan mempertahankan data, relasi dan objek skema. Hentikan semua proses versi lama sebelum peningkatan SQLite. PostgreSQL tetap menggunakan sequence; tidak menjalankan rebuild SQLite.

## Rancangan awal

Tabel dibuat dari metadata SQLAlchemy melalui `init_db()` pada startup. Model aktif berada di `app/models.py`, `app/graphs/models.py`, `app/security_models.py` dan `app/privacy_models.py`. Tidak ada `sql/01_schema.sql` atau `app.scripts.dump_schema` aktif pada baseline ini. Tabel/desain historis di bawah harus dibaca bersama model aktual dan status implementasi.

---

## Tabel: `users`

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| `id` | BigInt PK | Auto-increment |
| `email` | String(190) UNIQUE | |
| `password_hash` | String(255) | bcrypt |
| `name` | String(120) | |
| `gender` | Enum(male, female) | Nullable |
| `age` | SmallInt | Nullable |
| `last_cv_text` | Text | CV terakhir yang dipakai |
| `last_cv_file` | String(255) | Path file PDF terakhir |
| `created_at` | DateTime | UTC, server default |

---

## Tabel: `interview_sessions`

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| `id` | BigInt PK | |
| `uuid` | String(36) UNIQUE | UUID v4 untuk URL publik |
| `user_id` | FK → users | CASCADE DELETE |
| `candidate_name` | String(120) | Snapshot saat buat sesi |
| `gender` | Enum | Snapshot |
| `age` | SmallInt | Snapshot |
| `job_role` | String(150) | |
| `level` | Enum(junior, middle, senior, manager) | |
| `industry` | String(80) | |
| `company` | String(150) | Nullable |
| `job_description` | Text | |
| `cv_text` | Text | Full teks CV |
| `cv_file` | String(255) | Path PDF, nullable |
| `interviewer` | Enum(hr, user, manager) | |
| `question_count` | SmallInt | 3, 5, atau 7 |
| `answer_seconds` | SmallInt | Dari config berdasarkan level |
| `max_followups` | SmallInt | Maks follow-up di sesi ini |
| `status` | Enum | Lihat tabel status di bawah |
| `cv_summary` | JSONB | Hasil parse CV oleh LLM |
| `jd_summary` | JSONB | Hasil parse JD oleh LLM |
| `script` | JSONB | `{intro, closing, fillers, detail}` — teks + path audio |
| `error_message` | String(255) | Nullable, diisi jika status=failed |
| `total_score` | Numeric(5,2) | Skor akhir 0–5 |
| `review` | JSONB | Review teks dari LLM + saran belajar |
| `star_summary` | JSONB | Agregasi STAR dari semua jawaban |
| `started_at` | DateTime | Nullable |
| `finished_at` | DateTime | Nullable |
| `created_at` | DateTime | |
| `updated_at` | DateTime | Auto-update |

**Index:**
- `idx_user_finished`: `(user_id, status, finished_at)` — untuk dashboard dan riwayat
- `idx_user_role`: `(user_id, job_role)` — untuk delta skor per role

**Status values:**

| Status | Keterangan |
|--------|------------|
| `preparing` | Worker sedang menyiapkan pertanyaan & TTS |
| `ready` | Siap dimulai |
| `running` | Wawancara sedang berlangsung |
| `scoring` | Worker sedang finalisasi |
| `done` | Selesai |
| `failed` | Error |

---

## Tabel: `session_competencies`

Satu baris per kompetensi per sesi. Composite PK: `(session_id, competency)`.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| `session_id` | FK → interview_sessions | CASCADE DELETE |
| `competency` | Enum(communication, problem_solving, technical, analytical, teamwork, adaptability, leadership) | |
| `weight` | SmallInt | Bobot preset berdasarkan tipe interviewer |
| `score` | Numeric(5,2) | Nullable: NULL = belum terukur |

---

## Tabel: `interview_questions`

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| `id` | BigInt PK | |
| `session_id` | FK → interview_sessions | CASCADE DELETE |
| `turn_no` | SmallInt | Urutan giliran dalam sesi, nullable |
| `kind` | Enum(main, follow_up) | |
| `main_order` | SmallInt | Nomor pertanyaan utama (1–7) |
| `parent_question_id` | FK → interview_questions | Self-ref, cascade, nullable |
| `slot` | String(30) | opening, background, motivation, dll. |
| `category` | String(30) | Kategori tampilan |
| `question_text` | Text | Teks pertanyaan |
| `expected_points` | JSONB | Poin yang diharapkan dalam jawaban |
| `competencies` | JSONB | Kompetensi yang dinilai di pertanyaan ini |
| `follow_up_reason` | String(30) | too_short, no_result, too_general, dll. |
| `audio_file` | String(255) | Nama file MP3, nullable |
| `created_at` | DateTime | |

**Index:**
- `idx_session_main`: `(session_id, main_order, kind)` — untuk ordering pertanyaan

---

## Tabel: `interview_answers`

Satu baris per pertanyaan (unique constraint pada `question_id`).

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| `id` | BigInt PK | |
| `question_id` | FK → interview_questions UNIQUE | CASCADE DELETE |
| `audio_file` | String(255) | Nama file audio jawaban, dihapus setelah eval |
| `transcript` | Text | Transkrip STT |
| `duration_sec` | Numeric(6,2) | Durasi rekaman |
| `wpm` | SmallInt | Kata per menit |
| `filler_count` | SmallInt | Jumlah kata filler (eh, um, dll.) |
| `retry_count` | SmallInt | Berapa kali retry (maks 2) |
| `timed_out` | Boolean | Timer habis saat menjawab |
| `think_sec` | Numeric(6,2) | Waktu berpikir sebelum jawab |
| `response_action` | Enum(next, follow_up, redirect) | Keputusan AI |
| `response_text` | Text | Teks tanggapan AI |
| `response_audio_file` | String(255) | Audio tanggapan AI |
| `competency_scores` | JSONB | `{competency: {score, evidence}}` |
| `star` | JSONB | `{situation, task, action, result}` boolean |
| `score_total` | SmallInt | Skor total pertanyaan ini |
| `score_label` | String(20) | Label teks skor |
| `feedback` | JSONB | `{strengths, improvements, better_answer_tip}` |
| `eval_status` | Enum(pending, done, failed, skipped) | Status evaluasi LLM |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

## Relasi

```
users (1)
  └─ (N) interview_sessions
              └─ (N) session_competencies
              └─ (N) interview_questions
                          └─ (N) interview_questions (self-ref follow_up)
                          └─ (1) interview_answers
```

---

## Catatan Compatibility

- `BigId = BigInteger().with_variant(Integer, "sqlite")` — BigInt di Postgres, Integer di SQLite
- `JSONType = JSON().with_variant(JSONB(), "postgresql")` — JSONB di Postgres (bisa diindex), JSON di SQLite
- Semua enum di-declare dengan nama (`name="gender"`, dll.) agar Postgres hanya buat satu TYPE per nama
- Semua timestamp dalam UTC

## Pembaruan 5 November 2026

Lihat [acuan dan snapshot rubrik](assessment-reference.md), [persiapan perangkat dan stream jawaban](session-experience.md), serta [log runtime](logging.md). Setiap perubahan selanjutnya wajib memperbarui Markdown terkait dan [changelog](CHANGELOG.md).

Snapshot acuan disimpan dalam kolom JSON yang sudah ada: `interview_sessions.script.assessment` (version, sha256, rubric, sources, weights, validated). Tidak ada migrasi skema. Sesi lama tidak di-backfill agar tidak salah mengklaim asal rubrik.

## Identitas publik dan bahasa

Kolom `interview_sessions.uuid` yang sudah ada digunakan pada seluruh URL dan payload ID sesi publik. `id` numerik internal tetap menjaga FK dan job yang sudah ada. Bahasa disnapshot pada `script.settings.language` (`id`/`en`); sesi lama default `id`. Snapshot rubrik versi baru `2026-11-05.2` membedakan fokus persona dan tidak memberi penalti code-switching. Tidak diperlukan migrasi skema atau penghapusan sesi lama.

## Penyimpanan benchmark eksternal

[Dataset Mohler](mohler-benchmark.md) disimpan sebagai Parquet sumber, manifest unduhan dan JSON di `data/external/mohler-v1/`. Pilot berada di `data/external/mohler-pilot-50/`; masukan AI dan label manusia dipisahkan dan diikat hash. Hasil run/report juga berupa berkas lokal. Tidak ada tabel, migrasi, seed pengguna atau perubahan snapshot sesi untuk benchmark ini. `data/` diabaikan Git dan dikecualikan dari image Docker.

## Snapshot bahasa dan data graph terkini

`script.settings.language` mengatur wawancara, `feedback_language` mengatur penjelasan hasil (fallback: bahasa wawancara). `language_retry` tidak menulis InterviewAnswer atau GraphTurnInput untuk jawaban ditolak; ledger/checkpoint graph dapat mencatat operasi gagal atau STT yang sudah selesai tanpa menerimanya sebagai unit penilaian. Graph memakai tabel `graph_executions`, `graph_operations`, `graph_checkpoints`, `graph_checkpoint_writes`, `graph_turn_inputs`; data domain tetap otoritas. Tidak ada kolom baru untuk gate bahasa.
