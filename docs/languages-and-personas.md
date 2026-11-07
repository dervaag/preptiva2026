# Bahasa sesi, konteks campuran, persona, dan variasi

Diperbarui: 5 November 2026. Rubrik baru: `2026-11-05.2`.

## Bahasa

Form memiliki pilihan `id` (Bahasa Indonesia, default) atau `en` (English). Pilihan disimpan di `interview_sessions.script.settings.language`, bukan mengubah bahasa UI keseluruhan. UI masih berbahasa Indonesia. Sesi lama tanpa pilihan bahasa tetap Indonesia.

| Sesi | Jawaban kandidat | Perilaku pewawancara |
| --- | --- | --- |
| Indonesia | Indonesia, English, atau campuran | Bertanya dan menanggapi dalam Indonesia; istilah asli boleh dipertahankan. |
| English | English, Indonesia, atau campuran | Bertanya dan menanggapi dalam English; tidak otomatis mengganti bahasa sesi. |
| Keduanya | Makna tidak jelas | Klarifikasi dalam bahasa sesi jika batas follow-up masih tersedia; jangan membuat pertanyaan tambahan ketika aksi next. |

STT tetap memakai OpenAI `gpt-4o-transcribe`, mengirim rekaman sesudah Kirim. Parameter bahasa Indonesia yang sebelumnya dipaksakan dihilangkan agar STT mendeteksi bahasa audio. Prompt mengingatkan bahasa utama dan mempertahankan code-switching, nama, serta istilah tanpa menerjemahkan. Ini arahan model, bukan jaminan akurasi semua aksen/campuran. Rujukan API: https://developers.openai.com/api/docs/guides/speech-to-text

Intro, pertanyaan, follow-up, penutup, frasa detail, dan review mengikuti bahasa sesi. Key JSON tetap konsisten. Evidence penilaian harus tetap mengutip bahasa asli transkrip; tidak diterjemahkan. Campuran bahasa tidak menjadi penalti kompetensi. Salah transkripsi tidak boleh dianggap bukti kelemahan kandidat. Bahasa sesi tidak berubah diam-diam di tengah sesi.

## Fokus pewawancara

| Persona | Fokus | Batas |
| --- | --- | --- |
| HR / Rina | Potensi belajar, motivasi, kesadaran diri, integritas, kolaborasi, adaptasi, komunikasi | CV teknis boleh menjadi latar pengalaman; tidak menguji sintaks, SQL, algoritma, atau optimasi query. |
| User / Andi | Potensi teknis/fungsional sesuai JD, kontribusi pribadi, praktik, diagnosis, validasi, trade-off | Tidak menganggap semua pekerjaan adalah software. Kedalaman sesuai level dan profesi. |
| Manager / Hendra | Kepemimpinan, pengembangan orang, potensi umum, prioritas, risiko dan dampak bisnis; keputusan teknis/fungsional | Teknis pada tingkat trade-off/kualitas/investasi sesuai posisi, bukan kuis coding. |

Deskripsi persona pada form juga menampilkan perbedaan fokus ini sebelum sesi dibuat.

Urutan 7 pertanyaan: perkenalan → pengalaman → motivasi/fundamental sesuai persona → bukti perilaku/kasus → penggalian kompetensi lain → situasi/keputusan sesuai persona → pertanyaan kandidat. Mode 3 memilih slot 1/4/6 dan mode 5 slot 1/2/4/6/7; penutup suara selalu tersedia.

Tidak ada aturan internasional tunggal bahwa HR tidak boleh bertanya teknis. Pemisahan ini adalah desain produk. Acuan OPM/SIOP mendorong pertanyaan relevan dengan pekerjaan dan penilaian berbukti; lihat [assessment-reference.md](assessment-reference.md). Potensi yang dilaporkan hanya indikasi dari bukti percakapan, bukan diagnosis kepribadian atau prediksi pasti.

## Variasi dan pemeriksaan

Blueprint menyediakan 61 sudut pertanyaan (21 HR, 20 User, 20 Manager), bukan 61 pertanyaan statis. UUID sesi menjadi seed pemilihan sudut agar satu sesi stabil dan sesi lain bisa berbeda. Sudut berulang dalam sesi dihindari.

Worker memberi generator sampai 35 pertanyaan utama terakhir dari pemilik dan persona yang sama untuk menghindari pengulangan. Informasi ini ikut dikirim ke OpenAI sebagai konteks wawancara; riwayat pengguna lain tidak diambil. Setiap pertanyaan tetap dipersonalisasi dari CV, JD, level, dan industri.

Validator memeriksa jumlah/urutan, pertanyaan kosong, lebih dari satu tanda tanya, kemiripan antarslot (>0,88) dan riwayat (>0,92), serta istilah tes teknis yang dilarang pada HR. Set yang gagal diminta diperbaiki sekali; jika tetap gagal persiapan dihentikan dengan error, tanpa mengganti ke dummy. Kemiripan karakter tidak menjamin tidak ada duplikasi makna. Pemeriksaan pola teknis juga bukan pengganti review manusia.

Tag technical disaring dari pertanyaan HR; bobot technical HR baru 0 dan adaptability menjadi 25. Manager mempertahankan kombinasi teknis dan umum. Follow-up HR yang terdeteksi menguji teknis diminta diperbaiki satu kali; jika tetap tidak sesuai, sistem lanjut tanpa pertanyaan teknis tambahan. Sesi lama tidak diubah atau dinilai ulang otomatis.
