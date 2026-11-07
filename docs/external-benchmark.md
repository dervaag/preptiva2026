# Benchmark eksternal penilaian manusia

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Pemeriksaan sumber: 7 November 2026. Tiga dataset wawancara di bawah belum diunduh. Tindak lanjut: [Mohler ASAG telah diunduh dan disiapkan sebagai benchmark terpisah](mohler-benchmark.md); belum ada metrik AI–manusia dari run model. Status rubrik tetap `validated: false`.

## Hasil pemeriksaan penggunaan

| Sumber resmi | Temuan | Keputusan untuk Preptiva |
| --- | --- | --- |
| [RecruitView dataset card](https://huggingface.co/datasets/AI4A-lab/RecruitView) | Bagian Ethical Considerations & Usage Policy membatasi penggunaan akademik dan secara eksplisit melarang aplikasi wawancara AI, penilaian dan umpan balik wawancara; data lengkap melalui persetujuan akses | Tidak diimpor. Contoh publik GitHub tidak menghapus pembatasan penggunaan tersebut |
| [MIT Interview Dataset](https://roc-hci.com/past-projects/automated-prediction-of-job-interview-performances/) | Bagian MIT Interview Dataset menyatakan rating sembilan penilai dan permohonan melalui email akademik dengan persetujuan ketentuan | Kandidat untuk penelitian terpisah setelah izin sesuai tujuan diperoleh. Izin belum diperoleh; kelayakan penggunaan produk belum diketahui |
| [AVI-Personality](https://apal-seu.github.io/AVI6/) | Bagian Access menyatakan riset akademik nonkomersial, perjanjian ditandatangani peneliti berposisi tetap dan persetujuan pemilik data | Bukan sumber bebas untuk produk. Penggunaan riset terpisah memerlukan institusi dan izin; belum diperoleh |

Koreksi terhadap rekomendasi awal: RecruitView bukan pilihan yang langsung bisa dipakai pada aplikasi ini. Akses publik ke contoh bukan izin penggunaan untuk penilaian wawancara. Tidak ada pengiriman formulir, persetujuan ketentuan, atau kontak kepada pemilik dataset atas nama pengguna.

## Pemanfaatan metodologi

Pemeriksaan sumber menghasilkan ketentuan benchmark berikut:

1. Simpan rating manusia pada target dan skala aslinya. Skor kualitas jawaban, kesan wawancara dan kepribadian tidak diubah menjadi lima kompetensi EM.
2. Pisahkan benchmark eksternal dari `human_ratings` dan konsensus pada dataset Preptiva. Nilai rata-rata dataset bukan tiga rating independen baru.
3. Pisahkan peserta antara kalibrasi dan uji agar jawaban orang yang sama tidak bocor ke kedua set. Pertahankan split resmi jika ada.
4. Skor AI dibuat tanpa melihat label manusia. Catat model, hash prompt, versi sumber, definisi target, protokol anotasi dan izin penggunaan.
5. Nilai hubungan peringkat pada target yang sebanding; hasil tetap tidak mengesahkan rubrik EM, konteks Indonesia atau penilaian transkrip jika manusia menilai video.

## Pembanding yang sudah diimplementasikan

`validation/external_compare.py` menghitung Spearman dengan penanganan skor seri, jumlah kasus dan jumlah peserta. Skala tidak dipaksakan menjadi 1–5. Distribusi konstan menghasilkan korelasi `null`, bukan angka yang dikarang. Kasus duplikat, skor kosong/nonfinite, campuran target dan kasus non-uji ditolak. Alat tidak mengunduh data, tidak mengirim transkrip ke provider, dan tidak menandai hasil sebagai tervalidasi.

Setelah data yang diizinkan dan prediksi AI tersedia, simpan CSV privat di `data/external/` dengan kolom:

```csv
case_id,participant_id,target,split,human_score,ai_score
```

Salin `validation/external-provenance.example.json` ke direktori privat tersebut dan isi berdasarkan bukti sebenarnya. `permission_reference` harus menunjuk izin/ketentuan yang sesuai konteks; `use_permitted` tidak boleh diisi hanya karena data terlihat publik. Form isian provenance merupakan catatan koordinator, bukan pemeriksa izin otomatis. Kemudian:

```sh
.venv/bin/python validation/external_compare.py data/external/scores.csv --provenance data/external/provenance.json --output data/external/comparison.json
```

Belum ada runner otomatis atau adapter format dataset tertentu karena file sumber dan izin belum tersedia. AI tidak boleh dijalankan atas data terikat ketentuan sebelum penggunaan provider pihak ketiga juga diperiksa. Korelasi merupakan hubungan peringkat, bukan persentase akurasi atau kesepakatan skor; alat tidak menghitung interval keyakinan dan belum mengoreksi ketergantungan antarjawaban peserta.

## Materi permohonan akses untuk koordinator

Draf berikut belum dikirim. Pilih pemilik dataset dan lengkapi identitas asli sebelum dipakai; jangan menyatakan tujuan komersial sebagai akademik.

> Kami mengembangkan Preptiva, aplikasi latihan wawancara. Kami ingin mengevaluasi hubungan penilaian AI berbasis transkrip dengan rating manusia pada target yang sebanding. Mohon konfirmasi apakah penelitian terpisah dari aplikasi produk ini diizinkan, apakah transkrip dan rating tersedia, serta apakah pemrosesan melalui API pihak ketiga diizinkan. Kami akan mempertahankan label asli, split peserta, atribusi dan batas distribusi. Institusi, status penelitian/komersial, provider pemrosesan dan rencana publikasi: [diisi koordinator]. Kami belum mengunduh atau menggunakan data terbatas Anda.

Jika pengguna tidak memiliki afiliasi akademik atau izin sesuai penggunaan, lanjutkan dengan rating manusia atas materi yang memang boleh digunakan, sesuai [panduan asesor](assessor-validation.md).
