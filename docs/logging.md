# Panduan log runtime

Diperbarui: 5 November 2026. Log perubahan kode terpisah di [CHANGELOG.md](CHANGELOG.md).

## Format dan lokasi

`app/log.py` mengeluarkan satu objek JSON per baris ke stdout. Gunakan terminal Uvicorn/arq atau `docker compose logs -f web worker`. Tidak ada file log persisten otomatis; retensi ditentukan pengelola proses atau platform hosting.

Field umum: `ts` (Unix timestamp), `event`, `rid` (request ID), `sid` (session ID). Header respons `X-Request-ID` menghubungkan request HTTP dengan event pipeline. `session_id` tambahan muncul pada sebagian event.

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
| `answer_stream_failed` | Stream jawaban gagal; periksa rid dan event sebelumnya. |
| `evaluate_validation` | Kutipan atau kompetensi keluaran evaluator tidak memenuhi pemeriksaan. |
| `prepare_failed`, `evaluate_failed`, `finalize_failed` | Kesalahan tahap background. |

## Membaca waktu tunggu

Waktu setelah Kirim kira-kira: upload + STT + LLM respond + TTS + overhead database/network. Evaluasi kompetensi berjalan background dan normalnya tidak menahan tanggapan. UI streaming menampilkan transkrip setelah STT meskipun LLM/TTS belum selesai. Cache TTS tidak menghasilkan panggilan provider baru.

## Privasi dan operasional

Jangan mencatat API key, header Authorization, cookie, isi CV, atau transkrip mentah. Jangan menyalin log produksi ke Markdown. ID sesi dan request juga perlu perlindungan akses serta retensi yang sesuai. Error provider bisa memuat detail teknis; lakukan redaksi sebelum membagikan log. Konsumsi token/karakter adalah estimasi biaya; tagihan provider menjadi sumber biaya aktual.
