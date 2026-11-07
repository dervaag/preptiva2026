# Pipeline AI

Diperbarui: 5 November 2026. Pipeline aktif tidak menggunakan `mock.py`; `AI_MOCK` harus false. Isian form development boleh berupa contoh, tetapi seluruh isi wawancara memakai API nyata.

## Alur

1. `create_session`: snapshot CV/JD dan metadata rubrik dari [assessment-reference.md](assessment-reference.md) ke database.
2. `prepare_session`: GPT-4o-mini mengekstrak CV/JD, GPT-4o membuat pertanyaan utama sesuai blueprint, ElevenLabs membuat intro/pertanyaan/penutup. Semua pertanyaan utama dibuat di awal.
3. Setelah jawaban dikirim: STT OpenAI mentranskripsikan rekaman. Opsi NDJSON mengirim transkrip ke UI segera, sebelum tanggapan/audio selesai.
4. GPT-4o-mini menghasilkan tanggapan dan memilih next/follow_up/redirect. Konteks meliputi pertanyaan utama, expected_points, dan jawaban pada pertanyaan itu. Pertanyaan utama berikutnya belum diregenerasi dari seluruh percakapan.
5. ElevenLabs menghasilkan audio tanggapan dengan voice/model yang sama. Filler tidak menahan pemutaran tanggapan.
6. Setelah satu kelompok pertanyaan selesai, GPT-4o menilai jawaban utama beserta follow-up di background berdasarkan snapshot rubrik sesi. Kutipan diperiksa dalam kode.
7. Finalisasi menghitung agregat skor dalam kode lalu GPT-4o menulis review. Audio jawaban dihapus setelah finalisasi normal; transkrip dan skor tetap disimpan.

## Batas

- Pertanyaan utama: 3/5/7. Follow-up total sesi: 1/2/3, maksimal satu per pertanyaan utama.
- Durasi jawaban default: junior 90, middle/senior 120, manager 150 detik. Retry rekaman maksimal 2.
- Input CV/JD dibersihkan. Dokumen pendek (CV <=12.000, JD <=8.000 karakter) memakai satu ekstraksi; dokumen panjang diproses seluruhnya melalui chunking dan penggabungan ringkasan. Lihat [document-processing.md](document-processing.md).
- Batas output token: parse pendek 900, parse_chunk 1200, generate 2500, respond 220, evaluate 900, summarize 1500.
- Prompt pertanyaan utama maksimal 35 kata, follow-up 25, tanggapan 45. Batas kata merupakan instruksi, bukan validasi panjang keras.
- Aksi next dibersihkan dari pertanyaan atau permintaan baru sebelum suara dibuat agar tidak ada dua pertanyaan aktif.

## Suara

Konfigurasi proyek menggunakan ElevenLabs Multilingual v2 untuk prepared dan live. Prepared timeout 60 detik; live 30 detik; keseluruhan respond 60 detik. Dua request TTS serentak per proses, dengan retry 429 maksimal tiga kali setelah request pertama. Beberapa proses/sesi tetap berbagi kuota akun provider.

Tidak ada perpindahan otomatis ke OpenAI TTS atau speechSynthesis browser. Kegagalan suara dilaporkan. UI hanya membunyikan nada Web Audio lokal pada tes speaker, bukan suara pengganti pewawancara. Cache audio mempertimbangkan provider, model, voice, instruksi, versi pengaturan suara dan teks. Memutar ulang cache tidak melakukan panggilan provider.

STT proyek tetap `openai:gpt-4o-transcribe`; tidak memakai realtime microphone streaming. Opsi provider lain masih ada dalam implementasi, tetapi fallback STT default kosong.

## Penilaian

Rubrik, rujukan, batas klaim, rumus, dan mekanisme snapshot ada di [assessment-reference.md](assessment-reference.md). Evaluator baru menggunakan indikator lengkap 1–5 dari snapshot; sesi lama menggunakan anchor lama. Skor tanpa bukti valid maksimal 2/5. Pemeriksaan kutipan menggunakan kecocokan token/fuzzy dengan threshold 0,8, bukan pemeriksaan kebenaran fakta.

| Kompetensi | HR | User | Manager |
| --- | ---: | ---: | ---: |
| communication | 25 | 10 | 15 |
| problem_solving | 10 | 25 | 15 |
| technical | 0 | 35 | 10 |
| analytical | 10 | 15 | 15 |
| teamwork | 25 | 10 | 10 |
| adaptability | 25 | 5 | 10 |
| leadership | 5 | 0 | 25 |

Bobot dan label berasal dari `app/ai/scoring.py`, bukan standar eksternal. Skor sesi hanya mengagregasi kompetensi terukur, dengan bobot dinormalisasi ulang. Kutipan, STAR, kekuatan, kekurangan, dan tips disimpan bersama jawaban.

Lihat [session-experience.md](session-experience.md) untuk perangkat, fokus tab, dan kontrak stream; [logging.md](logging.md) untuk latensi dan token; [CHANGELOG.md](CHANGELOG.md) untuk perubahan.

Bahasa Indonesia/English, jawaban campuran, 61 variasi sudut, validasi peran HR/User/Manager dan batas riwayat dibahas di [languages-and-personas.md](languages-and-personas.md). Bahasa dan rubrik disnapshot di JSON sesi.

Pada aksi next untuk pertanyaan terakhir, kode membersihkan ajakan lanjut sebelum TTS. Follow-up yang masih diizinkan pada pertanyaan terakhir tetap dapat berjalan; penutup hanya terjadi ketika aksi next dan tidak ada pertanyaan utama berikutnya.
