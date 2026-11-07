# Menyiapkan pembandingan AI–asesor

Status 7 November 2026: perangkat lunak dan paket penilaian tanpa skor AI tersedia. **Asesor belum tersedia; belum ada penilaian independen, konsensus manusia, atau hasil validasi AI–manusia.** Semua perintah mempertahankan `validated: false`. Rubrik khusus Engineering Manager/persona Manager masih draf internal yang belum ditinjau ahli pekerjaan; rencana dan syarat peninjauannya ada di [rubric-validation-plan.md](rubric-validation-plan.md).

## Paket yang tersedia

- **Paket umum lama:** `data/assessor-kit-2026-11-07/`, tujuh contoh sintetis memakai rubrik umum `2026-11-05.2`. Form/hasil yang sudah dibagikan tetap dapat diimpor; hash format lama dipertahankan.
- **Paket draf Engineering Manager:** paket lokal siap dibagikan berada di `data/assessor-em-2026-11-07/packets.zip`; `dataset.json` koordinator ada di direktori yang sama. Dapat dibuat ulang pada direktori baru dengan `init --profile engineering-manager`. Memakai snapshot [rubrik EM](engineering-manager-rubric.md), lima kompetensi khusus, dan 20 contoh sintetis: lima kalibrasi serta 15 uji yang ditentukan sebelum penilaian. Setiap kompetensi memiliki empat konteks dengan bahasa Indonesia, Inggris, atau campuran. Ini bahan tinjauan dan uji alur kerja, **bukan gold set atau ukuran sampel validasi yang memadai**.

Pseudonim asesor-a/b/c belum menunjuk orang tertentu. Koordinator perlu menetapkan tiga orang berbeda yang memiliki kualifikasi relevan. Alat tidak mengundang asesor, memverifikasi identitas, atau mengisi skor manusia. Kompetensi, bobot, indikator, serta cakupan sampel harus ditinjau ahli sebelum hasil digunakan untuk klaim pengujian substantif. Target sampel yang lebih luas tetap mengikuti rencana, dengan keputusan kecukupan oleh ahli.

## Tinjauan ahli sebelum pengujian substantif

Paket lokal `data/assessor-em-2026-11-07/expertise-review.json` menyediakan isian kosong untuk ahli pekerjaan. Bagian `reference` memuat usulan saat ini, bukan persetujuan: sumber JD/tugas, relevansi lingkup, pemetaan tanggung jawab, lima kompetensi/bobot, serta seluruh 25 jangkar perilaku. Identitas/peran/pengalaman peninjau, keputusan, komentar dan tanggal masih kosong; `review_completed`, `job_reviewed_by_human` dan `validated` tetap false.

Template yang sama dapat dibuat untuk dataset baru:

```sh
python3 validation/kit.py expertise-review-template data/assessor-em/dataset.json --output data/assessor-em/expertise-review.json
```

Ahli meninjau kesesuaian pekerjaan, kejelasan dan perbedaan antarlevel, serta ketepatan pemetaan sumber; koordinator menyimpan hasil dan menindaklanjuti revisi. Mengisi template tidak otomatis mengganti status atau mengaktifkan rubrik sebagai tervalidasi. Perubahan indikator/bobot harus menghasilkan snapshot dan paket versi baru sebelum penilaian berikutnya.

## 1. Membuat dan membagikan formulir

```sh
python3 validation/kit.py init --profile engineering-manager --output data/assessor-em/dataset.json
python3 validation/kit.py pack data/assessor-em/dataset.json --assessor assessor-a --output data/assessor-em/assessor-a.html
python3 validation/kit.py pack data/assessor-em/dataset.json --assessor assessor-b --output data/assessor-em/assessor-b.html
python3 validation/kit.py pack data/assessor-em/dataset.json --assessor assessor-c --output data/assessor-em/assessor-c.html
```

Tanpa `--profile`, `init` tetap membuat paket umum lama. Semua perintah menolak menimpa file yang sudah ada. Gunakan direktori baru untuk versi rubrik/dataset berikutnya. `dataset.json` adalah berkas koordinator; bagikan satu HTML kepada setiap asesor.

HTML mandiri dapat dibuka offline. Form memuat konteks pekerjaan/level, indikator tingkat 1–5, ID dan sumber indikator, pertanyaan, transkrip serta kompetensi. **Skor AI, skor asesor lain, konsensus, dan label kalibrasi/uji tidak dimasukkan ke formulir.** Form tidak mengirim data ke server atau menyimpan isian otomatis; asesor harus mengunduh JSON sebelum menutup halaman.

Untuk setiap kasus, asesor:

1. Memilih skor 1–5 yang didukung bukti, atau **bukti belum cukup** tanpa skor. Kekurangan bukti tidak disamakan dengan kemampuan rendah.
2. Menyalin kutipan asli, memilih indikator pada kompetensi dan tingkat skor yang sama, serta menulis alasan. Tingkat merupakan jangkar alternatif, bukan daftar tingkat rendah yang harus dipenuhi secara kumulatif.
3. Untuk skor 1–4, menjelaskan bukti yang belum tersedia untuk menilai tingkat berikutnya. Skor 5 tidak memiliki tingkat berikutnya. Penilaian `insufficient` tidak mengklaim indikator tercapai.
4. Menyatakan bahwa ia menilai sendiri secara independen tanpa melihat skor AI atau asesor lain, lalu mengunduh `ratings-<pseudonim>.json`.

Kutipan literal dan ID valid hanya membuktikan keterlacakan struktur. Relevansi kutipan terhadap indikator tetap merupakan penilaian manusia. Pernyataan form juga tidak menggantikan verifikasi kualifikasi/independensi oleh koordinator.

## 2. Menggabungkan penilaian independen

```sh
python3 validation/kit.py merge data/assessor-em/dataset.json /path/ratings-assessor-a.json /path/ratings-assessor-b.json /path/ratings-assessor-c.json --output data/assessor-em/human-rated.json
```

Format EM mengikat hash pada snapshot penuh, pekerjaan/level/persona, metadata dataset, pertanyaan, kompetensi, bahasa, transkrip, dan split. Perubahan materi setelah formulir dibuat menyebabkan penolakan impor. Merge memeriksa kasus lengkap, asesor unik, pernyataan independensi, skor/status, kutipan literal, ID indikator sesuai tingkat/kompetensi, serta alasan dan gap. Rating yang telah diimpor tidak boleh ditimpa.

Skor independen disimpan pada `human_ratings`; kutipan, indikator, alasan dan gap pada `human_evidence`. Status bukti kurang disimpan sebagai `null`, tanpa mengarang skor. Metadata impor mencatat pseudonim, assignment, waktu impor dan batas bahwa alat tidak memverifikasi identitas. Dataset asli tidak diubah; hasil selalu ditulis ke berkas baru.

## 3. Menetapkan konsensus setelah pembahasan

```sh
python3 validation/kit.py consensus-template data/assessor-em/human-rated.json --output data/assessor-em/consensus-decisions.json
```

Perintah ini menolak dataset yang belum memiliki penilaian sekurangnya tiga asesor yang sama pada semua kasus. Template berisi keputusan kosong; alat **tidak menghitung rata-rata untuk dijadikan konsensus**. Koordinator meninjau skor dan alasan independen di `human-rated.json`, membahas perbedaan bersama asesor, lalu mengisi `coordinator_id`, `reviewed_independent_ratings: true`, dan seluruh `decisions` pada template.

Setiap keputusan memerlukan `status` (`measured`/`insufficient`), `score` (1–5/null), `quote`, `indicators_met`, `rationale`, serta `next_level_gap` sesuai aturan yang sama dengan formulir. Bila masih belum cukup bukti, konsensus tetap `insufficient`, bukan skor yang dipaksakan. Setelah keputusan selesai:

```sh
python3 validation/kit.py consensus data/assessor-em/human-rated.json data/assessor-em/consensus-decisions.json --output data/assessor-em/consensus-rated.json
```

Impor memeriksa hash dataset **dan penilaian independen**, sehingga perubahan rating setelah template dibuat terdeteksi. Skor independen dipertahankan, konsensus yang sudah ada tidak ditimpa, dan metadata koordinator/tinjauan dicatat. Persetujuan ini merupakan catatan proses, bukan verifikasi identitas atau validasi otomatis.

## 4. Menjalankan AI secara terpisah

```sh
.venv/bin/python validation/kit.py run-ai data/assessor-em/consensus-rated.json --run-paid --output data/assessor-em/ai-rated.json
```

Runner memakai evaluator dan pemeriksa indikator yang sama dengan aplikasi, lima run logis independen per kasus. Konteks prompt hanya berisi pertanyaan/transkrip, pekerjaan/persona, rubrik dan indikator yang relevan; **skor manusia dan konsensus tidak disertakan**. Setiap run menyimpan skor terverifikasi/status, kutipan, detail indikator dan sumber. Model, hash modul evaluator, hash konteks prompt, serta waktu mulai dicatat sebagai provenance. Hash modul mencakup kode evaluator; bukan jaminan versi internal model provider tetap sama.

`--run-paid` wajib karena memakai kredit API. Paket EM 20 kasus berarti 100 run logis, termasuk kasus kalibrasi yang nanti dikeluarkan dari komparasi uji. Evaluator EM dapat melakukan satu percobaan perbaikan struktur untuk setiap run, sehingga totalnya dapat mencapai 200 panggilan model. Paket umum tujuh kasus berarti 35 run/panggilan evaluator tanpa retry struktur EM. Hasil AI yang sudah ada tidak ditimpa. Runner tidak otomatis dijalankan saat membuat paket. Bila keluaran yang diterima memiliki bukti tidak cukup, skor pembandingan tetap `null`. Jika struktur EM tetap tidak valid setelah satu perbaikan, evaluator gagal dan runner berhenti. Runner saat ini hanya menulis berkas hasil setelah seluruh kasus selesai; kegagalan di tengah proses dapat membuat hasil run sebelumnya tidak tersimpan walaupun kredit API sudah terpakai. Belum ada checkpoint atau resume, sehingga mulai dengan batch kecil pada dataset terpisah sebelum menjalankan seluruh paket.

## 5. Membandingkan dengan denominator yang jelas

```sh
python3 validation/compare.py data/assessor-em/ai-rated.json --output data/assessor-em/comparison.json
```

Dataset EM harus melewati impor konsensus sebelum analisis. Laporan memuat:

- Jumlah total, kasus uji, kasus yang dapat dibandingkan, serta ID kalibrasi yang dikeluarkan.
- Kasus uji yang dikeluarkan dari komparasi lengkap beserta alasan: bukti manusia, konsensus, atau AI belum cukup. Nilai kosong tidak diubah menjadi skor.
- Quadratic weighted kappa tiap pasangan asesor, dengan jumlah pasangan skor terukur yang benar-benar tersedia.
- Kappa AI run pertama terhadap konsensus, galat absolut rata-rata, dan persentase selisih maksimal satu poin, memakai kasus dengan semua rating independen, konsensus, dan seluruh run AI terukur.
- Stabilitas rentang skor AI maksimal satu poin, dengan denominator khusus kasus yang semua run AI-nya terukur.
- Kutipan literal, hasil deskriptif per bahasa dan per kompetensi, serta provenance.

Setiap kasus uji tetap membutuhkan minimal tiga asesor yang sama dan lima run AI. Kalibrasi dikeluarkan secara eksplisit. Jika tidak ada kasus yang dapat dibandingkan, metrik menjadi `null` dengan denominator nol. Kappa juga `null` bila distribusinya konstan. Dua kasus uji hanyalah minimum komputasi, **bukan sampel validasi yang cukup**. Eksklusi kasus dapat membiasakan estimasi; jumlah dan alasannya harus ditinjau sebelum interpretasi.

Keberadaan kutipan tidak membuktikan relevansinya. Statistik kelompok kecil bukan bukti fairness, dan perbandingan bahasa saja bukan pengujian dampak kesalahan STT. Studi sensitivitas STT dan tinjauan relevansi pekerjaan tetap pekerjaan tersendiri. Tidak ada perintah yang mengubah rubrik menjadi `validated: true`.

Simpan jawaban nyata/hasil penilaian di luar repository. `data/` diabaikan Git dan tidak dimasukkan ke image deployment. Gunakan data sintetis atau data dengan persetujuan yang telah dianonimkan; jangan memasukkan CV/transkrip kandidat nyata ke artefak publik CI.
