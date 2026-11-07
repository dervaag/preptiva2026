# Menggunakan benchmark Mohler di Preptiva

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Dataset sudah diunduh pada 7 November 2026 ke `data/external/mohler-v1/`, di luar Git. Jumlahnya 2.442 jawaban dengan dua rating manusia: 2.273 open-ended dan 169 closed-ended. Sumber: [nkazi/MohlerASAG](https://huggingface.co/datasets/nkazi/MohlerASAG), revisi tetap `dac06732b42d01a5169f543f6d272f1476cced3e`. Dataset card distributor menyatakan CC BY 4.0. Atribusi Mohler, Bunescu dan Mihalcea (2011), tautan paper, lisensi, revisi, perubahan dan hash berkas disimpan di `manifest.json`; dokumentasi sumber asli juga disimpan lokal.

## Pemeriksaan kualitas sumber

Skor asli latihan E01–E10 berskala 0–5; E11–E12 berskala 0–10. Sumber menyediakan `score_avg` pada skala 0–5. Sebanyak 214 baris open-ended memiliki rata-rata yang berbeda dari perhitungan `(grader1 + grader2) / 2 * 5 / original_max`. Ini temuan ketidaksesuaian data, bukan bukti nilai mana yang benar. Nilai asli dipertahankan dan baris tersebut ditandai, tanpa koreksi otomatis. Pilot mengecualikannya; eksklusi ini membatasi keterwakilan sampel.

## Berkas lokal siap pakai

- `data/external/mohler-v1/dataset.json`: semua jawaban, skor penilai asli, rata-rata dari sumber dan penanda kualitas.
- `data/external/mohler-v1/manifest.json`: provenance unduhan dan jumlah ketidaksesuaian.
- `data/external/mohler-pilot-50/inputs.json`: 50 jawaban open-ended yang lolos pemeriksaan konsistensi, tanpa rating manusia.
- `data/external/mohler-pilot-50/labels.json`: rating manusia terpisah, terikat hash masukan.

Pemilihan pilot berdasarkan urutan SHA-256 ID setelah pemeriksaan konsistensi, bukan hasil AI. Belum ada training atau tuning; semua kasus pilot hanya untuk evaluasi. ID AXX merupakan indeks jawaban, bukan identitas peserta; tidak ada klaim split antarorang yang terverifikasi.

## Perintah

Dependensi Parquet hanya untuk impor benchmark, tidak ditambahkan ke server web:

```sh
.venv/bin/pip install -r validation/requirements.txt
.venv/bin/python validation/mohler.py download --output data/external/mohler-new
.venv/bin/python validation/mohler.py prepare data/external/mohler-new/dataset.json --limit 50 --output data/external/mohler-pilot-new
```

Untuk berkas pilot yang sudah tersedia, jalankan evaluasi berikut jika ingin menggunakan kredit OpenAI dari `.env`:

```sh
.venv/bin/python validation/mohler.py run data/external/mohler-pilot-50/inputs.json --output data/external/mohler-run-50 --run-paid
.venv/bin/python validation/mohler.py report data/external/mohler-pilot-50/inputs.json data/external/mohler-pilot-50/labels.json data/external/mohler-run-50 --output data/external/mohler-report-50.json
```

Runner mengirim pertanyaan, jawaban instruktur dan jawaban peserta ke model `MODEL_DEEP` melalui klien aplikasi. Tidak memuat rating manusia. Setiap hasil disimpan segera agar hasil sebelum kegagalan tidak hilang; resume otomatis belum tersedia. Gunakan direktori baru jika menjalankan ulang. Perintah menolak menimpa artefak yang sudah ada. Report menolak hasil yang belum lengkap atau hash input berbeda.

Keluaran report: jumlah kasus, model/provenance prompt, Spearman, MAE skala 0–5, persentase selisih maksimal satu poin, dan pasangan skor per kasus. Tidak menghasilkan prediksi tanpa panggilan model nyata. Unduhan dan persiapan lokal tidak memakai kredit AI; runner berbayar belum dijalankan sebagai bagian penyiapan ini.

## Hubungan dengan aplikasi

Ini benchmark terpisah untuk penilaian jawaban akademik berbasis jawaban acuan, menggunakan klien model Preptiva. Promptnya berbeda dari evaluator wawancara produksi. Dataset tidak dimasukkan ke prompt wawancara pengguna dan tidak mengubah skor sesi. Pengujian ini belum memvalidasi evaluator produksi, kepemimpinan, non-IT atau keseluruhan rubrik EM. `validated` tetap false. Data publik juga mungkin pernah masuk pelatihan model.
