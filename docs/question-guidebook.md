# Guidebook wawancara adaptif dan panel

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Versi panduan: `2026-11-07.1`. Status: adaptasi internal untuk latihan, **belum tervalidasi untuk seleksi kerja**. Rubrik skor tetap `2026-11-05.2`, `validated: false`; pekerjaan validasi asesor tetap ada di [rencana validasi](rubric-validation-plan.md).

Sumber runtime adalah [question-guidebook.json](question-guidebook.json). Setiap sesi baru menyimpan salinan panduan beserta versi dan hash. Isi panduan berupa tujuan penggalian, bukan daftar kalimat pertanyaan untuk diulang. Ada 21 sudut HR, 20 User, dan 20 Manager. Pemilihan stabil dalam satu sesi dan dapat berbeda antarsesi.

## Hubungan dengan empat dokumen acuan

| Acuan yang diperiksa | Bagian | Penerapan internal dan batas |
| --- | --- | --- |
| [OPM, Structured Interviews](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews.pdf) | Slide 4–5, 8–11: definisi, standardisasi, analisis pekerjaan dan pertanyaan | Menjaga kompetensi yang dituju ketika contoh/kalimat berubah. OPM membahas pertanyaan yang sama dengan urutan standar; personalisasi adaptif Preptiva adalah desain latihan berbeda, bukan klaim kesetaraan validitas. Panel AI bukan pengganti panel asesor manusia terlatih. |
| [SIOP/APA, Principles, edisi kelima](https://www.apa.org/ed/accreditation/about/policies/personnel-selection-procedures.pdf) | Bagian Sources of Validity Evidence; Criterion Relevance (PDF halaman 14 dan 19) | Pertanyaan harus terkait tugas pekerjaan; asal contoh tidak menggantikan bukti kemampuan. Relevansi dan manfaat skor tetap membutuhkan bukti validasi. Tidak mengklaim dokumen ini menetapkan daftar pertanyaan atau bobot persona. |
| [SIOP, AI-Based Assessments, 2023](https://www.siop.org/wp-content/uploads/legacy/SIOP%20Considerations%20and%20Recommendations%20for%20the%20Validation%20and%20Use%20of%20AI-Based%20Assessments%20for%20Employee%20Selection%20010323.pdf) | 4.5.1 dan Bagian 5 (PDF halaman 25, 29–30) | Simpan versi panduan, asal bukti CV, persona, dan jejak perubahan pertanyaan. Tes perangkat lunak atau contoh keluaran model tidak merupakan validasi psikometrik. |
| [ISO 10667-1:2020](https://www.iso.org/standard/74716.html) | Abstrak publik saja | Catat tujuan latihan, konteks penggunaan, dan pengelolaan hasil. Isi standar berbayar tidak digunakan untuk mengarang kutipan klausul atau mengklaim sertifikasi. |

Seluruh 61 sudut, pemisahan persona, aturan fresh graduate, urutan giliran, dan rumus panel adalah keputusan produk internal. Empat sumber memberi landasan metodologi, bukan bank soal atau aturan bahwa HR di seluruh organisasi tidak boleh bertanya teknis.

## Pemisahan konteks

| Interviewer | Yang digali | Yang dihindari |
| --- | --- | --- |
| Rina / HR | Motivasi, nilai kerja yang dapat diamati, integritas, pembelajaran, komunikasi, kolaborasi, refleksi, daya juang dan pencarian bantuan | Kuis teknis, sintaks, implementasi; diagnosis kepribadian, kemiripan pribadi sebagai ukuran budaya kerja, pertanyaan atribut pribadi yang tidak relevan |
| Andi / User | Praktik teknis **atau fungsional** pada profesi sebenarnya, kontribusi, diagnosis, validasi hasil, kualitas dan pilihan pendekatan | Menganggap semua pekerjaan adalah software, meminta kedalaman senior tanpa konteks, mengarang pengalaman kerja |
| Hendra / Manager | Prioritas, stakeholder, pengembangan orang, risiko, keputusan dan dampak sesuai lingkup pengalaman | Menganggap semua kandidat pernah punya bawahan; kuis coding; menyamakan jam kerja panjang dengan daya juang |

Generator dipanggil terpisah per persona. Konteks HR tidak memuat daftar keterampilan atau persyaratan teknis JD. Kutipan CV yang menyebut teknologi tetap boleh menjadi latar cerita perilaku. Misalnya, konflik kelompok dalam proyek SQL dapat digali HR; optimasi query tidak. Validator kompetensi menolak `technical` untuk HR dan menjaga tujuan kompetensi tiap slot. Filter istilah membantu mendeteksi beberapa kuis teknis, tetapi tidak menjamin semua kalimat model sesuai konteks; review manusia tetap diperlukan.

Evaluator menerima konteks persona dan hanya baris rubrik kompetensi pertanyaannya. Skor teknis dari User tidak menjadi skor HR. Hasil panel menampilkan skor tiap persona dan agregat panel, bukan voting independen beberapa asesor atas jawaban yang sama.

## Membaca kondisi kandidat

1. Form menyediakan pilihan Sesuaikan dari CV, Mahasiswa/pelajar, Fresh graduate, Sudah bekerja, atau Beralih karier. Pilihan ini terpisah dari level posisi yang dituju.
2. Ekstraksi membaca pendidikan, proyek, magang, aktivitas dan pekerjaan. Kutipan bukti harus benar-benar ada di CV. Penentuan otomatis tahap karier hanya diterima jika disertai kutipan yang ada di dokumen; bukti bertentangan atau tidak cukup menjadi `unknown`.
3. Tanpa bukti tahap karier, jangan menyimpulkan bahwa `years_exp=0`, usia muda atau posisi junior berarti fresh graduate. Ajukan klarifikasi netral. Pilihan eksplisit kandidat menentukan pendekatan awal.
4. Mahasiswa/fresh graduate memakai perkuliahan, skripsi, proyek kelompok, organisasi, relawan atau magang yang memang tersedia. Jika informasi tidak ada, tanyakan pengalaman yang relevan tanpa mengarang fakta.
5. Koreksi kandidat dalam percakapan menjadi konteks pertanyaan berikutnya. Pekerjaan berbayar bukan syarat agar contoh dinilai sebagai bukti; rubrik yang sama tetap meminta alasan, tindakan dan hasil sesuai kompetensi.

Contoh ilustratif internal untuk CV lulusan Akuntansi dengan proyek koperasi kampus (bukan kalimat runtime wajib):

- HR: “Dalam proyek koperasi kampus, bagaimana Anda menangani anggota yang terlambat mengirim pekerjaannya?”
- User: “Pada laporan koperasi kampus itu, bagaimana Anda memeriksa bahwa saldo dan bukti transaksi sudah cocok?”
- Manager: “Ketika waktu pengumpulan proyek itu menipis, bagaimana Anda menentukan pekerjaan yang perlu didahulukan?”

Jika kandidat menjawab bahwa masalahnya adalah pembagian tugas yang tidak jelas, pertanyaan berikutnya dapat menggali cara menyepakati tanggung jawab atau mengecek perbaikan, sesuai persona aktif dan kompetensi yang telah ditetapkan.

## Mekanisme adaptif

Persiapan membuat rencana cakupan 3/5/7 pertanyaan, pembagian pembicara, serta audio intro, penutup dan pertanyaan pertama. Audio pertanyaan berikutnya baru dibuat setelah adaptasi, sehingga audio rencana yang akan diganti tidak dibuat sia-sia. Setelah satu kelompok jawaban utama/follow-up selesai, pertanyaan utama berikutnya **dibentuk ulang** dari CV, JD, persona berikutnya, tujuan kompetensi dan paket percakapan yang berisi giliran terbaru dan giliran lama relevan dengan rujukan sumber. Follow-up tetap milik persona yang bertanya. Pertanyaan masa depan yang disiapkan di awal merupakan rencana, bukan skrip final yang harus dibacakan.

Adaptasi mempertahankan slot dan kompetensi, memeriksa anchor CV, pengulangan teks, serta batas persona. Pemeriksaan yang gagal mendapat satu kesempatan perbaikan. Jika model gagal, jawaban/pertanyaan berikutnya tidak dikomit sebagian; pengguna dapat mengirim ulang. Jika TTS gagal, pertanyaan/tanggapan dapat ditampilkan sebagai teks. Retry setelah jawaban berhasil memakai hasil tersimpan tanpa memindahkan giliran lagi. STT, respons, adaptasi dan audio tidak menimbulkan perubahan skema database.

Sesi baru menyimpan `settings.dynamic_questions`, `settings.panel`, `settings.career_stage`, `guidebook`, `candidate_profile`, `speaker_by_order`, `question_plan`, dan `question_provenance` di JSON script. Jejak adaptasi mencatat anchor CV, persona, pertanyaan sebelumnya dan jumlah giliran percakapan. Sesi lama tanpa flag adaptif tetap memakai perilaku pertanyaan yang telah disiapkan.

Adaptasi menambah panggilan LLM dan audio per pergantian pertanyaan utama, sehingga dapat menambah latensi dan biaya. Anggaran timeout respons yang sama mencakup respons, adaptasi dan TTS setelah transkripsi. Kemiripan teks tidak menjamin bebas pengulangan makna.

## Panel

Pilih format **Panel**, lalu dua atau tiga persona berbeda. Total pertanyaan tetap 3/5/7, bukan jumlah pertanyaan per orang. Pembagian giliran berputar sesuai urutan panel; identitas aktif dan suara berubah bersama pertanyaan. Semua voice ID anggota panel harus tersedia sebelum sesi dibuat.

Bobot agregat panel adalah rata-rata bobot persona terpilih, dibulatkan dengan sisa terbesar agar total 100. Skor kompetensi hanya memakai bukti yang terukur. Hasil per persona dihitung dari pertanyaan utamanya beserta follow-up, memakai bobot persona sendiri. Karena jumlah giliran dan kompetensi dapat berbeda, skor antaranggota panel bukan ukuran kesepakatan asesor. Pembandingan riwayat dibatasi ke posisi, level, komposisi panel dan versi/hash panduan/rubrik yang sama.

## Verifikasi

Tes unit/integrasi memeriksa pemisahan konteks, anchor yang tidak ada di CV, pilihan tahap karier, 61 sudut, pemisahan suara/penilaian panel, batas follow-up, perbaikan keluaran salah, rollback adaptasi, dan idempotensi retry. `tests/browser_smoke.py` menggunakan respons provider serta perangkat sintetis untuk sesi tunggal/panel dua/panel tiga dan tampilan mobile.

`tests/question_quality_smoke.py --run-paid` memakai model nyata pada tiga CV/JD sintetis: HR fresh graduate, User berpengalaman non-software, serta panel fresh graduate. Tidak memakai STT/TTS atau menulis sesi produksi. Contoh pertanyaan disimpan di `artifacts/question-quality-smoke.json` untuk tinjauan. Ini uji contoh keluaran model, bukan validasi oleh asesor atau jaminan kualitas seluruh pekerjaan.

Pembaruan lanjutan: [konteks terbatas, bukti, dan Retry/Next](panel-implementation.md). Next setelah interupsi tidak memiliki jawaban baru untuk adaptasi; pertanyaan berikutnya memakai rencana berbasis CV yang sudah dibuat.
