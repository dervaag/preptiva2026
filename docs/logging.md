# Panduan log runtime

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Diperbarui: 7 November 2026. Log perubahan kode terpisah di [CHANGELOG.md](CHANGELOG.md).

## Format dan lokasi

`app/log.py` mengeluarkan satu objek JSON per baris ke stdout. Gunakan terminal Uvicorn/arq atau `docker compose logs -f web worker`. Tidak ada file log persisten otomatis; retensi ditentukan pengelola proses atau platform hosting.

Field umum: `ts` (Unix timestamp), `event`, `rid` (request ID), `sid` (session ID), `question_id`. Header respons `X-Request-ID` menghubungkan request HTTP dengan event pipeline. Pada pengiriman jawaban, `sid` adalah UUID publik sesi dan `question_id` adalah ID pertanyaan; keduanya ikut pada log provider/validasi dalam pemrosesan itu. Worker dapat memakai ID numerik internal sebagai `sid`. `session_id` tambahan muncul pada sebagian event.

Contoh sintetis, bukan log pengguna:

```json
{"ts":0,"event":"step","rid":"contoh","sid":123,"step":"stt","ms":1800,"ok":true,"provider":"openai","model":"gpt-4o-transcribe"}
```

## Event yang berguna

| Event/step | Arti |
| --- | --- |
| `startup` | Mode aplikasi, model STT, backend job; `ai_mock` harus false. |
| `step: stt` | Waktu API transkripsi dalam milidetik; tidak termasuk seluruh waktu upload browser. |
| `step: llm:respond` | Waktu membuat keputusan/tanggapan, bukan STT. |
| `step: tts`, `tts_usage` | Durasi pembuatan suara, provider, model, karakter, cache. |
| `tts_rate_limit` | Retry batas konkurensi/rate limit ElevenLabs. |
| `tts_failed` | Pembuatan suara gagal; tidak berpindah suara otomatis. |
| `documents_chunked` | Jumlah karakter CV/JD dan chunk; tidak memuat teks pribadi. |
| `llm_usage` | Token input/output per langkah; bisa dipakai untuk estimasi biaya. |
| `stt_usage` | Durasi audio yang diproses; bukan durasi keseluruhan sesi. |
| `answer` | Aksi next/follow_up/redirect dan metrik jawaban. |
| `session_closed` | Pengiriman penutupan karena halaman ditinggalkan; idempotent. |
| `ai_output_rejected` | Keluaran AI ditolak: `stage`, `reason`, dan `attempt` (1 atau 2). Satu perbaikan keluaran diperbolehkan; bukan retry tanpa batas. |
| `answer_failed` | Pemrosesan jawaban gagal, baik stream maupun respons JSON biasa. Memuat `error_type`, `stage`, `reason`, dan `frames` lokasi kode tanpa pesan exception atau variabel lokal. |
| `evaluate_validation` | Kutipan atau kompetensi keluaran evaluator tidak memenuhi pemeriksaan. |
| `prepare_failed`, `evaluate_failed`, `finalize_failed` | Kesalahan tahap background. |

## Membaca waktu tunggu

Waktu setelah Kirim kira-kira: upload + STT + LLM respond + TTS + overhead database/network. Evaluasi kompetensi berjalan background dan normalnya tidak menahan tanggapan. UI streaming menampilkan transkrip setelah STT meskipun LLM/TTS belum selesai. Cache TTS tidak menghasilkan panggilan provider baru.

## Menelusuri kegagalan jawaban

HTTP `200` dari OpenAI hanya berarti permintaan provider berhasil; aplikasi masih memeriksa struktur, persona, kompetensi, dan kutipan jawabannya. HTTP `200` pada `/answers?stream=true` berarti stream telah dibuka. Hasil akhirnya ada pada event `result` atau `error`; event error menyertakan `request_id` untuk dicocokkan dengan `rid` di log.

Kode `reason` antara lain `schema_invalid`, `action_invalid`, `reference_required`, `reference_invalid`, dan `question_constraints`. `stage` membedakan `respond` dari `adapt_question`; kesalahan lain memakai `answer` dengan `unexpected_error`, lalu periksa `error_type` dan `frames`. Frame hanya berisi berkas relatif aplikasi, nama fungsi, dan nomor baris, termasuk lokasi dari penyebab exception. Isi keluaran model, pesan Pydantic, dan transkrip tidak dicetak. Penolakan keluaran AI setelah dua percobaan menghasilkan HTTP `502` pada respons biasa atau event `error` pada stream; jangan menganggap jawaban sudah tersimpan hanya karena status stream `200`.

Kutipan singkat seperti “Belum.” boleh menjadi sumber pertanyaan klarifikasi hanya bila merupakan seluruh jawaban asli. Ini tidak melonggarkan bukti penilaian kompetensi. Pertanyaan adaptif yang tetap tidak memenuhi aturan ditolak, bukan diganti diam-diam dengan keluaran tanpa sumber.

`GET /sw.js` yang menghasilkan `404` perlu ditelusuri terpisah dari `answer_failed`: frontend saat ini tidak mendaftarkan service worker. Jangan mengaitkan keduanya tanpa bukti dari request browser.

## Privasi dan operasional

Jangan mencatat API key, header Authorization, cookie, isi CV, atau transkrip mentah. Jangan menyalin log produksi ke Markdown. ID sesi dan request juga perlu perlindungan akses serta retensi yang sesuai. Error provider bisa memuat detail teknis; lakukan redaksi sebelum membagikan log. Konsumsi token/karakter adalah estimasi biaya; tagihan provider menjadi sumber biaya aktual.

## Diagnostik koreksi bahasa

Event `answer_language_retry` menandai permintaan ulang, bukan jawaban diterima atau skor gagal. Event ini tidak memasukkan transkrip ke log. Pada graph, operasi deteksi/accept yang gagal tidak boleh diartikan sebagai jawaban penilaian tersimpan. Periksa hasil domain/state sebelum menyimpulkan progres. Tidak ada inferensi biaya/latensi baru dari event ini.
