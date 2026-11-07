# Hasil pemeriksaan awal penilaian

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Tanggal: 7 November 2026. Ruang lingkup: profil Engineering Manager/persona Manager. Ini hasil verifikasi teknis dan kesiapan studi, bukan hasil validasi akurasi penilaian.

## Hasil yang benar-benar dijalankan

| Pemeriksaan | Hasil |
| --- | --- |
| Tes rubrik `test_job_rubric.py` | 5 lulus |
| Tes alur asesor `test_assessor_workflow.py` | 9 lulus |
| Tes audit `test_validation_audit.py` | 3 lulus |
| Integritas snapshot dataset | Hash cocok |
| Pemetaan sumber indikator | 25 indikator terhubung ke ID sumber yang tersedia; isi sumber dan relevansinya tidak diverifikasi oleh pemeriksaan ID |
| Materi pilot | 20 jawaban sintetis; 5 kalibrasi dan 15 uji |
| Penilaian manusia di dataset | 0 |
| Run AI di dataset | 0 |
| Akurasi AI terhadap manusia | Belum dapat dihitung |
| Status validasi | `false`, menunggu bukti manusia |

Tes memakai fixture sintetis, bukan rating asesor asli. Tidak ada panggilan API berbayar dalam pemeriksaan ini. Laporan mesin lokal tersedia di `data/assessor-em-2026-11-07/readiness-audit.json`. Perintah untuk mengulang pemeriksaan tersedia pada [panduan validasi](assessor-validation.md).

## Ketika belum memiliki asesor

Pengguna mengonfirmasi belum memiliki asesor atau hasil penilaian manusia untuk kasus EM. Rating akademik Mohler yang diunduh kemudian merupakan dataset eksternal terpisah. Status yang tepat adalah dasar latihan berbasis referensi yang siap ditinjau. Dua model AI yang sepakat juga belum menyediakan pembanding manusia atau bukti validitas terhadap kinerja kerja.

Koordinator perlu mencari peninjau yang memahami pekerjaan Engineering Manager untuk memeriksa JD, kompetensi, bobot dan indikator, serta tiga penilai yang kompeten menggunakan rubrik. Peninjau pekerjaan dapat merangkap salah satu penilai jika perannya dicatat; tiga rating tetap harus berasal dari tiga orang berbeda dan dibuat independen. Jumlah tiga mengikuti rancangan studi internal proyek, bukan klaim ketentuan universal.

Bagikan satu formulir HTML kepada setiap penilai setelah tinjauan rubrik selesai. Materi permintaan yang dapat digunakan koordinator:

> Kami sedang menguji rubrik latihan wawancara Engineering Manager. Kami membutuhkan tinjauan kesesuaian tugas dan indikator, lalu penilaian independen atas jawaban sintetis. Penilai mencatat skor atau bukti belum cukup, kutipan, indikator, alasan, dan bukti yang belum tersedia untuk tingkat berikutnya. Skor AI dan penilai lain tidak ditampilkan. Mohon jelaskan pengalaman relevan Anda serta kemungkinan konflik kepentingan sebelum menerima tugas.

Materi ini belum dikirim kepada siapa pun. Jangan mengisi nama, persetujuan atau rating atas nama asesor.

## Syarat sebelum menarik kesimpulan

1. Ahli meninjau konteks target dan kecukupan sampel; perbarui versi rubrik dan paket jika diperlukan. Pilot 20 kasus belum merupakan sampel validasi yang memadai.
2. Tiga penilai mengisi secara independen, kemudian koordinator membahas konsensus tanpa menghapus rating awal.
3. Jalankan AI terpisah tanpa skor manusia di prompt, lima kali per kasus sesuai protokol. Simpan versi rubrik, model dan provenance.
4. Bandingkan AI–konsensus dan kesepakatan antarasesor, stabilitas, kutipan, pengecualian bukti serta denominator. Tinjau bahasa, pengaruh STT dan fairness secara terpisah.
5. Ahli menafsirkan hasil beserta ketidakpastian dan batas konteks. Memenuhi metrik pilot tidak otomatis membuktikan validitas untuk seleksi kerja.

AI dapat membantu menyiapkan rubrik, menguji perangkat lunak dan menghitung perbandingan. Penilaian independen, kompetensi penilai dan relevansi pekerjaan memerlukan bukti dari pelaksana sebenarnya.

## Tindak lanjut dataset publik

Pemeriksaan akses dan ketentuan tiga dataset serta pembanding skor eksternal dicatat di [benchmark eksternal](external-benchmark.md). RecruitView tidak sesuai untuk penggunaan aplikasi ini menurut ketentuan dataset card; MIT dan AVI memerlukan izin. Tindak lanjut: [Mohler sudah diunduh](mohler-benchmark.md), dengan 2.442 jawaban bernilai manusia dan pilot 50 jawaban terpisah dari dataset EM. Belum ada metrik AI–manusia yang dihasilkan. Tes alat pembanding dan impor Mohler terpisah dari 17 tes awal di atas.

## Verifikasi perangkat lunak berikutnya

Pada baseline `a85d0da`, 7 tes gate bahasa dan 50 tes sistem serta suite controller lulus setelah integrasi main. Ini menguji pengingat bahasa, giliran tetap, audio/teks dan tidak adanya finish tambahan. Angka 17 pada tabel awal tetap merupakan hasil pemeriksaan awal, bukan total seluruh tes terbaru. Tidak ada rating manusia EM, hasil model Mohler atau klaim validitas baru dari pemeriksaan ini.
