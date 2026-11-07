# Pedoman dasar asesor Preptiva

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Disusun 7 November 2026. Status: pedoman latihan dan tinjauan ahli, belum tervalidasi sebagai alat seleksi. Fokus awal Engineering Manager dengan persona Manager. Panduan ini menjelaskan penggunaan [rubrik EM](engineering-manager-rubric.md); tidak mengganti indikator, bobot, versi, atau snapshot runtime.

## Dasar yang dapat ditelusuri

| Sumber primer yang diperiksa 7 November 2026 | Bagian | Dasar penggunaan | Batas |
| --- | --- | --- | --- |
| [OPM Structured Interviews](https://www.opm.gov/policy-data-oversight/assessment-and-selection/other-assessment-methods/structured-interviews/) | Penjelasan struktur pertanyaan dan benchmarks of proficiency | Tentukan kompetensi, pertanyaan dan jangkar penilaian sebelum menilai | Tidak menetapkan bobot atau ambang kelulusan Preptiva; wawancara adaptif Preptiva tidak identik dengan wawancara terstruktur penuh |
| [GitLab Engineering Manager](https://handbook.gitlab.com/job-description-library/engineering/development/management/engineering-manager/) | Pembuka dan Responsibilities | Contoh pekerjaan: pengelolaan tim, coaching, koordinasi lintas fungsi dan keputusan teknis | Contoh satu organisasi; kesesuaian dengan JD pengguna harus ditinjau |
| [O*NET Database](https://www.onetcenter.org/database.html) | About the job, About the worker, dan License Exceptions | Sumber tambahan untuk analisis tugas dan kompetensi pekerjaan lain | Belum dipetakan ke indikator runtime. Taksonomi konteks AS perlu adaptasi lokal; data pekerjaan bukan skor jawaban |

O*NET menyediakan unduhan data pekerjaan. Jika data unduhannya digunakan, catat versi yang benar-benar diunduh, kode pekerjaan, nama berkas/baris, atribusi USDOL/ETA, tautan [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), serta perubahan yang dibuat. Perhatikan pengecualian lisensi pada sumber. Halaman publik tidak otomatis memberikan izin untuk menyalin seluruh isinya; panduan ini memakai ringkasan dan tautan.

Indikator skor, bobot dan contoh di Preptiva adalah rancangan internal. Sumber di atas mendukung metode atau relevansi tugas, bukan mengesahkan skor. Referensi tambahan beserta lokasi sumber tersedia dalam snapshot rubrik EM.

## Lima fokus untuk Engineering Manager

| Fokus | Key | Bobot usulan | Bukti yang digali |
| --- | --- | --- | --- |
| Pengambilan keputusan | problem_solving | 25% | Tujuan, batasan, alternatif, risiko, alasan keputusan dan peninjauan hasil |
| Kepemimpinan tim | teamwork | 20% | Peran, koordinasi, delegasi, konflik dan kemandirian tim |
| Pengembangan orang | leadership | 20% | Diagnosis kebutuhan belajar, coaching, umpan balik dan evaluasi perkembangan |
| Komunikasi stakeholder | communication | 20% | Penyesuaian informasi, penyelarasan ekspektasi dan tindak lanjut |
| Penilaian teknis | technical | 15% | Pilihan teknis, trade-off, risiko dan verifikasi bersama engineer |

Bobot ini harus ditinjau ahli terhadap JD target. Skor 1–5 menunjukkan kualitas bukti pada lingkup pekerjaan yang sama, bukan junior sampai direktur. Untuk pekerjaan/persona lain gunakan rubrik umumnya sampai profil khusus tersedia.

## Urutan penilaian satu jawaban

1. Baca konteks pekerjaan, pertanyaan utama dan follow-up sebagai satu unit. Tentukan kompetensi yang memang diberi kesempatan untuk ditunjukkan.
2. Pisahkan situasi, tindakan pribadi, alasan dan hasil. Bedakan pengalaman nyata dengan rencana hipotetis. STAR membantu pencatatan, tetapi bukan syarat jawaban yang baik.
3. Salin kutipan persis dari satu giliran asli. Catat ID giliran; jangan menggabungkan potongan berbeda menjadi kutipan baru. Periksa apakah maknanya mendukung indikator.
4. Jika bukti kurang, pilih `insufficient` tanpa skor terukur. Jika ada dugaan salah transkripsi, minta klarifikasi atau tandai belum cukup; jangan menganggapnya salah konsep.
5. Jika cukup, cocokkan dengan indikator kompetensi pada snapshot. Pilih tingkat tertinggi yang seluruh unsur pokoknya didukung. Skor rendah 1/2 memerlukan bukti perilaku rendah eksplisit pada profil EM.
6. Tulis alasan hubungan kutipan dengan indikator. Untuk skor 1–4, catat bukti yang belum tersedia untuk tingkat berikutnya; untuk skor 5 tidak ada tingkat berikutnya.
7. Simpan penilaian independen sebelum melihat skor AI atau asesor lain. Perbedaan dibahas setelah semua penilaian terkumpul.

Gunakan jangkar lengkap pada rubrik, bukan hanya ringkasan tabel ini. Jangan memberi bonus/pengurangan otomatis karena angka hasil, nama perusahaan, ukuran tim, gaya pribadi, usia, gender, aksen atau campuran bahasa. Klaim pengalaman tetap laporan kandidat, bukan fakta yang sudah diverifikasi.

## Contoh pencatatan internal

Pertanyaan pengambilan keputusan: “Ceritakan keputusan prioritas tim ketika waktu terbatas. Apa pilihan, risiko, dan cara Anda memeriksa hasilnya?”

Jawaban sintetis: “Targetnya menstabilkan checkout dalam dua hari. Saya memilih rollback daripada refactor karena perubahan refactor terlalu besar untuk waktu itu.”

Catatan latihan: kutipan tersebut dapat mendukung `em.problem_solving.l3`: ada tujuan, batasan, pilihan dan alasan. Bukti untuk tingkat 4 belum lengkap: perbandingan konsekuensi, asumsi yang perlu diperiksa dan cara peninjauan belum dijelaskan. Tanyakan secara netral: “Apa risiko masing-masing pilihan dan bagaimana Anda memeriksa hasil keputusan?” Skor contoh adalah ilustrasi internal yang belum dinilai asesor; jangan memasukkannya sebagai gold label atau kunci jawaban pada paket uji.

Jika jawaban hanya “Saya mengambil keputusan yang terbaik”, gunakan bukti belum cukup. Jangan menyimpulkan kemampuan kandidat rendah dari jawaban singkat tersebut.

## Paket yang dapat digunakan

Paket awal lokal ada di `data/assessor-em-2026-11-07/` setelah dibuat melalui [perangkat asesor](assessor-validation.md):

- `expertise-review.json`: isian ahli untuk meninjau pekerjaan, kompetensi, bobot dan 25 indikator.
- `assessor-a.html`, `assessor-b.html`, `assessor-c.html`: formulir offline untuk tiga orang berbeda; masing-masing mengunduh JSON penilaiannya setelah selesai.
- `dataset.json`: materi koordinator, 20 kasus sintetis tanpa skor manusia; lima kalibrasi dan 15 uji. Ini paket pilot proses, bukan sampel validasi yang memadai.

Tetapkan peninjau ahli pekerjaan dan tiga asesor relevan sebelum membagikan paket. Paket ini tidak mengundang siapa pun. Identitas, persetujuan, skor dan konsensus harus diisi oleh pelaksana sebenarnya. Jika rubrik berubah setelah tinjauan, buat versi dan paket baru sebelum penilaian substantif.

Setelah rating independen terkumpul, gunakan alur merge → konsensus manusia → evaluasi AI terpisah → perbandingan dalam panduan perangkat. Jangan memasukkan kasus uji atau skor manusia ke prompt AI. Laporan harus menyebut jumlah kasus terukur, kasus yang dikeluarkan, kesepakatan antarasesor, AI–konsensus dan stabilitas AI.

Status saat ini: tersedia dasar penilaian berbasis referensi untuk latihan; tinjauan ahli, rating manusia untuk kasus EM dan bukti validasi rubrik EM masih belum tersedia. Tidak ada persetujuan ahli atau status `validated` yang diisi otomatis.

## Memakai dataset yang sudah dinilai manusia

[Mohler ASAG](mohler-benchmark.md) sudah diunduh dan memiliki dua rating manusia asli per jawaban akademik. Gunakan melalui alat benchmark terpisah; jangan menyalin labelnya menjadi rating atas kasus EM. Sebanyak 214 rata-rata sumber tidak konsisten ditandai dan tidak masuk pilot 50 jawaban. Data ini membantu menguji scorer jawaban teknis setelah run model, tetapi tidak menggantikan tinjauan ahli dan penilaian independen pada rubrik EM. Belum ada hasil AI–manusia.
