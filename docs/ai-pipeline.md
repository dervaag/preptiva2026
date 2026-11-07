# Pipeline AI

Diperbarui: 7 November 2026. Pipeline aktif tidak menggunakan `mock.py`; `AI_MOCK` harus false. Isian form development boleh berupa contoh, tetapi seluruh isi wawancara memakai API nyata.

## Alur

1. `create_session`: snapshot rubrik, guidebook, komposisi panel, bahasa, tahap karier pilihan pengguna dan batas sesi. Tidak ada migrasi tabel untuk fitur panel; metadata memakai JSON script.
2. `prepare_session`: ekstraksi CV/JD termasuk proyek, pendidikan, magang dan bukti kutipan. Profil otomatis memerlukan bukti literal dari CV. Panggilan generator dipisahkan per persona dengan rencana cakupan kompetensi dan riwayat pengguna sendiri. Audio intro, pertanyaan pertama dan penutup mengikuti voice pembicaranya; audio pertanyaan berikutnya dibuat sesudah adaptasi.
3. Sesudah jawaban dikirim, STT menghasilkan transkrip. NDJSON mengirim transkrip lebih dulu. Respons mempertimbangkan profil dan seluruh percakapan, dengan batas follow-up tetap ditegakkan.
4. Follow-up tetap milik pembicara pertanyaan utama. Ketika beralih ke pertanyaan utama berikutnya, model membentuk ulang pertanyaan dan expected points dari percakapan serta bukti CV, mempertahankan slot dan kompetensi. Identitas/voice mengikuti persona berikutnya.
5. Audio pertanyaan baru memakai nama unik. Jawaban, teks/audio pertanyaan berikutnya dan jejak adaptasi dikomit bersama; kegagalan tidak meninggalkan giliran parsial. Sesi lama tanpa `dynamic_questions` memakai pertanyaan lama.
6. Finalisasi menilai setiap kelompok pertanyaan utama/follow-up dengan konteks persona serta baris rubrik terkait, lalu menghitung agregat. Hasil panel menampilkan skor per persona. Skor bukan hasil voting asesor independen.
7. Review dibuat dari evaluasi berbukti. Audio jawaban hanya berada di memori permintaan, bukan disimpan untuk dihapus kemudian.

Rincian, batasan, contoh fresh graduate dan sumber metodologi: [guidebook pertanyaan](question-guidebook.md).

## Batas

- Pertanyaan utama: 3/5/7. Follow-up total sesi: 1/2/3, maksimal satu per pertanyaan utama.
- Durasi jawaban default: junior 90, middle/senior 120, manager 150 detik. Retry rekaman maksimal 2.
- Input CV/JD dibersihkan. Dokumen pendek (CV <=12.000, JD <=8.000 karakter) memakai satu ekstraksi; dokumen panjang diproses seluruhnya melalui chunking dan penggabungan ringkasan. Lihat [document-processing.md](document-processing.md).
- Batas output token saat ini: parse/chunk 2200, generate per persona 3000, adaptasi pertanyaan 900, respond 300, evaluate 1500, summarize 1500.
- Prompt pertanyaan utama maksimal 35 kata, follow-up 25, tanggapan 45. Batas kata merupakan instruksi, bukan validasi panjang keras.
- Aksi next dibersihkan dari pertanyaan atau permintaan baru sebelum suara dibuat agar tidak ada dua pertanyaan aktif.

## Suara

Konfigurasi proyek menggunakan ElevenLabs Multilingual v2 untuk prepared dan live. Prepared timeout 60 detik; live 30 detik; keseluruhan respond 60 detik. Dua request TTS serentak per proses, dengan retry 429 maksimal tiga kali setelah request pertama. Beberapa proses/sesi tetap berbagi kuota akun provider.

Tidak ada perpindahan otomatis ke OpenAI TTS atau speechSynthesis browser. Kegagalan suara dilaporkan. UI hanya membunyikan nada Web Audio lokal pada tes speaker, bukan suara pengganti pewawancara. Cache audio mempertimbangkan provider, model, voice, instruksi, versi pengaturan suara dan teks. Memutar ulang cache tidak melakukan panggilan provider.

STT proyek tetap `openai:gpt-4o-transcribe`; tidak memakai realtime microphone streaming. Konfigurasi provider lain ditolak; tidak ada fallback STT yang diaktifkan.

## Penilaian

Rubrik, rujukan, batas klaim, rumus, dan mekanisme snapshot ada di [assessment-reference.md](assessment-reference.md). Evaluator baru menggunakan indikator lengkap 1–5 dari snapshot; sesi lama menggunakan anchor lama. Skor tanpa bukti valid maksimal 2/5. Pemeriksaan kutipan menggunakan pencocokan teks setelah normalisasi, bukan fuzzy matching atau pemeriksaan kebenaran fakta.

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
