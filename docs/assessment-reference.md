# Acuan dan rubrik asesmen

Versi: `2026-11-05.2`. Tanggal tinjauan: 5 November 2026.

## Sumber dan penerapannya

| Sumber | Tautan | Penggunaan |
| --- | --- | --- |
| U.S. OPM, Structured Interviews | https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews.pdf | Pertanyaan berbasis kompetensi pekerjaan, indikator perilaku, standar skor yang konsisten. |
| SIOP/APA, Principles for Validation and Use of Personnel Selection Procedures, 2018 | https://www.apa.org/ed/accreditation/about/policies/personnel-selection-procedures.pdf | Relevansi pekerjaan, reliabilitas, bukti validitas, kalibrasi dengan asesor manusia. |
| SIOP, AI-Based Assessments for Employee Selection, 2023 | https://www.siop.org/wp-content/uploads/legacy/SIOP%20Considerations%20and%20Recommendations%20for%20the%20Validation%20and%20Use%20of%20AI-Based%20Assessments%20for%20Employee%20Selection%20010323.pdf | Evaluasi penggunaan AI, dokumentasi, dan pengujian kualitas penilaian. |
| ISO 10667-1:2020 | https://www.iso.org/standard/74716.html | Tata kelola proses asesmen konteks pekerjaan. Dokumen lengkap berbayar. |

Sumber tersebut menjadi acuan metodologi. Aplikasi ini belum tersertifikasi ISO dan belum divalidasi sebagai alat seleksi kerja. Pertanyaan utama dipersonalisasi dan follow-up adaptif; implementasi ini bukan wawancara terstruktur identik antarkandidat. Skor ditujukan untuk latihan. Bobot, label skor, dan indikator di bawah merupakan adaptasi internal, bukan angka yang ditetapkan sumber tersebut.

## Rubrik yang digunakan aplikasi

<!-- rubric:start -->
Bahasa sesi dapat Indonesia atau English. Jawaban campuran tetap diterima; jangan menurunkan skor karena campuran bahasa, aksen, atau istilah teknis Inggris. Kutipan harus tetap dalam bahasa asli transkrip. HR menggali potensi belajar dan perilaku kerja, User menilai potensi teknis/fungsional, Manager menggabungkan kepemimpinan/potensi umum dan keputusan teknis pada konteks bisnis. Potensi merupakan indikasi dari bukti jawaban, bukan diagnosis atau prediksi pasti.
Nilai kompetensi berdasarkan bukti perilaku dalam transkrip, relevansi terhadap posisi/JD, dan level kandidat. Gunakan pertanyaan utama dan follow-up sebagai satu unit penilaian. STAR membantu menyusun bukti, bukan syarat mutlak untuk pertanyaan konseptual atau pertanyaan kandidat di penutup. Jangan menilai wajah, gender, usia, aksen, atau perpindahan tab sebagai kemampuan kandidat.

| Kompetensi | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| communication | Sulit diikuti, pesan tidak jelas | Ada pesan utama tetapi terputus dan kurang konteks | Runtut dan cukup jelas | Terstruktur, ringkas, contoh relevan | Sangat jelas, terstruktur, menyesuaikan audiens dan menyampaikan dampak |
| problem_solving | Masalah tidak teridentifikasi | Masalah disebut tetapi langkah tanpa alasan | Langkah logis, analisis akar masalah/alternatif terbatas | Akar masalah dan alternatif beserta alasan keputusan jelas | Analisis sistematis, trade-off, verifikasi solusi dan hasil terukur |
| technical | Konsep keliru | Sebagian konsep benar, penerapan belum jelas | Fundamental benar sesuai level | Penerapan nyata, detail implementasi dan batasan jelas | Akurat dan mendalam sesuai level, trade-off serta validasi implementasi |
| analytical | Kesimpulan tanpa dasar | Ada alasan tetapi bukti tidak memadai | Alasan logis, data masih terbatas | Membandingkan alternatif memakai data dan asumsi jelas | Menguji asumsi, membandingkan metrik dan menjelaskan ketidakpastian |
| teamwork | Menyalahkan atau kontribusi tidak jelas | Menyebut tim tanpa peran pribadi | Peran dan kerja sama cukup jelas | Mengelola koordinasi/konflik dan kontribusi konkret | Meningkatkan kolaborasi dengan hasil nyata dan refleksi yang relevan |
| adaptability | Tidak menunjukkan penyesuaian | Perubahan disebut tanpa tindakan jelas | Menyesuaikan diri saat diminta | Belajar dan menyesuaikan pendekatan secara proaktif | Mengantisipasi perubahan, menguji pembelajaran dan menunjukkan dampaknya |
| leadership | Tidak ada inisiatif atau tanggung jawab | Inisiatif disebut tanpa keputusan/peran jelas | Memimpin lingkup sesuai level | Mengarahkan orang, prioritas dan keputusan dengan alasan jelas | Mengelola trade-off strategis, mengembangkan orang dan menunjukkan dampak terukur |

Skor 2 dan 4 mewakili bukti yang melampaui tingkat sebelumnya tetapi belum memenuhi tingkat berikutnya. Tidak adanya bukti bukan bukti ketidakmampuan. Jika tidak ada kutipan pendukung yang valid, skor kompetensi maksimal 2; jelaskan bahwa bukti belum cukup. Jangan mengarang pengalaman atau angka. Jangan menghukum kesalahan STT sebagai kesalahan kompetensi. Metrik tempo/kata pengisi hanya konteks komunikasi, bukan aturan pengurangan nilai otomatis.
<!-- rubric:end -->

## Penyimpanan dan keterlacakan

Markdown ini adalah sumber rubrik yang dibaca runtime oleh `app/ai/assessment.py`. Bagian di antara penanda `rubric:start/end` dikirim ke evaluator. Setiap sesi baru menyimpan snapshot versi, hash SHA-256, teks rubrik, URL sumber, dan bobot di `interview_sessions.script.assessment`. Tidak memerlukan tabel atau migrasi baru. Evaluasi memakai snapshot sesi; perubahan dokumen tidak mengubah rubrik sesi lama. Sesi tanpa snapshot ditandai sebagai rubrik lama, bukan diklaim memakai versi ini.

Skor per kompetensi 1–5 dikonversi ke skala 100 (dikali 20). Skor kompetensi sesi adalah rata-rata penilaian kompetensi tersebut; skor total merupakan rata-rata berbobot kompetensi yang terukur. Kompetensi tidak terukur dikecualikan dan bobot dinormalisasi ulang. Label internal: >=85 Strong Match; >=70 Good; >=55 Needs Work; sisanya Not Ready. Penjelasan, kutipan, dan saran tersedia di hasil sesi. Skor 80 berarti agregat rubrik, bukan persentil atau probabilitas lolos.

## Validasi lanjutan

Sebelum dipakai untuk seleksi nyata: tentukan kompetensi lewat analisis pekerjaan; kumpulkan jawaban acuan yang dinilai beberapa asesor; ukur kesepakatan AI–asesor dan antarputaran; audit bias, kutipan, dan pengaruh kualitas transkripsi. Jangan mengklaim validitas hanya karena menggunakan sumber di atas. Rencana kerjanya, dimulai dari Engineering Manager/persona Manager, ada di [rubric-validation-plan.md](rubric-validation-plan.md).

## Fokus persona dan bahasa (versi 2026-11-05.2)

Batas fokus persona adalah desain produk yang mengikuti analisis pekerjaan, bukan aturan bahwa semua HR di dunia dilarang menilai teknis. Bobot HR baru: communication 25, problem_solving 10, technical 0, analytical 10, teamwork 25, adaptability 25, leadership 5. User dan Manager tidak berubah. Sesi lama mempertahankan bobot dan snapshot aslinya.

## Profil draf khusus Engineering Manager

Mulai 7 November 2026, [profil EM/persona Manager](engineering-manager-rubric.md) versi `2026-11-07.em.1` dapat dipilih secara eksplisit untuk latihan. Profil ini memiliki lima kompetensi dengan 25 jangkar perilaku internal, sumber metodologi/pekerjaan dan snapshot tersendiri. Rubrik umum di atas tetap menjadi default; HR, User, panel, pekerjaan lain dan sesi historis tidak dialihkan. Draf belum ditinjau ahli pekerjaan, belum dinilai asesor, dan selalu `validated: false`. Detail alur manusia ada di [panduan asesor](assessor-validation.md).
