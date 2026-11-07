# Pipeline AI

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Sebelum respons/follow-up, jawaban yang terdeteksi dominan memakai bahasa Indonesia/Inggris berbeda dari bahasa sesi dikembalikan sebagai `language_retry`. Pemeriksaan dilakukan sebelum jawaban penilaian diterima di legacy maupun graph. Pengingat meminta ulang dalam bahasa sesi tanpa memajukan pertanyaan, menambah follow-up atau menutup sesi; jawaban singkat/tidak pasti tidak ditolak otomatis. Lihat [kebijakan bahasa](languages-and-personas.md).

Penutup sesi: tidak ada fase kandidat bertanya kepada panel. Blueprint baru memakai slot `reflection`, bukan `candidate_questions`; generator/adaptasi menolak ajakan agar kandidat mengajukan pertanyaan. Penutup baru memakai teks tetap Indonesia/Inggris yang menjelaskan sesi selesai dan hasil akan diproses. Payload penutup sesi lama dengan pertanyaan/ajakan Q&A diganti pada jalur state/akhir giliran dan endpoint suara, agar teks dan audio tidak bertentangan. Pertanyaan utama dan follow-up yang memang meminta jawaban kandidat tetap berjalan seperti biasa.

Bahasa hasil: pertanyaan dan STT memakai `settings.language`, sedangkan alasan penilaian, feedback dan ringkasan memakai snapshot `settings.feedback_language` dari bahasa platform saat sesi dibuat (fallback sesi lama: bahasa wawancara). Jalur legacy dan LangGraph menggunakan kebijakan sama. Kutipan asli tidak diterjemahkan. Ringkasan menyatakan wawancara selesai, tidak meminta jawaban tambahan; keluaran feedback bertanda tanya diperbaiki sekali atau dinyatakan gagal agar dapat dicoba ulang. Lihat [hasil](results.md).

Diperbarui: 7 November 2026. Pipeline aktif tidak menggunakan `mock.py`; `AI_MOCK` harus false. Isian form development boleh berupa contoh, tetapi seluruh isi wawancara memakai API nyata.

## Alur

1. `create_session`: snapshot rubrik, guidebook, komposisi panel, bahasa, tahap karier pilihan pengguna dan batas sesi. Metadata panel memakai JSON script; tabel aditif `interview_events` menyimpan event dengan kunci idempoten.
2. `prepare_session`: ekstraksi CV/JD termasuk proyek, pendidikan, magang dan bukti kutipan. Profil otomatis memerlukan bukti literal dari CV. Panggilan generator dipisahkan per persona dengan rencana cakupan kompetensi dan riwayat pengguna sendiri. Audio intro, pertanyaan pertama dan penutup mengikuti voice pembicaranya; audio pertanyaan berikutnya dibuat sesudah adaptasi.
3. Sesudah jawaban dikirim, STT menghasilkan transkrip. NDJSON mengirim transkrip lebih dulu. Respons mempertimbangkan profil dan paket dialog terbatas: giliran terbaru, retrieval giliran lama, klaim berkutipan, dan indeks sumber. Batas follow-up tetap ditegakkan; teks asli disimpan utuh. Jawaban teks dapat dipakai tanpa STT.
4. Follow-up tetap milik pembicara pertanyaan utama. Ketika beralih ke pertanyaan utama berikutnya, model membentuk ulang pertanyaan dan expected points dari percakapan serta bukti CV, mempertahankan slot dan kompetensi. Identitas/voice mengikuti persona berikutnya.
5. Audio pertanyaan baru memakai nama unik. Jawaban, teks/audio pertanyaan berikutnya dan jejak adaptasi dikomit bersama; kegagalan tidak meninggalkan giliran parsial. Sesi lama tanpa `dynamic_questions` memakai pertanyaan lama.
6. Finalisasi menilai setiap kelompok pertanyaan utama/follow-up dengan konteks persona serta baris rubrik terkait, lalu menghitung agregat. Hasil panel menampilkan skor per persona. Skor bukan hasil voting asesor independen.
7. Review dibuat dari evaluasi berbukti. Audio jawaban hanya berada di memori permintaan, bukan disimpan untuk dihapus kemudian.

Rincian, batasan, contoh fresh graduate dan sumber metodologi: [guidebook pertanyaan](question-guidebook.md).

## Batas

- Pertanyaan utama: 3/5/7. Follow-up total sesi: 1/2/3, maksimal satu per pertanyaan utama.
- Durasi jawaban default: junior 90, middle/senior 120, manager 150 detik. Retry rekaman maksimal 2.
- Input CV/JD dibersihkan. Dokumen pendek (CV <=12.000, JD <=8.000 karakter) memakai satu ekstraksi; dokumen panjang diproses seluruhnya melalui chunking dan penggabungan ringkasan. Lihat [document-processing.md](document-processing.md).
- Batas output token saat ini: parse/chunk 2200, generate per persona 3000, adaptasi pertanyaan 900, respond 300, evaluate 1800, summarize 1500.
- Prompt pertanyaan utama maksimal 35 kata, follow-up 25, tanggapan 45. Batas kata merupakan instruksi, bukan validasi panjang keras.
- Aksi next dibersihkan dari pertanyaan atau permintaan baru sebelum suara dibuat agar tidak ada dua pertanyaan aktif.

## Suara

Konfigurasi proyek menggunakan ElevenLabs Multilingual v2 untuk prepared dan live. Prepared timeout 60 detik; live 30 detik; keseluruhan respond 60 detik. Dua request TTS serentak per proses, dengan retry 429 maksimal tiga kali setelah request pertama. Beberapa proses/sesi tetap berbagi kuota akun provider.

Tidak ada perpindahan otomatis ke OpenAI TTS atau speechSynthesis browser. Kegagalan suara dilaporkan dan percakapan dapat dilanjutkan melalui teks; tidak memakai suara provider lain. UI hanya membunyikan nada Web Audio lokal pada tes speaker, bukan suara pengganti pewawancara. Cache audio mempertimbangkan provider, model, voice, instruksi, versi pengaturan suara dan teks. Memutar ulang cache tidak melakukan panggilan provider.

STT proyek tetap `openai:gpt-4o-transcribe`; mendukung unggahan audio serta transport realtime sesuai snapshot sesi. Konfigurasi provider lain ditolak; tidak ada fallback STT yang diaktifkan.

## Penilaian

Rubrik, rujukan, batas klaim, rumus, dan mekanisme snapshot ada di [assessment-reference.md](assessment-reference.md). Evaluator baru menggunakan indikator lengkap 1–5 dari snapshot; sesi lama menggunakan anchor lama. Skor tanpa bukti valid maksimal 2/5. Kutipan harus berupa substring literal dari satu giliran asli; ID giliran dan offset disimpan. Skor tanpa bukti cukup bersifat sementara dan tidak masuk agregat, berbeda dari skor rendah dengan bukti. Ini bukan pemeriksaan kebenaran klaim kandidat.

| Kompetensi | HR | User | Manager |
| --- | ---: | ---: | ---: |
| communication | 25 | 10 | 15 |
| problem_solving | 10 | 25 | 15 |
| technical | 0 | 35 | 10 |
| analytical | 10 | 15 | 15 |
| teamwork | 25 | 10 | 10 |
| adaptability | 25 | 5 | 10 |
| leadership | 5 | 0 | 25 |

Bobot dan label berasal dari `app/ai/scoring.py`, bukan standar eksternal. Hasil baru menampilkan cakupan bukti secara terpisah. Skor sesi hanya mengagregasi kompetensi dengan bukti cukup, dengan bobot dinormalisasi ulang. Kutipan, STAR, kekuatan, kekurangan, dan tips disimpan bersama jawaban.

Lihat [session-experience.md](session-experience.md) untuk perangkat, fokus tab, dan kontrak stream; [logging.md](logging.md) untuk latensi dan token; [CHANGELOG.md](CHANGELOG.md) untuk perubahan.

Bahasa Indonesia/English, jawaban campuran, 61 variasi sudut, validasi peran HR/User/Manager dan batas riwayat dibahas di [languages-and-personas.md](languages-and-personas.md). Bahasa dan rubrik disnapshot di JSON sesi.

Pada aksi next untuk pertanyaan terakhir, kode membersihkan ajakan lanjut sebelum TTS. Follow-up yang masih diizinkan pada pertanyaan terakhir tetap dapat berjalan; penutup hanya terjadi ketika aksi next dan tidak ada pertanyaan utama berikutnya.

Interupsi pertanyaan, event/checkpoint, fallback teks, dan status brief dijelaskan di [panel-implementation.md](panel-implementation.md). Retry mengulang pertanyaan yang sama; Next menyimpan penanda dilewati tanpa skor. Penilaian gagal dapat dicoba ulang tanpa kehilangan jawaban.

## Benchmark eksternal terpisah — 7 November 2026

[Benchmark Mohler](mohler-benchmark.md) memakai `app.ai.model_router.complete` dan `MODEL_DEEP`, dengan prompt penilaian akademik berbasis jawaban instruktur di `validation/mohler.py`. Ini bukan pemanggilan evaluator wawancara `orchestrator.evaluate`. Masukan AI hanya pertanyaan, jawaban acuan dan jawaban peserta; rating manusia disimpan terpisah. Dataset tidak ditambahkan ke retrieval atau prompt sesi pengguna. Runner menyimpan hasil per kasus dan provenance; report menghitung Spearman, MAE 0–5 dan persentase selisih maksimal satu poin. Run model belum dijalankan dan tidak ada hasil akurasi baru.
